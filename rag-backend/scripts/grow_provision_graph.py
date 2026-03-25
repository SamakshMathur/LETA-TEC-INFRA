"""
Grow the Provision Graph with additional edges derived from:
1. Statute Index intra-topic relationships
2. Known Section-Rule implementation mappings
3. Cross-topic statutory cross-references
4. Hierarchical parent-child provision links
5. Co-citation mining from chunks (gap filler)

Run: python -m scripts.grow_provision_graph
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EDGES_PATH = Path("data/graph/edges.jsonl")
CHUNKS_PATH = Path("data/chunks/chunks.jsonl")
STATUTE_INDEX_PATH = Path("app/retrieval/statute_index.json")


def load_existing_edges():
    """Load existing edges and return set of (source, target) pairs."""
    edges = []
    pairs = set()
    if EDGES_PATH.exists():
        with open(EDGES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                edge = json.loads(line)
                edges.append(edge)
                pairs.add((edge["source"], edge["target"]))
                pairs.add((edge["target"], edge["source"]))
    return edges, pairs


def normalize_provision(text):
    """Normalize provision text to graph node ID format."""
    from app.ingestion.legal_parser import LegalParser
    text = text.strip()
    if "Section" in text:
        num = text.replace("Section", "").strip()
        # Handle IGST references
        if "IGST" in num:
            num = num.replace("IGST", "").strip()
            return f"IGST_SEC_{num.replace('(', '_').replace(')', '')}"
        return LegalParser.normalize_citation("section", num)
    elif "Rule" in text:
        num = text.replace("Rule", "").strip()
        return LegalParser.normalize_citation("rule", num)
    return None


def generate_intra_topic_edges(statute_index, existing_pairs):
    """Generate RELATED_TO edges between provisions listed under the same topic."""
    new_edges = []
    for topic, data in statute_index.items():
        # Collect all provisions for this topic
        provs = set()
        for p in data.get("primary", []):
            norm = normalize_provision(p)
            if norm:
                provs.add(norm)
        for sub_provs in data.get("subtopics", {}).values():
            for p in sub_provs:
                norm = normalize_provision(p)
                if norm:
                    provs.add(norm)

        # Create edges between all pairs
        provs = sorted(provs)
        for i in range(len(provs)):
            for j in range(i + 1, len(provs)):
                a, b = provs[i], provs[j]
                if (a, b) not in existing_pairs:
                    new_edges.append({
                        "source": a,
                        "target": b,
                        "relation": "RELATED_TO",
                        "weight": 5  # statutory index = strong signal
                    })
                    existing_pairs.add((a, b))
                    existing_pairs.add((b, a))

    return new_edges


def generate_section_rule_edges(existing_pairs):
    """Generate IMPLEMENTS edges between sections and their implementing rules."""
    # Known GST Section → Rule mappings (from CGST Act structure)
    section_rule_map = {
        # ITC
        "CGST_SEC_16": ["CGST_RUL_36", "CGST_RUL_36_4", "CGST_RUL_37"],
        "CGST_SEC_17": ["CGST_RUL_42", "CGST_RUL_43"],
        "CGST_SEC_17_2": ["CGST_RUL_42", "CGST_RUL_43"],
        "CGST_SEC_18": ["CGST_RUL_40", "CGST_RUL_41", "CGST_RUL_44"],
        "CGST_SEC_19": ["CGST_RUL_45"],
        "CGST_SEC_20": ["CGST_RUL_39"],
        # Registration
        "CGST_SEC_22": ["CGST_RUL_8", "CGST_RUL_9", "CGST_RUL_10"],
        "CGST_SEC_25": ["CGST_RUL_8", "CGST_RUL_9", "CGST_RUL_10", "CGST_RUL_11"],
        "CGST_SEC_28": ["CGST_RUL_19"],
        "CGST_SEC_29": ["CGST_RUL_20", "CGST_RUL_21", "CGST_RUL_22"],
        # Invoice
        "CGST_SEC_31": ["CGST_RUL_46", "CGST_RUL_46A", "CGST_RUL_47", "CGST_RUL_48", "CGST_RUL_54", "CGST_RUL_55"],
        "CGST_SEC_34": ["CGST_RUL_53"],
        # Returns
        "CGST_SEC_37": ["CGST_RUL_59"],
        "CGST_SEC_38": ["CGST_RUL_60"],
        "CGST_SEC_39": ["CGST_RUL_61"],
        "CGST_SEC_44": ["CGST_RUL_80"],
        # Payment
        "CGST_SEC_49": ["CGST_RUL_85", "CGST_RUL_86", "CGST_RUL_87", "CGST_RUL_88A"],
        "CGST_SEC_49A": ["CGST_RUL_88A"],
        "CGST_SEC_50": ["CGST_RUL_88B"],
        # Refund
        "CGST_SEC_54": ["CGST_RUL_89", "CGST_RUL_90", "CGST_RUL_91", "CGST_RUL_92", "CGST_RUL_96"],
        "CGST_SEC_55": ["CGST_RUL_93", "CGST_RUL_94", "CGST_RUL_95"],
        # Assessment
        "CGST_SEC_60": ["CGST_RUL_98"],
        "CGST_SEC_61": ["CGST_RUL_99"],
        "CGST_SEC_62": ["CGST_RUL_100"],
        # Audit
        "CGST_SEC_65": ["CGST_RUL_101"],
        "CGST_SEC_66": ["CGST_RUL_102"],
        "CGST_SEC_67": ["CGST_RUL_139", "CGST_RUL_140", "CGST_RUL_141"],
        # Demand & Recovery
        "CGST_SEC_73": ["CGST_RUL_142"],
        "CGST_SEC_74": ["CGST_RUL_142"],
        "CGST_SEC_79": ["CGST_RUL_145", "CGST_RUL_146", "CGST_RUL_147", "CGST_RUL_148", "CGST_RUL_149", "CGST_RUL_150", "CGST_RUL_151", "CGST_RUL_152", "CGST_RUL_153", "CGST_RUL_154", "CGST_RUL_155", "CGST_RUL_156", "CGST_RUL_157", "CGST_RUL_158", "CGST_RUL_159"],
        # Appeals
        "CGST_SEC_107": ["CGST_RUL_108", "CGST_RUL_109", "CGST_RUL_109A", "CGST_RUL_110"],
        "CGST_SEC_112": ["CGST_RUL_110", "CGST_RUL_111", "CGST_RUL_112"],
        # Penalty
        "CGST_SEC_122": ["CGST_RUL_162"],
        "CGST_SEC_129": ["CGST_RUL_138", "CGST_RUL_138A", "CGST_RUL_138B", "CGST_RUL_140"],
        "CGST_SEC_130": ["CGST_RUL_139", "CGST_RUL_140", "CGST_RUL_141"],
        # E-Way Bill
        "CGST_SEC_68": ["CGST_RUL_138", "CGST_RUL_138A", "CGST_RUL_138B", "CGST_RUL_138C", "CGST_RUL_138D", "CGST_RUL_138E"],
        # Job Work
        "CGST_SEC_143": ["CGST_RUL_45"],
        # TDS/TCS
        "CGST_SEC_51": ["CGST_RUL_66"],
        "CGST_SEC_52": ["CGST_RUL_67"],
        # Valuation
        "CGST_SEC_15": ["CGST_RUL_27", "CGST_RUL_28", "CGST_RUL_29", "CGST_RUL_30", "CGST_RUL_31", "CGST_RUL_32", "CGST_RUL_33", "CGST_RUL_34", "CGST_RUL_35"],
        # Accounts
        "CGST_SEC_35": ["CGST_RUL_56", "CGST_RUL_57", "CGST_RUL_58"],
        # Composition
        "CGST_SEC_10": ["CGST_RUL_3", "CGST_RUL_4", "CGST_RUL_5", "CGST_RUL_6", "CGST_RUL_7"],
        # Anti-Profiteering
        "CGST_SEC_171": ["CGST_RUL_126", "CGST_RUL_127", "CGST_RUL_128", "CGST_RUL_129", "CGST_RUL_130", "CGST_RUL_131", "CGST_RUL_132", "CGST_RUL_133", "CGST_RUL_134", "CGST_RUL_135", "CGST_RUL_136", "CGST_RUL_137"],
        # Time of Supply
        "CGST_SEC_12": ["CGST_RUL_1"],
        "CGST_SEC_13": ["CGST_RUL_1"],
    }

    new_edges = []
    for section, rules in section_rule_map.items():
        for rule in rules:
            if (section, rule) not in existing_pairs:
                new_edges.append({
                    "source": section,
                    "target": rule,
                    "relation": "CO_IMPLEMENTED",
                    "weight": 8  # strong structural link
                })
                existing_pairs.add((section, rule))
                existing_pairs.add((rule, section))

    return new_edges


def generate_cross_topic_edges(existing_pairs):
    """Generate edges for known cross-topic statutory relationships in GST."""
    cross_refs = [
        # ITC ↔ Refund (claiming refund of accumulated ITC)
        ("CGST_SEC_16", "CGST_SEC_54", "RELATED_TO", 10),
        ("CGST_SEC_17", "CGST_SEC_54", "RELATED_TO", 8),
        ("CGST_SEC_18", "CGST_SEC_54", "RELATED_TO", 6),
        # ITC ↔ Returns (ITC claimed in returns)
        ("CGST_SEC_16", "CGST_SEC_39", "RELATED_TO", 8),
        ("CGST_SEC_16_2", "CGST_SEC_37", "RELATED_TO", 7),
        ("CGST_SEC_16_4", "CGST_SEC_39", "RELATED_TO", 8),
        # ITC ↔ Payment (ITC utilization)
        ("CGST_SEC_16", "CGST_SEC_49", "RELATED_TO", 8),
        ("CGST_SEC_49", "CGST_RUL_86B", "RELATED_TO", 9),
        # Supply ↔ Valuation
        ("CGST_SEC_7", "CGST_SEC_15", "RELATED_TO", 9),
        ("CGST_SEC_9", "CGST_SEC_15", "RELATED_TO", 9),
        # Supply ↔ Time of Supply
        ("CGST_SEC_7", "CGST_SEC_12", "RELATED_TO", 7),
        ("CGST_SEC_7", "CGST_SEC_13", "RELATED_TO", 7),
        ("CGST_SEC_9", "CGST_SEC_12", "RELATED_TO", 8),
        ("CGST_SEC_9", "CGST_SEC_13", "RELATED_TO", 8),
        # Registration ↔ Penalty
        ("CGST_SEC_22", "CGST_SEC_122", "RELATED_TO", 5),
        ("CGST_SEC_24", "CGST_SEC_122", "RELATED_TO", 5),
        # Invoice ↔ ITC (invoice is prerequisite for ITC)
        ("CGST_SEC_31", "CGST_SEC_16", "RELATED_TO", 9),
        ("CGST_SEC_31", "CGST_SEC_16_2", "RELATED_TO", 9),
        # Returns ↔ Penalty
        ("CGST_SEC_37", "CGST_SEC_47", "RELATED_TO", 8),
        ("CGST_SEC_39", "CGST_SEC_47", "RELATED_TO", 8),
        ("CGST_SEC_44", "CGST_SEC_47", "RELATED_TO", 7),
        # Demand ↔ Appeals
        ("CGST_SEC_73", "CGST_SEC_107", "RELATED_TO", 10),
        ("CGST_SEC_74", "CGST_SEC_107", "RELATED_TO", 10),
        ("CGST_SEC_73", "CGST_SEC_112", "RELATED_TO", 8),
        ("CGST_SEC_74", "CGST_SEC_112", "RELATED_TO", 8),
        ("CGST_SEC_75", "CGST_SEC_107", "RELATED_TO", 9),
        # Demand ↔ Interest
        ("CGST_SEC_73", "CGST_SEC_50", "RELATED_TO", 8),
        ("CGST_SEC_74", "CGST_SEC_50", "RELATED_TO", 8),
        # Refund ↔ Export
        ("CGST_SEC_54", "CGST_RUL_96", "RELATED_TO", 10),
        ("CGST_SEC_54", "CGST_RUL_96A", "RELATED_TO", 9),
        # Penalty ↔ Appeals
        ("CGST_SEC_122", "CGST_SEC_107", "RELATED_TO", 8),
        ("CGST_SEC_129", "CGST_SEC_107", "RELATED_TO", 9),
        ("CGST_SEC_130", "CGST_SEC_107", "RELATED_TO", 8),
        # Audit ↔ Demand
        ("CGST_SEC_65", "CGST_SEC_73", "RELATED_TO", 7),
        ("CGST_SEC_65", "CGST_SEC_74", "RELATED_TO", 7),
        ("CGST_SEC_66", "CGST_SEC_73", "RELATED_TO", 7),
        ("CGST_SEC_67", "CGST_SEC_74", "RELATED_TO", 8),
        # E-Way Bill ↔ Penalty
        ("CGST_RUL_138", "CGST_SEC_129", "RELATED_TO", 10),
        ("CGST_RUL_138", "CGST_SEC_130", "RELATED_TO", 8),
        # RCM ↔ ITC
        ("CGST_SEC_9_3", "CGST_SEC_16", "RELATED_TO", 8),
        ("CGST_SEC_9_4", "CGST_SEC_16", "RELATED_TO", 8),
        # Composition ↔ Registration
        ("CGST_SEC_10", "CGST_SEC_22", "RELATED_TO", 7),
        ("CGST_SEC_10", "CGST_SEC_25", "RELATED_TO", 7),
        # TDS/TCS ↔ Payment
        ("CGST_SEC_51", "CGST_SEC_49", "RELATED_TO", 7),
        ("CGST_SEC_52", "CGST_SEC_49", "RELATED_TO", 7),
        # Assessment ↔ Demand
        ("CGST_SEC_62", "CGST_SEC_73", "RELATED_TO", 8),
        ("CGST_SEC_63", "CGST_SEC_74", "RELATED_TO", 8),
        ("CGST_SEC_61", "CGST_SEC_73", "RELATED_TO", 7),
        # Provisional Assessment ↔ Interest
        ("CGST_SEC_60", "CGST_SEC_50", "RELATED_TO", 7),
    ]

    new_edges = []
    for src, tgt, rel, weight in cross_refs:
        if (src, tgt) not in existing_pairs:
            new_edges.append({
                "source": src,
                "target": tgt,
                "relation": rel,
                "weight": weight
            })
            existing_pairs.add((src, tgt))
            existing_pairs.add((tgt, src))

    return new_edges


def generate_hierarchical_edges(existing_pairs):
    """Generate parent-child edges for section/rule subsections."""
    # Collect all provisions from chunks
    all_provisions = set()
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            cits = chunk.get("metadata", {}).get("citations", [])
            for c in cits:
                if "_SEC_" in c or "_RUL_" in c:
                    all_provisions.add(c)

    # Also include provisions already in the graph
    if EDGES_PATH.exists():
        with open(EDGES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                edge = json.loads(line)
                all_provisions.add(edge["source"])
                all_provisions.add(edge["target"])

    new_edges = []
    for prov in all_provisions:
        # Find parent: CGST_SEC_17_5 → parent is CGST_SEC_17
        parts = prov.split("_")
        if len(parts) > 3:  # Has sub-parts (e.g., _SEC_17_5 or _RUL_42_1)
            parent = "_".join(parts[:3])
            if parent in all_provisions and parent != prov:
                if (parent, prov) not in existing_pairs:
                    new_edges.append({
                        "source": parent,
                        "target": prov,
                        "relation": "RELATED_TO",
                        "weight": 15  # very strong — same section
                    })
                    existing_pairs.add((parent, prov))
                    existing_pairs.add((prov, parent))

    return new_edges


def main():
    print("=== Provision Graph Growth ===")
    print()

    # Load existing
    existing_edges, existing_pairs = load_existing_edges()
    print(f"Existing edges: {len(existing_edges)}")

    # Load statute index
    with open(STATUTE_INDEX_PATH, "r") as f:
        statute_index = json.load(f)

    # Generate new edges from each source
    intra_topic = generate_intra_topic_edges(statute_index, existing_pairs)
    print(f"New intra-topic edges: {len(intra_topic)}")

    section_rule = generate_section_rule_edges(existing_pairs)
    print(f"New section-rule edges: {len(section_rule)}")

    cross_topic = generate_cross_topic_edges(existing_pairs)
    print(f"New cross-topic edges: {len(cross_topic)}")

    hierarchical = generate_hierarchical_edges(existing_pairs)
    print(f"New hierarchical edges: {len(hierarchical)}")

    all_new = intra_topic + section_rule + cross_topic + hierarchical
    print(f"\nTotal new edges: {len(all_new)}")

    if not all_new:
        print("No new edges to add.")
        return

    # Append to edges.jsonl
    with open(EDGES_PATH, "a", encoding="utf-8") as f:
        for edge in all_new:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")

    total = len(existing_edges) + len(all_new)
    print(f"\nGraph grown: {len(existing_edges)} -> {total} edges (+{len(all_new)})")
    print("Done!")


if __name__ == "__main__":
    main()
