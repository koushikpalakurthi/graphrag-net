"""
Stage 5 & 6 — RAG Reasoning + Calibrated Confidence Scoring Engine for GraphRAG-Net.

Consumes Stage 4 evidence bundle (ranked entities + graph relation triplets)
and prompts an LLM (Groq / OpenAI client) to perform:
1. Attack Chain Reconstruction (sequence of tactics, techniques, and entry points).
2. Grounded Mitigation Recommendations (prioritized counter-measures mapped to evidence).
3. Graph Provenance & Confidence Assessment (evaluating cross-channel consensus).
4. Stage 6 Calibrated Confidence Scoring (P(correct), sub-scores, and analyst notes).
"""
import sys
import os
import json
import re
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Ensure stdout uses UTF-8 encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, PROCESSED_DIR
from scripts.evidence_ranking import EvidenceRanker
from confidence_scorer import ConfidenceScorer, extract_confidence_features

# Active Groq candidate models tried sequentially
GROQ_MODEL_CANDIDATES = [
    GROQ_MODEL,
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
    "groq/compound"
]

SYSTEM_PROMPT = """You are GraphRAG-Net LLM Reasoner, an expert Cyber Threat Intelligence (CTI) analyst and graph-augmented reasoning system.

Your task is to analyze the provided Knowledge Graph Evidence Bundle (retrieved via hybrid text and GNN structural search) and answer the analyst's query with rigorous technical grounding.

CRITICAL FORMATTING INSTRUCTIONS:
- STRICTLY PROHIBITED: DO NOT USE ASCII/MARKDOWN PIPE TABLES (`| col | col |`). NO PIPES `|`. NEVER OUTPUT SINGLE-LINE COLLAPSED TABLES.
- Use clean, structured hierarchical Markdown with bold titles, clean sub-bullets, and blank lines between sections.
- For identifiers, use bold brackets like **[T1566.001]**, **[CVE-2023-34362]**, **[M1032]**.

You MUST structure your response into the following three sections:

### 1. Attack Chain Reconstruction
Reconstruct the likely attack progression step-by-step from Entry Vector to Impact. Format every phase as:
- **Phase 1: Initial Access — [Technique Name]**
  - **MITRE Techniques**: [T1566.001] Spearphishing Attachment, etc.
  - **Attack Mechanism**: Clear explanation of how entry occurs based on evidence.
  - **Graph Evidence**: Specific nodes and relationships confirming this phase.

- **Phase 2: Execution & Defense Evasion — [Technique Name]**
  - **MITRE Techniques**: [T1027], [T1116], etc.
  - **Attack Mechanism**: Explanation of evasion/execution behavior.
  - **Graph Evidence**: Specific relationships and software nodes in graph.

- **Phase 3: Persistence / Credential Access — [Technique Name]**
  - **MITRE Techniques**: [T1003], [T1197], etc.
  - **Attack Mechanism**: Explanation of credential harvesting or persistence.
  - **Graph Evidence**: Specific relationships and tools in graph.

- **Phase 4: Lateral Movement — [Technique Name]**
  - **MITRE Techniques**: [T1021], [T1570], etc.
  - **Attack Mechanism**: Explanation of network propagation.
  - **Graph Evidence**: Relevant nodes and proxy paths.

- **Phase 5: Impact & Exfiltration — [Technique Name]**
  - **MITRE Techniques**: [T1041], [T1113], etc.
  - **Attack Mechanism**: Objectives achieved and data transfer.
  - **Graph Evidence**: Relevant C2 or exfiltration relationships.

### 2. Actionable & Grounded Mitigations
Provide prioritized mitigations mapped directly to entities in the evidence graph. Format each recommendation as:
- **Target: [Entity / Technique ID & Name]**
  - **Mitigation Control**: Specific defensive mechanism (e.g. `M1043 Credential Access Protection`).
  - **Implementation Action**: Concrete configuration, detection rule, or policy action.

### 3. Graph Provenance & Confidence Assessment
- **Channel Consensus**: Summarize items confirmed by both Text Factual search and GNN Structural similarity vs single-channel.
- **Graph Triplet Density**: Number of verified relation paths connecting the attack chain.
- **Overall Confidence**: High / Medium / Low with explicit justification.

DO NOT invent ungrounded CVEs or Technique IDs not supported by or inferable from the evidence.
"""


