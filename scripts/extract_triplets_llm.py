"""
Stage 1b (unstructured source): LLM-assisted entity-relation-entity triplet
extraction from raw advisory text, following CTINexus's approach.

Runs on Groq (https://console.groq.com), not Anthropic -- Groq's free tier
requires no credit card, which matters since this script makes one API call
per advisory and is meant to be run repeatedly during development.

IMPORTANT -- this script was written and syntax-checked, but NOT run against
a live API call: api.groq.com isn't reachable from the sandbox this project
was built in (network allowlist), and no API key was available either way.
You are the first person to actually run this against a real model. See the
bottom of this file for a `--self-test` mode that exercises the parsing/
validation logic against a hand-written example response, so you can
sanity-check the code path independent of the live API call.

Free tier rate limits (check https://console.groq.com/settings/limits for
current numbers -- these change): as of this writing, llama-3.3-70b-versatile
allows roughly 30 requests/minute. main() paces requests accordingly; if you
hit a 429 rate-limit error anyway, increase RATE_LIMIT_DELAY_SECONDS below.

Design:
- Schema-constrained prompt: the model is given the exact entity types and
  relation types already used in the Neo4j graph (see ENTITY_TYPES /
  RELATION_TYPES below), and told to emit ONLY those types. This keeps
  extracted triplets compatible with the existing graph schema instead of
  inventing new ad-hoc types per document.
- Groq's JSON mode (response_format={"type": "json_object"}) guarantees
  syntactically valid JSON back -- removes one failure mode entirely
  compared to hoping the model follows a "respond with only JSON" instruction.
- Each extracted entity is tagged with whether its name plausibly matches
  something already in the graph (e.g. "APT28", "CWE-79") -- this is a
  hint for align_extracted_entities.py, not a guarantee; real resolution
  happens there via fuzzy + embedding matching, same pattern as
  resolve_entities.py in Stage 1.
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DIR, PROCESSED_DIR, GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL

# Constrained to types that already exist as node/edge labels in the graph
# built in Stage 1 (see parse_stix_to_graph.py / parse_capec_to_graph.py /
# parse_cwe_to_graph.py), plus "Vulnerability" which is new -- CVEs aren't
# loaded yet, so this is the first source that will populate that type.
ENTITY_TYPES = [
    "ThreatGroup", "Technique", "Software", "Mitigation",
    "Weakness", "AttackPattern", "Vulnerability", "Campaign",
]
RELATION_TYPES = [
    "USES",            # ThreatGroup/Campaign USES Technique/Software
    "EXPLOITS",        # Technique/AttackPattern EXPLOITS Vulnerability/Weakness
    "MITIGATES",       # Mitigation MITIGATES Technique/Vulnerability
    "ATTRIBUTED_TO",   # Campaign ATTRIBUTED_TO ThreatGroup
    "TARGETS",         # ThreatGroup/Campaign TARGETS Software
]

EXTRACTION_SYSTEM_PROMPT = f"""You are a cybersecurity threat intelligence analyst extracting structured data from advisory text.

Extract entity-relation-entity triplets using ONLY these entity types:
{json.dumps(ENTITY_TYPES)}

Use ONLY these relation types:
{json.dumps(RELATION_TYPES)}

For each entity, include:
- "name": the entity's name as it appears in the text (use canonical/well-known names where possible, e.g. "APT28" not "the Russian threat actor")
- "type": one of the entity types above
- "known_id_hint": if the text mentions a known identifier (CVE-ID, CWE-ID, ATT&CK technique ID like T1566), include it here, else null

For each relation, include source entity name, relation type, and target entity name -- both entities must appear in your entities list.

Respond with ONLY valid JSON, no markdown fences, no preamble, in this exact shape:
{{
  "entities": [{{"name": "...", "type": "...", "known_id_hint": null}}],
  "relations": [{{"source": "...", "relation": "...", "target": "..."}}]
}}

