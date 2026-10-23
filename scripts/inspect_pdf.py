"""Inspect actual PDFs; synthetic reports explicitly retain their origin."""

import argparse
import json
from pathlib import Path
from app.services.pdf_extractor import extract_pdf
from app.services.hierarchy_parser import parse_hierarchy


def inspect(path: Path, output: Path, synthetic=False):
    elements, report = extract_pdf(path.read_bytes())
    nodes, title = parse_hierarchy(elements)
    report.update(
        source=str(path),
        synthetic_fixture=synthetic,
        title=title,
        candidate_headings=[
            {
                "number": n["section_number"],
                "heading": n["heading"],
                "pages": [n["page_start"], n["page_end"]],
            }
            for n in nodes
        ],
        elements=elements,
        structural_warnings=[w for n in nodes for w in n["warnings"]],
    )
    output.mkdir(parents=True, exist_ok=True)
    prefix = output / path.stem
    prefix.with_suffix(".inspection.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    lines = [
        f"# Inspection: {path.name}",
        f"Synthetic fixture: {synthetic}",
        f"Pages: {report['page_count']}",
        f"Title: {title}",
        "Observed extracted headings:",
    ]
    lines += [
        f"- {n['section_number']} {n['heading']} (pages {n['page_start']}–{n['page_end']})"
        for n in nodes
    ]
    lines += ["Warnings:"] + [
        f"- {w}" for w in report["warnings"] + report["structural_warnings"]
    ]
    lines += [
        "Completeness is unverified until compared visually with the PDF. Reference expectations are not independent extraction evidence."
    ]
    prefix.with_suffix(".inspection.md").write_text("\n".join(lines) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("generated"))
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    report = inspect(args.pdf, args.output, args.synthetic)
    print(
        json.dumps(
            {
                "pages": report["page_count"],
                "headings": len(report["candidate_headings"]),
                "warnings": report["warnings"],
            }
        )
    )


if __name__ == "__main__":
    main()