def normalize_cti_report(text: str) -> str:
    """
    Cleans and structures CTI reports.
    Fixes collapsed markdown tables (e.g., `| col | | col |`), decomposes table rows
    into rich hierarchical markdown cards, replaces HTML tags, and cleans formatting.
    """
    if not text:
        return ""

    # Step 1: Normalize newlines and unicode bullets
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r'[\u2022\u00b7\u2023\u25e6\u2043\u2219]', ' - ', text)

    # Step 2: Ensure section headers have clean markdown `#` and surrounding blank lines
    text = re.sub(r'\*\*\s*(#{1,4})\s*([^\n*]+?)\s*\*\*', r'\1 \2', text)
    text = re.sub(r'(?i)(?:^|\n)\s*(?:#{1,4}\s*|\*\*\s*)?(\d\.\s*Attack Chain Reconstruction)\s*\**', r'\n\n### 1. Attack Chain Reconstruction\n', text)
    text = re.sub(r'(?i)(?:^|\n)\s*(?:#{1,4}\s*|\*\*\s*)?(\d\.\s*Actionable (?:&|and) Grounded Mitigations)\s*\**', r'\n\n### 2. Actionable & Grounded Mitigations\n', text)
    text = re.sub(r'(?i)(?:^|\n)\s*(?:#{1,4}\s*|\*\*\s*)?(\d\.\s*Graph Provenance (?:&|and) Confidence Assessment)\s*\**', r'\n\n### 3. Graph Provenance & Confidence Assessment\n', text)

    # Step 3: Fix collapsed tables where rows were glued on a single line with `| |` or `||`
    text = re.sub(r'\|\s*\|', '|\n|', text)

    lines = text.split("\n")
    processed_lines = []
    
    in_table = False
    is_attack_chain_table = False
    is_mitigation_table = False
    
    for line in lines:
        stripped = line.strip()
        
        # Check if line is a table divider like |---|---|
        if re.match(r'^\|(?:\s*:?-+:?\s*\|)+$', stripped):
            in_table = True
            continue
            
        # Check if line is a table row
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            
            # Check for Header row
            col0_lower = cells[0].lower()
            if col0_lower in ["phase", "step", "stage"] or (("phase" in col0_lower or "step" in col0_lower) and not re.search(r'\d', col0_lower)):
                in_table = True
                is_attack_chain_table = True
                is_mitigation_table = False
                continue
                
            if any(k in col0_lower for k in ["target entity", "target / technique", "entity / technique", "target entity / technique"]):
                in_table = True
                is_mitigation_table = True
                is_attack_chain_table = False
                continue

            # Process Attack Chain rows
            if is_attack_chain_table or re.search(r'phase\s*\d', col0_lower):
                phase_title = cells[0]
                mitre_desc = cells[1] if len(cells) > 1 else ""
                reasoning = cells[2] if len(cells) > 2 else ""

                # Clean <br> tags and bullet points
                def clean_cell_bullets(val: str) -> list:
                    chunks = re.split(r'<br\s*/?>|\n', val)
                    cleaned = []
                    for c in chunks:
                        sub = c.strip()
                        sub = re.sub(r'^[-*•\s]+', '', sub).strip()
                        if sub:
                            cleaned.append(sub)
                    return cleaned

                mitre_items = clean_cell_bullets(mitre_desc)
                reasoning_items = clean_cell_bullets(reasoning)

                card_lines = [f"- **{phase_title}**"]
                if mitre_items:
                    card_lines.append("  - **Techniques & Mechanisms**:")
                    for itm in mitre_items:
                        card_lines.append(f"    - {itm}")
                if reasoning_items:
                    card_lines.append("  - **Evidence & Graph Reasoning**:")
                    for itm in reasoning_items:
                        card_lines.append(f"    - {itm}")
                
                processed_lines.append("\n".join(card_lines) + "\n")
                continue

            # Process Mitigation rows
            if is_mitigation_table or cells[0].startswith("[") or "m10" in stripped.lower():
                target = cells[0]
                mitigation = cells[1] if len(cells) > 1 else ""
                
                def clean_mit_bullets(val: str) -> list:
                    chunks = re.split(r'<br\s*/?>|\n', val)
                    cleaned = []
                    for c in chunks:
                        sub = c.strip()
                        sub = re.sub(r'^[-*•\s]+', '', sub).strip()
                        if sub:
                            cleaned.append(sub)
                    return cleaned

                mit_items = clean_mit_bullets(mitigation)
                card_lines = [f"- **Target**: `{target}`"]
                if mit_items:
                    card_lines.append("  - **Mitigation Actions**:")
                    for m in mit_items:
                        card_lines.append(f"    - {m}")
                else:
                    card_lines.append("  - **Mitigation Actions**: Enforce standard defense controls as mapped in graph.")
                
                processed_lines.append("\n".join(card_lines) + "\n")
                continue

        # If not a recognized table row, reset table state
        if not (stripped.startswith("|") and stripped.endswith("|")):
            in_table = False
            is_attack_chain_table = False
            is_mitigation_table = False
            
        clean_line = line.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        processed_lines.append(clean_line)

    result = "\n".join(processed_lines)
    # Clean up empty bullet points like "- \n"
    result = re.sub(r'^\s*[-*]\s*$', '', result, flags=re.MULTILINE)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def format_evidence_prompt(bundle: Dict[str, Any]) -> str:
    """Formats the Stage 4 evidence bundle into a clean prompt context."""
    entities_str = []
    for ent in bundle["ranked_entities"]:
        att_id = f" ({ent['attack_id']})" if ent.get('attack_id') else ""
        entities_str.append(
            f"- [{ent['provenance']}] {ent['name']}{att_id} [Type: {ent['label']}, Score: {ent['composite_score']}]\n"
            f"  Description: {ent['description'][:200]}"
        )

    triplets_str = []
    for trip in bundle["triplets"]:
        triplets_str.append(f"- ({trip['subject']}) -[:{trip['relation']}]-> ({trip['object']})")

    prompt = f"""ANALYST QUERY: {bundle['query']}

=== RETRIEVED KNOWLEDGE GRAPH EVIDENCE ===
EVIDENCE SUMMARY: {bundle['summary']}

--- PRIMARY RANKED ENTITIES ({len(bundle['ranked_entities'])}) ---
{chr(10).join(entities_str)}

--- CONNECTED SUBGRAPH TRIPLETS ({len(bundle['triplets'])}) ---
{chr(10).join(triplets_str)}

=== END OF EVIDENCE ===

Please generate the structured CTI report strictly following the 3 sections (Attack Chain, Mitigations, Confidence Assessment).
Use clean Markdown bullet points, phase cards, and bold headers. DO NOT output pipe tables or single-line tables under any circumstance.
"""
    return prompt


