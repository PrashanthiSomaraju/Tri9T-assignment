"""Layout extraction; warnings are evidence of uncertainty, never invented text."""
from collections import Counter
from io import BytesIO
import re
import fitz
import pytesseract
from PIL import Image


def _element(kind, text, page, bbox, **extra):
    return dict(kind=kind, text=text, page=page, bbox=list(bbox), **extra)


def _ocr(page, number, warnings, clip=None):
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
    image = Image.open(BytesIO(pix.tobytes("png")))
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6", timeout=45)
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError, RuntimeError) as exc:
        warnings.append(f"page {number}: OCR unavailable/failed ({type(exc).__name__}); content requires review")
        return []
    groups = {}
    ox, oy = (clip.x0, clip.y0) if clip else (0, 0)
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        groups.setdefault(key, []).append(i)
    result = []
    for indexes in groups.values():
        text = " ".join(data['text'][i] for i in indexes)
        confidence = sum(float(data['conf'][i]) for i in indexes) / len(indexes)
        x0 = min(data['left'][i] for i in indexes)/2 + ox
        y0 = min(data['top'][i] for i in indexes)/2 + oy
        x1 = max(data['left'][i]+data['width'][i] for i in indexes)/2 + ox
        y1 = max(data['top'][i]+data['height'][i] for i in indexes)/2 + oy
        result.append(_element("unclassified", text, number, (x0,y0,x1,y1), source="ocr", confidence=confidence, font_size=0, bold=False, spans=[]))
        if confidence < 75:
            warnings.append(f"page {number}: low OCR confidence {confidence:.1f}: {text[:60]}")
    return result


def extract_pdf(raw: bytes) -> tuple[list[dict], dict]:
    elements, warnings, pages = [], [], []
    with fitz.open(stream=raw, filetype="pdf") as pdf:
        if pdf.needs_pass:
            raise ValueError("Encrypted PDF requires an unlocked copy")
        if len(pdf) > 200:
            raise ValueError("PDF exceeds 200-page synchronous ingestion limit")
        for number, page in enumerate(pdf, 1):
            layout = page.get_text("dict", sort=True)
            native = page.get_text().strip()
            corrupted = native.count('\ufffd') > max(2, len(native)*.02)
            tables = []
            try:
                for table in page.find_tables().tables:
                    rows = [[cell or "" for cell in row] for row in table.extract()]
                    tables.append(_element("table", "\n".join(" | ".join(r) for r in rows), number, table.bbox, rows=rows, source="native", confidence=None, font_size=0, bold=False, spans=[]))
            except (ValueError, RuntimeError) as exc:
                warnings.append(f"page {number}: table detection failed ({type(exc).__name__})")
            page_elements = list(tables)
            if not native or corrupted:
                warnings.append(f"page {number}: OCR fallback; native text empty or corrupted")
                page_elements = _ocr(page, number, warnings)
                if not page_elements:
                    page_elements.append(_element("unclassified", "", number, page.rect, source="unreadable", confidence=0, spans=[], font_size=0, bold=False))
            else:
                for block_index, block in enumerate(layout['blocks']):
                    if block['type'] == 1:
                        rect = fitz.Rect(block['bbox'])
                        page_elements.append(_element("figure", "[raster figure]", number, rect, source="native", confidence=None, font_size=0, bold=False, spans=[]))
                        # OCR raster regions even on mixed native/scanned pages.
                        page_elements.extend(_ocr(page, number, warnings, rect))
                        warnings.append(f"page {number}: raster region OCR; inspect for duplication or unreadable labels")
                        continue
                    for line in block.get('lines', []):
                        rect = fitz.Rect(line['bbox'])
                        if any(fitz.Rect(t['bbox']).contains(rect.tl) and fitz.Rect(t['bbox']).contains(rect.br) for t in tables):
                            continue
                        spans = [{k:s[k] for k in ('text','font','size','flags','bbox')} for s in line['spans']]
                        text = ''.join(s['text'] for s in spans).strip()
                        if not text:
                            continue
                        page_elements.append(_element("unclassified", text, number, rect, source="native", confidence=None, font_size=max(s['size'] for s in spans), bold=any(s['flags'] & 16 for s in spans), spans=spans, block_index=block_index))
                        if abs(line.get('dir',(1,0))[1]) > .1:
                            warnings.append(f"page {number}: rotated text; reading order uncertain")
            page_elements.sort(key=lambda e:(round(e['bbox'][1],1),e['bbox'][0]))
            # Side-by-side non-table lines are a review signal, not proof of correct column ordering.
            if any(abs(a['bbox'][1]-b['bbox'][1]) < 3 and a['bbox'][2] < b['bbox'][0] for a,b in zip(page_elements,page_elements[1:])):
                warnings.append(f"page {number}: possible columns; reading order requires review")
            pages.append({"page": number, "text_blocks": sum(b['type']==0 for b in layout['blocks']), "spans": [s for e in page_elements for s in e.get('spans',[])], "tables": len(tables), "ocr": any(e['source']=='ocr' for e in page_elements)})
            elements.extend(page_elements)
        if not pages:
            raise ValueError("PDF has no pages")
        # Suppress only exact repeated margin text; retain evidence in report.
        margins = Counter()
        for e in elements:
            page = pdf[e['page']-1]
            if e['kind']=='unclassified' and (e['bbox'][1] < 40 or e['bbox'][3] > page.rect.height-35):
                margins[e['text']] += 1
        ignored = []
        for index,e in enumerate(elements):
            e['element_id'] = index
            e['reading_order'] = index
            if margins[e['text']] >= 2:
                e['kind'] = 'repeated_header'
                ignored.append(e)
    if not any(e['text'].strip() for e in elements):
        warnings.append("No readable content recovered")
    return elements, {"page_count": len(pages), "pages": pages, "warnings": warnings, "suppressed_headers": ignored, "element_count": len(elements), "observations_only": True}
