from app.services.pdf_extractor import extract_pdf
from app.services.hierarchy_parser import parse_hierarchy


def parsed(raw):
    elements, report = extract_pdf(raw)
    nodes, title = parse_hierarchy(elements)
    return nodes, title, elements, report


def test_missing_levels(pdfs):
    rows, _, _, _ = parsed(pdfs[0])
    by = {r["section_number"]: r for r in rows}
    n = by["2.1.1.1"]
    assert rows[n["parent_index"]]["section_number"] == "2.1"
    assert n["declared_level"] == 4 and n["effective_level"] == 3
    assert any("missing intermediate" in w for w in n["warnings"])


def test_physical_order_and_parent(pdfs):
    rows, _, _, _ = parsed(pdfs[0])
    by = {r["section_number"]: r for r in rows}
    assert by["3.4"]["order_index"] < by["3.3"]["order_index"]
    assert rows[by["3.4"]["parent_index"]]["section_number"] == "3"
    assert rows[by["3.3"]["parent_index"]]["section_number"] == "3"


def test_duplicate_titles(pdfs):
    rows, _, _, _ = parsed(pdfs[0])
    codes = [r for r in rows if r["heading"] == "Error Codes"]
    assert len(codes) == 2 and codes[0]["parent_index"] != codes[1]["parent_index"]


def test_lists_numeric_prose_references(pdfs):
    rows, _, _, _ = parsed(pdfs[0])
    n = next(r for r in rows if r["section_number"] == "3.3")
    assert len([e for e in n["elements"] if e["kind"] == "list_item"]) == 5
    assert "Sections 2.1 and 4.3" in n["body_text"]
    assert "60 seconds" in n["body_text"]
    assert not any(r["section_number"] == "1.5" for r in rows)


def test_multiline_table(pdfs):
    rows, _, _, _ = parsed(pdfs[0])
    n = next(r for r in rows if r["section_number"] == "4.2")
    table = next(e for e in n["elements"] if e["kind"] == "table")
    row = next(r for r in table["rows"] if r[0] == "E3")
    assert "2 seconds" in row[1] and "controlled pressure" in row[1]


def test_title_locations_accounting(pdfs):
    rows, title, elements, report = parsed(pdfs[0])
    assert title == "CardioTrack CT-200 Synthetic Reference Manual"
    assigned = [e["element_id"] for n in rows for e in n["elements"]]
    assert sorted(assigned) == [e["element_id"] for e in elements]
    assert len(assigned) == len(set(assigned))
    for n in rows:
        assert 1 <= n["page_start"] <= n["page_end"] <= report["page_count"]
    assert all(len(e["bbox"]) == 4 for e in elements)