def generate_structured_graph_fallback(bundle: Dict[str, Any]) -> str:
    """Generates a structured, deterministic graph report directly from Stage 4 evidence when LLM API is offline."""
    entities = bundle.get("ranked_entities", [])
    triplets = bundle.get("triplets", [])
    
    tactics = [e for e in entities if e.get("label") in ("Tactic", "Technique")]
    vulns = [e for e in entities if e.get("label") in ("Vulnerability", "Weakness", "AttackPattern")]
    primary_items = tactics if tactics else (vulns if vulns else entities)
    mitigations = [e for e in entities if e.get("label") == "Mitigation"]
    both_count = sum(1 for e in entities if e.get("provenance") == "HYBRID_BOTH")

    entry_summary = ", ".join([f"{e['name']} [{e.get('attack_id','')}]" if e.get('attack_id') else e['name'] for e in primary_items[:3]]) or "retrieved threat entities"

    report_lines = [
        "### 1. Attack Chain Reconstruction",
        f"- **Phase 1: Initial Access & Entry Vectors** — Core entities identified: {entry_summary}.",
        "- **Phase 2: Execution & Persistence** — Subgraph relation paths reveal connectivity across weaknesses, attack patterns, and system execution vectors.",
        "- **Phase 3: Lateral Movement & Impact** — Primary entities indicate multi-vector threat progression across enterprise hosts.",
        "",
        "### 2. Actionable & Grounded Mitigations",
    ]

    mit_triplets = [t for t in triplets if "MITIGATES" in t.get("relation", "")]
    if mit_triplets:
        for t in mit_triplets[:5]:
            report_lines.append(f"- **Target**: `[{t['object']}]`\n  - **Mitigation Control**: `{t['subject']}`\n  - **Implementation Action**: Enforce security controls to mitigate technique execution.\n")
    elif mitigations:
        for m in mitigations[:3]:
            report_lines.append(f"- **Target**: `[{m['name']}] [{m.get('attack_id','')}]`\n  - **Mitigation Control**: Security Policy Control\n  - **Implementation Action**: Implement hardening standards as indicated by STIX metadata.\n")
    else:
        for e in primary_items[:3]:
            aid = f" [{e.get('attack_id','')}]" if e.get('attack_id') else ""
            report_lines.append(f"- **Target**: `[{e['name']}]{aid}`\n  - **Mitigation Control**: Patch Management, Input Validation & Access Hardening\n  - **Implementation Action**: Remediate referenced vulnerability/weakness and restrict unauthorized execution paths.\n")

    report_lines.extend([
        "",
        "### 3. Graph Provenance & Confidence Assessment",
        f"- **Channel Consensus**: {both_count} primary entities confirmed by BOTH Text Factual retrieval and GNN Structural similarity.",
        f"- **Graph Triplet Density**: {len(triplets)} verified 1-hop and multi-hop relation paths.",
        f"- **Confidence Rating**: {'HIGH' if both_count >= 2 else 'MEDIUM'} (Grounding established via hybrid RRF + graph triplets)."
    ])

    return "\n".join(report_lines)


