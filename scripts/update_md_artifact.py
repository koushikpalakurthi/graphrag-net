import re
import os

md_path = r"C:\Users\koush\.gemini\antigravity-ide\brain\9b01394d-6e00-4b65-8c18-7061d9b144a3\GraphRAG_Net_CTI_Thinker_Style_Report.md"

with open("scripts/generate_report.py", "r", encoding="utf-8") as f:
    py_code = f.read()

# Extract abstract
abstract_match = re.search(r'p_abstract = \(\s*\"(.*?)\"\s*\)', py_code, re.DOTALL)
abstract_text = abstract_match.group(1).replace('"\n        "', ' ').replace('"\n        ', ' ') if abstract_match else ""

# Extract 20 papers tuples
tuples = re.findall(r'\(\s*"(2\.3\.\d+\. Paper \d+:[^"]+)"\s*,\s*"([^"]+)"\s*,\s*"(.*?)"\s*\)', py_code, re.DOTALL)

# Extract survey_data_20 from generate_report.py
survey_matches = re.findall(r'\(\s*"(\d+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', py_code)

md_table = "| S.No. | Title of Paper & Journal (Year) | Method / Approach | Key Contribution | Gap Identified |\n"
md_table += "| :--- | :--- | :--- | :--- | :--- |\n"
for sno, ptitle, pmethod, pcontrib, pgap in survey_matches:
    md_table += f"| {sno} | {ptitle} | {pmethod} | {pcontrib} | {pgap} |\n"

md_content = f"""# GRAPHRAG-NET: A HETEROGENEOUS KNOWLEDGE GRAPH-AUGMENTED AGENTIC RAG FRAMEWORK WITH PLATT-CALIBRATED CONFIDENCE SCORING FOR EXPLAINABLE CYBER THREAT INTELLIGENCE

**Author**: KOUSHIK R (Reg No: 21MIS0001)  
**Degree**: M.Tech. (Integrated) in Software Engineering  
**Department**: School of Computer Science and Engineering, Vellore Institute of Technology, Chennai  
**Date**: April, 2026  

---

## ABSTRACT

{abstract_text}

---

## CHAPTER 1: INTRODUCTION

### 1.1 Background & Domain Context
In modern enterprise security architectures, the rapid proliferation of Advanced Persistent Threats (APTs), zero-day exploits, and complex multi-vector cyber campaigns has fundamentally overwhelmed traditional Security Operations Center (SOC) monitoring tools. Security analysts receive tens of thousands of unstructured Cyber Threat Intelligence (CTI) documents daily, ranging from vendor threat bulletins, government advisories (e.g., CISA, NVD), open-source intelligence (OSINT) blogs, to structured STIX/TAXII feeds. Transforming these unstructured narratives into actionable, structured, and machine-readable threat graphs is paramount for automated threat hunting, attack path reconstruction, and vulnerability mitigation.

### 1.2 Key Limitations of Prior Work (L1-L3)
1. **L1: Performance Degradation in Unseen Entities**
2. **L2: Domain Complexities of Threat Text & Long-Tail Distribution**
3. **L3: Inflexibility in Attack Technique Identification & Version Drift**

---

## CHAPTER 2: LITERATURE REVIEW

### 2.1 Systematic Literature Review Overview
To establish the theoretical and empirical foundations of GraphRAG-Net, a systematic literature survey was conducted covering 20 Q1 journal papers published between 2024 and 2026 across top-tier publishers (IEEE Transactions, Elsevier, Springer Nature, ACM). The survey focuses strictly on structured CTI graphs, graph neural networks, relational reasoning, graph alignment, and graph-augmented retrieval.

### 2.2 Literature Review Taxonomy Table (20 Q1 Journal Papers, 2024-2026)

{md_table}

---

### 2.3 Detailed Review of Individual Benchmark Papers

"""

for p_title, p_name, p_body in tuples:
    clean_body = p_body.replace('"\n         "', '\n\n').replace('"\n         ', ' ')
    md_content += f"#### {p_title} Title: {p_name}\n\n{clean_body}\n\n"

md_content += """---

### 2.4 Chapter Summary of Literature Review
The systematic literature review of 20 Q1 journal papers (2024–2026) demonstrates that Cyber Threat Intelligence (CTI) processing has rapidly evolved from relational graph embeddings (SecKG2vec) and symbolic graph RAG (CyKG-RAG) to multi-agent RAG systems (AgCyRAG) and GNN provenance models (Provenancer). However, existing systems exhibit three fundamental limitations:
1. Missing GNN Topology Learning in RAG
2. Single-Channel Vector Context Drift
3. Uncalibrated Security Hallucinations

### 2.5 Identified Research Gap
Despite recent advancements, no existing CTI system successfully unites multi-ontology data fusion (STIX 2.1, ATT&CK, CAPEC, CWE, CVE), learned GNN structural topology (Hetero-GraphSAGE), Dual-Channel RRF retrieval (BM25 + GNN embeddings), and empirical Platt confidence calibration within a unified agentic RAG architecture. GraphRAG-Net fills this exact research gap.

---

## CHAPTER 4: PROPOSED ARCHITECTURE AND METHODOLOGY

### 4.1 GraphRAG-Net Architectural Overview
![Figure 4.1: End-to-End System Architecture of GraphRAG-Net Framework](file:///C:/Users/koush/.gemini/antigravity-ide/brain/9b01394d-6e00-4b65-8c18-7061d9b144a3/graphrag_net_architecture_1790092317869.jpg)

### 4.3 Stage 2 & 3: LLM Extraction & 3-Tier Entity Disambiguation
![Figure 4.2: Schema-Constrained LLM Extraction and 3-Tier Entity Disambiguation Pipeline](file:///C:/Users/koush/.gemini/antigravity-ide/brain/9b01394d-6e00-4b65-8c18-7061d9b144a3/graphrag_net_extraction_pipeline_1790092983622.jpg)

"""

with open(md_path, "w", encoding="utf-8") as f:
    f.write(md_content)

print("Updated Markdown artifact successfully with 20 Q1 papers table!")
