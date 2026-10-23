import argparse
import json
from pathlib import Path
from app.services.pdf_extractor import extract_pdf
from app.services.hierarchy_parser import parse_hierarchy
from app.services.canonical import content_hash


def validate(raw: bytes, reference=False):
    elements, report = extract_pdf(raw)
    nodes, title = parse_hierarchy(elements)
    checks = []

    def check(name, condition):
        checks.append({"check": name, "status": "pass" if condition else "fail"})

    assigned = [e["element_id"] for n in nodes for e in n["elements"]]
    expected = [e["element_id"] for e in elements if e["kind"] != "repeated_header"]
    check(
        "every nonsuppressed element assigned exactly once",
        sorted(assigned) == sorted(expected) and len(assigned) == len(set(assigned)),
    )
    check(
        "valid parents, no forward/circular references",
        all(
            n["parent_index"] is None or 0 <= n["parent_index"] < n["order_index"]
            for n in nodes
        ),
    )
    check(
        "source page ranges valid",
        all(
            1 <= n["page_start"] <= n["page_end"] <= report["page_count"] for n in nodes
        ),
    )
    check(
        "hashes deterministic",
        all(
            n["content_hash"]
            == content_hash(
                n["heading"], [e for e in n["elements"] if e["kind"] != "heading"]
            )
            for n in nodes
        ),
    )
    # Check that each non-heading text survives in body, modulo whitespace.
    from app.services.canonical import normalize

    check(
        "body text retained",
        all(
            normalize(e["text"]) in normalize(n["body_text"])
            for n in nodes
            for e in n["elements"]
            if e["kind"] != "heading"
        ),
    )
    if reference:
        by = {n["section_number"]: n for n in nodes}
        check(
            "REFERENCE CONTENT: expected top sections",
            set(["1", "2", "3", "4", "5", "7", "8"]).issubset(by),
        )
        check(
            "REFERENCE CONTENT: missing-level parent",
            "2.1.1.1" in by
            and nodes[by["2.1.1.1"]["parent_index"]]["section_number"] == "2.1",
        )
        check(
            "REFERENCE CONTENT: physical section order",
            by.get("3.4", {}).get("order_index", 999)
            < by.get("3.3", {}).get("order_index", -1),
        )
        check(
            "REFERENCE CONTENT: duplicate titles distinct",
            len([n for n in nodes if n["heading"] == "Error Codes"]) == 2,
        )
        table = by.get("4.2", {}).get("elements", [])
        check(
            "REFERENCE CONTENT: structured E1–E5 rows",
            all(
                any(
                    e["kind"] == "table" and any(r[0] == code for r in e["rows"])
                    for e in table
                )
                for code in ["E1", "E2", "E3", "E4", "E5"]
            ),
        )
    warnings = report["warnings"] + [w for n in nodes for w in n["warnings"]]
    return {
        "title": title,
        "checks": checks,
        "warnings": warnings,
        "visual_review": "not performed by this script",
        "reference_checks_are_not_completeness_proof": True,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pdf", type=Path)
    p.add_argument("--reference-checks", action="store_true")
    p.add_argument(
        "--output", type=Path, default=Path("generated/hierarchy_validation.json")
    )
    args = p.parse_args()
    result = validate(args.pdf.read_bytes(), args.reference_checks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    args.output.with_suffix(".md").write_text(
        "\n".join(
            [f"{c['status'].upper()}: {c['check']}" for c in result["checks"]]
            + ["WARNING: " + w for w in result["warnings"]]
            + ["Visual comparison remains a separate review step."]
        )
        + "\n"
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(any(c["status"] == "fail" for c in result["checks"]))


if __name__ == "__main__":
    main()