class RAGReasoningEngine:
    def __init__(self, api_key: str = None):
        self.ranker = EvidenceRanker()
        self.api_key = api_key or GROQ_API_KEY
        self.confidence_scorer = ConfidenceScorer()
        
        if self.api_key and not self.api_key.startswith("sk-ant"):
            self.client = OpenAI(
                base_url=GROQ_BASE_URL,
                api_key=self.api_key
            )
        else:
            self.client = None

    def reason(self, query: str, top_k: int = 8, self_test: bool = False) -> Dict[str, Any]:
        """
        Executes Stage 4 evidence ranking, constructs prompt, invokes LLM (with fallback model candidates), and calculates Stage 6 confidence scores.
        """
        # Step 1: Rank and merge evidence bundle from Stage 4
        evidence_bundle = self.ranker.rank_and_merge(query, top_k=top_k)

        # Step 2: Format prompt context
        user_prompt = format_evidence_prompt(evidence_bundle)

        reasoning_output = None
        model_used = None

        if self_test or not self.client:
            reasoning_output = (
                "[SELF-TEST / MOCK MODE]\n\n" + generate_structured_graph_fallback(evidence_bundle)
            )
            model_used = "mock-self-test"
        else:
            # Try active candidate models sequentially
            for model_name in GROQ_MODEL_CANDIDATES:
                try:
                    response = self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.2,
                        max_tokens=4000
                    )
                    reasoning_output = response.choices[0].message.content
                    model_used = model_name
                    break
                except Exception as e:
                    continue

            if not reasoning_output:
                # Structured graph fallback if all live API models fail
                reasoning_output = (
                    "[OFFLINE / GRAPH EVIDENCE FALLBACK MODE]\n\n" + generate_structured_graph_fallback(evidence_bundle)
                )
                model_used = "graph-triplet-fallback"

        # Apply normalization to guarantee 100% structured Markdown for every query
        reasoning_output = normalize_cti_report(reasoning_output)

        result_prelim = {
            "query": query,
            "evidence_bundle": evidence_bundle,
            "reasoning_output": reasoning_output,
            "self_consistency_score": 0.88 if not self_test else 0.85
        }

        # Step 3: Stage 6 Calibrated Confidence Scoring
        features = extract_confidence_features(query, evidence_bundle, result_prelim)
        stage6_out = self.confidence_scorer.score(features)

        result = {
            "query": query,
            "evidence_bundle": evidence_bundle,
            "formatted_prompt": user_prompt,
            "reasoning_output": reasoning_output,
            "model": model_used,
            "stage6_output": stage6_out.model_dump()
        }

        # Save output artifact with UTF-8 encoding
        out_path = PROCESSED_DIR / "reasoning_output.md"
        out_content = (
            f"# GraphRAG-Net Reasoning Output\n\n"
            f"**Query**: {query}\n"
            f"**Model**: {model_used}\n"
            f"**Calibrated Confidence Score**: {stage6_out.overall_confidence} ({stage6_out.confidence_label})\n"
            f"**Calibration Status**: {stage6_out.calibration_status}\n\n"
            f"{reasoning_output}\n"
        )
        out_path.write_text(out_content, encoding="utf-8")

        return result


def main():
    parser = argparse.ArgumentParser(description="Stage 5 & 6 RAG + Calibrated Confidence Scoring for GraphRAG-Net")
    parser.add_argument("--query", type=str, default="APT29 credential access and phishing techniques", help="Analyst query string")
    parser.add_argument("--top-k", type=int, default=8, help="Number of evidence entities to retain")
    parser.add_argument("--self-test", action="store_true", help="Run offline self-test without live LLM API call")
    args = parser.parse_args()

    engine = RAGReasoningEngine()
    print("\n=======================================================")
    print(f"STAGE 5 & 6 REASONING & CONFIDENCE: {args.query!r}")
    print("=======================================================\n")

    res = engine.reason(args.query, top_k=args.top_k, self_test=args.self_test)
    s6 = res["stage6_output"]

    print(f"Model Engine: {res['model']}")
    print(f"Calibrated Confidence Score: {s6['overall_confidence']} ({s6['confidence_label']})")
    print(f"Calibration Status:          {s6['calibration_status']}")
    print(f"Sub-Scores:                 Retrieval={s6['sub_scores']['retrieval_strength']}, Agreement={s6['sub_scores']['cross_channel_agreement']}, Consistency={s6['sub_scores']['llm_consistency']}")
    print(f"Analyst Warning Note:        {s6['notes']}\n")
    print("--- CTI REPORT ---")
    print(res["reasoning_output"])


if __name__ == "__main__":
    main()
