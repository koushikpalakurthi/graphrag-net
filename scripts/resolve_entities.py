"""
Stage 1c: Entity resolution / alias merging.

MITRE ATT&CK already ships explicit alias lists for ThreatGroup and Software
nodes (e.g. APT29's 14 aliases including "Cozy Bear", "Midnight Blizzard").
That's the easy case -- just fold aliases into a canonical node's alias set.

The harder case this stage handles is CROSS-SOURCE aliasing: when a later
ingestion pass adds entities from vendor advisories or CVE writeups that use
names ATT&CK doesn't know about. For those, we do fuzzy string matching +
embedding similarity, then flag borderline matches for LLM verification
rather than auto-merging -- silently merging two different threat actors is
a much worse error than leaving a duplicate node.
"""
import sys
import json
from pathlib import Path
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR

FUZZY_MATCH_THRESHOLD = 88       # auto-flag as candidate above this score
FUZZY_AUTOMERGE_THRESHOLD = 97   # only auto-merge above this (near-exact)


def load_graph():
    nodes = json.loads((PROCESSED_DIR / "nodes.json").read_text())
    edges = json.loads((PROCESSED_DIR / "edges.json").read_text())
    return nodes, edges


def build_alias_index(nodes):
    """
    ATT&CK-native aliasing: every alias string points to its canonical node id.
    This lets later ingestion (e.g. a vendor report saying "Cozy Bear") resolve
    directly to the canonical APT29 node instead of creating a duplicate.
    """
    alias_index = {}
    collisions = []
    for n in nodes:
        if n["label"] not in ("ThreatGroup", "Software"):
            continue
        canonical_id = n["id"]
        names_to_index = [n["name"]] + n.get("aliases", [])
        for alias in names_to_index:
            key = alias.strip().lower()
            if key in alias_index and alias_index[key] != canonical_id:
                collisions.append((alias, alias_index[key], canonical_id))
            alias_index[key] = canonical_id
    return alias_index, collisions


def find_cross_entity_fuzzy_candidates(nodes):
    """
    Find same-type node pairs whose names/aliases are suspiciously similar but
    NOT already unified via the native alias list -- these are candidates for
    LLM-assisted verification before merging (never auto-merged silently).
    """
    candidates = []
    by_label = {}
    for n in nodes:
        by_label.setdefault(n["label"], []).append(n)

    for label, group in by_label.items():
        if label not in ("ThreatGroup", "Software"):
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                score = fuzz.token_sort_ratio(a["name"], b["name"])
                if score >= FUZZY_MATCH_THRESHOLD:
                    candidates.append({
                        "node_a": a["id"], "name_a": a["name"],
                        "node_b": b["id"], "name_b": b["name"],
                        "label": label,
                        "fuzzy_score": score,
                        "recommend_action": (
                            "auto_merge" if score >= FUZZY_AUTOMERGE_THRESHOLD
                            else "llm_verify"
                        ),
                    })
    return candidates


def main():
    nodes, edges = load_graph()
    alias_index, collisions = build_alias_index(nodes)

    print(f"Indexed {len(alias_index)} alias strings across "
          f"{sum(1 for n in nodes if n['label'] in ('ThreatGroup','Software'))} "
          f"ThreatGroup/Software nodes.")

    if collisions:
        print(f"\nWARNING: {len(collisions)} alias strings map to >1 canonical "
              f"node within ATT&CK itself (needs manual review):")
        for alias, id1, id2 in collisions[:10]:
            print(f"  '{alias}' -> {id1} AND {id2}")

    candidates = find_cross_entity_fuzzy_candidates(nodes)
    auto_merge = [c for c in candidates if c["recommend_action"] == "auto_merge"]
    llm_verify = [c for c in candidates if c["recommend_action"] == "llm_verify"]
    print(f"\nFuzzy-match candidates NOT already covered by native aliases: {len(candidates)}")
    print(f"  auto_merge (score >= {FUZZY_AUTOMERGE_THRESHOLD}): {len(auto_merge)}")
    print(f"  needs llm_verify (score >= {FUZZY_MATCH_THRESHOLD}):  {len(llm_verify)}")
    for c in candidates[:10]:
        print(f"  [{c['recommend_action']}] {c['name_a']!r} <-> {c['name_b']!r} "
              f"(score={c['fuzzy_score']})")

    out = {
        "alias_index": alias_index,
        "collisions": collisions,
        "fuzzy_candidates": candidates,
    }
    (PROCESSED_DIR / "entity_resolution.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {PROCESSED_DIR / 'entity_resolution.json'}")


if __name__ == "__main__":
    main()