If the text contains no extractable entities, respond with {{"entities": [], "relations": []}}.
Do not invent entities or relations not supported by the text."""


def get_client():
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("pip install openai   (used as the client library -- "
                           "Groq's API is OpenAI-compatible, no OpenAI account needed)")
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com/keys "
            "and add it to your .env file (see .env.example) before running this script."
        )
    return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


def extract_triplets(client, text: str, max_retries: int = 2) -> dict:
    """Call the LLM once per advisory, with one retry on malformed JSON."""
    if not text.strip():
        return {"entities": [], "relations": []}

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=2000,
                response_format={"type": "json_object"},  # Groq's JSON mode -- guarantees parseable JSON
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": text[:8000]},  # cap input length
                ],
            )
            raw = response.choices[0].message.content.strip()
            # Defensive strip in case the model wraps in ```json fences anyway
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)

            # Validate shape and drop anything outside our schema rather than
            # silently trusting the model
            entities = [e for e in parsed.get("entities", []) if e.get("type") in ENTITY_TYPES]
            valid_names = {e["name"] for e in entities}
            relations = [
                r for r in parsed.get("relations", [])
                if r.get("relation") in RELATION_TYPES
                and r.get("source") in valid_names
                and r.get("target") in valid_names
            ]
            return {"entities": entities, "relations": relations}

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1)
                continue

    print(f"  WARNING: extraction failed after {max_retries + 1} attempts: {last_error}")
    return {"entities": [], "relations": []}


RATE_LIMIT_DELAY_SECONDS = 2.1  # ~28 req/min, just under Groq's free-tier ~30/min limit


def load_existing_results(out_path):
    """Resume support: load any already-extracted results from a previous
    (possibly interrupted) run, so re-running main() doesn't redo work or
    burn tokens re-processing advisories already done."""
    if out_path.exists():
        existing = json.loads(out_path.read_text())
        done_ids = {r["source_id"] for r in existing}
        return existing, done_ids
    return [], set()


def main():
    advisories_path = RAW_DIR / "github_advisories.json"
    if not advisories_path.exists():
        raise FileNotFoundError(f"{advisories_path} not found -- run download_advisories.py first.")

    advisories = json.loads(advisories_path.read_text())
    out_path = PROCESSED_DIR / "llm_extracted_triplets.json"
    results, done_ids = load_existing_results(out_path)

    if done_ids:
        print(f"Resuming: {len(done_ids)} advisories already extracted in a previous run, skipping those.")

    client = get_client()

    try:
        import openai
    except ImportError:
        openai = None

    for i, adv in enumerate(advisories, 1):
        ghsa_id = adv.get("ghsa_id")
        if ghsa_id in done_ids:
            continue

        text = f"{adv.get('summary','')}\n\n{adv.get('description','')}".strip()
        print(f"[{i}/{len(advisories)}] Extracting from {ghsa_id}...")

        try:
            extracted = extract_triplets(client, text)
        except Exception as e:
            is_rate_limit = openai and isinstance(e, openai.RateLimitError)
            if is_rate_limit:
                print(f"\nHit Groq's rate limit: {e}")
                print(f"Saving {len(results)} results extracted so far to {out_path} "
                      f"and stopping cleanly.")
                print("Re-run this same script later (after the limit resets) -- "
                      "it will automatically skip everything already done and "
                      "pick up where it left off.")
            else:
                print(f"\nUnexpected error on {ghsa_id}: {e}")
                print(f"Saving {len(results)} results extracted so far before exiting.")
            out_path.write_text(json.dumps(results, indent=2))
            return

        results.append({
            "source_id": ghsa_id,
            "source_cve": adv.get("cve_id"),
            "entities": extracted["entities"],
            "relations": extracted["relations"],
        })
        print(f"    -> {len(extracted['entities'])} entities, {len(extracted['relations'])} relations")

        # Checkpoint after every advisory, not just at the end -- a crash or
        # rate limit mid-run loses at most the single in-flight call, never
        # previously-completed work.
        out_path.write_text(json.dumps(results, indent=2))
        time.sleep(RATE_LIMIT_DELAY_SECONDS)

    total_entities = sum(len(r["entities"]) for r in results)
    total_relations = sum(len(r["relations"]) for r in results)
    print(f"\nExtracted {total_entities} entities, {total_relations} relations "
          f"from {len(advisories)} advisories")
    print(f"Wrote {out_path}")


def self_test():
    """
    Exercises the parsing/validation path against a hand-written example
    response, WITHOUT calling the live API -- lets you confirm the JSON
    validation and schema-filtering logic works before spending API calls.
    """
    example_text = """CVE-2024-99999: A critical vulnerability was discovered in ExampleCorp's
    VPN client. The threat actor APT28 has been observed exploiting this vulnerability
    (related to CWE-787: Out-of-bounds Write) to gain initial access. Organizations
    should apply the vendor patch as mitigation."""

    fake_model_response = json.dumps({
        "entities": [
            {"name": "APT28", "type": "ThreatGroup", "known_id_hint": None},
            {"name": "CVE-2024-99999", "type": "Vulnerability", "known_id_hint": "CVE-2024-99999"},
            {"name": "CWE-787", "type": "Weakness", "known_id_hint": "CWE-787"},
            {"name": "Vendor Patch", "type": "Mitigation", "known_id_hint": None},
        ],
        "relations": [
            {"source": "APT28", "relation": "EXPLOITS", "target": "CVE-2024-99999"},
            {"source": "CVE-2024-99999", "relation": "EXPLOITS", "target": "CWE-787"},  # intentionally odd, tests schema filter doesn't crash
            {"source": "Vendor Patch", "relation": "MITIGATES", "target": "CVE-2024-99999"},
        ],
    })

    parsed = json.loads(fake_model_response)
    entities = [e for e in parsed.get("entities", []) if e.get("type") in ENTITY_TYPES]
    valid_names = {e["name"] for e in entities}
    relations = [
        r for r in parsed.get("relations", [])
        if r.get("relation") in RELATION_TYPES
        and r.get("source") in valid_names
        and r.get("target") in valid_names
    ]

    print("Self-test (no live API call):")
    print(f"  Input text: {example_text[:80]}...")
    print(f"  Parsed entities: {len(entities)}")
    for e in entities:
        print(f"    - {e['name']} ({e['type']}) hint={e['known_id_hint']}")
    print(f"  Parsed relations: {len(relations)}")
    for r in relations:
        print(f"    - {r['source']} -[{r['relation']}]-> {r['target']}")
    print("\nIf this looks right, the parsing/validation logic is sound.")
    print("Run without --self-test (and with GROQ_API_KEY set) for the real thing.")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        main()