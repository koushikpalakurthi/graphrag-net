"""
Stage 1d: Load the parsed, resolved graph into Neo4j.

Run after (ATT&CK):     download_attack.py -> parse_stix_to_graph.py -> resolve_entities.py
Run after (CAPEC):      download_capec.py -> parse_capec_to_graph.py
Run after (CWE):        download_cwe.py -> parse_cwe_to_graph.py
Run after (unstructured, optional): download_advisories.py -> extract_triplets_llm.py
                         -> align_extracted_entities.py -> predict_long_distance_relations.py
Requires: `docker compose up -d` (see docker-compose.yml) so Neo4j is reachable
at NEO4J_URI.

This loader is idempotent and additive -- run it again after adding a new
source and it will MERGE into the existing graph rather than duplicating it.
Load order matters: ATT&CK first, then CAPEC (cross-links target ATT&CK
nodes), then CWE (enriches CAPEC's placeholder Weakness nodes), then the
unstructured-extraction outputs last (they may reference nodes from any of
the above, plus introduce new ones like Vulnerability/CVE nodes).
"""
import sys
import json
from pathlib import Path
from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, PROCESSED_DIR

# All node labels we load -- used to create uniqueness constraints up front.
NODE_LABELS = [
    "Technique", "Tactic", "ThreatGroup", "Software",
    "Mitigation", "Campaign", "DataSource", "DataComponent",
    "AttackPattern", "Weakness", "Vulnerability",
]

# (nodes_file, edges_file) pairs to load, in order. CAPEC is loaded after
# ATT&CK because its MAPS_TO_TECHNIQUE edges reference ATT&CK Technique nodes.
# CWE is loaded next so it *enriches* the placeholder Weakness nodes CAPEC
# already created (same id format, e.g. "CWE-276") rather than creating
# duplicates -- MERGE-by-id fills in the extra fields on the existing node.
# The unstructured-extraction outputs load last: llm_extracted_nodes.json
# introduces genuinely new entities (e.g. CVEs) not present in any structured
# source, and inferred_edges.json is edges-only (its nodes already exist by
# this point, from either structured or LLM-extracted sources) -- passing
# None as its nodes file tells the loader below to skip node loading for it.
SOURCE_FILES = [
    ("nodes.json", "edges.json"),
    ("capec_nodes.json", "capec_edges.json"),
    ("cwe_nodes.json", "cwe_edges.json"),
    ("cve_nodes.json", "cve_edges.json"),
    ("llm_extracted_nodes.json", "llm_extracted_edges.json"),
    (None, "inferred_edges.json"),
]


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def create_constraints(tx):
    for label in NODE_LABELS:
        tx.run(
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
            f"REQUIRE n.id IS UNIQUE"
        )


def load_nodes(tx, nodes):
    # Batched UNWIND write -- far faster than one MERGE per node for ~2k nodes,
    # and scales fine to the 100k+ node graphs later ingestion passes will add.
    # Every node dict is normalized to a common key set before batching so a
    # single Cypher SET clause works regardless of source-specific extra
    # fields (e.g. CWE's abstraction/status/mitigations) -- missing fields
    # are filled with None, which SET treats as "leave unset" only on first
    # MERGE; on a later enrichment pass (e.g. CWE filling in a CAPEC
    # placeholder) the real values simply overwrite the earlier None/empty ones.
    common_fields = [
        "attack_id", "name", "description", "aliases", "platforms", "source",
        "abstraction", "status", "mitigations", "severity", "likelihood",
    ]
    by_label = {}
    for n in nodes:
        row = {k: n.get(k) for k in common_fields}
        row["id"] = n["id"]
        by_label.setdefault(n["label"], []).append(row)

    for label, batch in by_label.items():
        tx.run(
            f"""
            UNWIND $batch AS row
            MERGE (n:{label} {{id: row.id}})
            SET n += apoc.map.removeKey(
                apoc.map.clean(row, [], [null]), 'id'
            )
            """,
            batch=batch,
        )
        print(f"  Loaded {len(batch)} :{label} nodes")


def load_edges(tx, edges):
    by_label = {}
    for e in edges:
        by_label.setdefault(e["label"], []).append(e)

    for label, batch in by_label.items():
        tx.run(
            f"""
            UNWIND $batch AS row
            MATCH (a {{id: row.source_id}})
            MATCH (b {{id: row.target_id}})
            MERGE (a)-[r:{label}]->(b)
            SET r.description = row.description,
                r.source      = row.source,
                r.confidence  = row.confidence
            """,
            batch=batch,
        )
        print(f"  Loaded {len(batch)} :{label} edges")


def main():
    driver = get_driver()
    try:
        driver.verify_connectivity()
    except Exception as e:
        print(f"Could not connect to Neo4j at {NEO4J_URI}: {e}")
        print("Start it with: docker compose up -d   (from the project root)")
        sys.exit(1)

    with driver.session() as session:
        print("Creating uniqueness constraints...")
        session.execute_write(create_constraints)

        for nodes_file, edges_file in SOURCE_FILES:
            edges_path = PROCESSED_DIR / edges_file

            if nodes_file is None:
                # Edges-only source (e.g. inferred_edges.json) -- its nodes
                # were already created by an earlier source in this loop.
                if not edges_path.exists():
                    print(f"Skipping {edges_file} (not found -- optional, "
                          f"only produced by the unstructured-extraction pipeline)")
                    continue
                edges = json.loads(edges_path.read_text())
                print(f"\n[{edges_file}] Loading {len(edges)} edges (no new nodes)...")
                session.execute_write(load_edges, edges)
                continue

            nodes_path = PROCESSED_DIR / nodes_file
            if not nodes_path.exists():
                print(f"Skipping {nodes_file} (not found -- run its parser script first; "
                      f"this is expected/optional for the unstructured-extraction sources)")
                continue

            nodes = json.loads(nodes_path.read_text())
            edges = json.loads(edges_path.read_text())

            print(f"\n[{nodes_file}] Loading {len(nodes)} nodes...")
            session.execute_write(load_nodes, nodes)

            print(f"[{edges_file}] Loading {len(edges)} edges...")
            session.execute_write(load_edges, edges)

    driver.close()
    print("\nDone. Verify in the Neo4j browser (http://localhost:7474) with e.g.:")
    print('  MATCH (t:ThreatGroup {name: "APT29"})-[:USES]->(x) RETURN t, x LIMIT 25')
    print("  MATCH (c:AttackPattern)-[:MAPS_TO_TECHNIQUE]->(t:Technique) RETURN c, t LIMIT 25")


if __name__ == "__main__":
    main()
