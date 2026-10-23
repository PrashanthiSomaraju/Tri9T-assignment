from io import BytesIO
import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont
from app.services.pdf_extractor import extract_pdf
from app.services.hierarchy_parser import parse_hierarchy
from app.services.canonical import content_hash


def scanned_pdf():
    image=Image.new('RGB',(1200,400),'white')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',38)
    draw.text((40,60),'Battery life 300 measurement cycles',font=font,fill='black')
    b=BytesIO();image.save(b,format='PNG')
    doc=fitz.open();page=doc.new_page(width=600,height=200)
    page.insert_image(page.rect,stream=b.getvalue())
    return doc.tobytes()


def test_real_ocr_scan():
    elements,report=extract_pdf(scanned_pdf())
    assert report['pages'][0]['ocr']
    assert any('300' in e['text'] for e in elements)
    assert all(e['source']=='ocr' for e in elements)
    assert all(0<=e['confidence']<=100 for e in elements)


def test_ocr_unavailable_visible(monkeypatch):
    import pytesseract
    def fail(*args,**kwargs): raise pytesseract.TesseractNotFoundError()
    monkeypatch.setattr(pytesseract,'image_to_data',fail)
    elements,report=extract_pdf(scanned_pdf())
    assert any('OCR unavailable' in w for w in report['warnings'])
    assert elements[0]['source']=='unreadable'


def test_mixed_native_raster():
    image_pdf=fitz.open(stream=scanned_pdf(),filetype='pdf')
    pix=image_pdf[0].get_pixmap()
    doc=fitz.open();p=doc.new_page()
    p.insert_text((50,60),'1 Introduction',fontname='hebo',fontsize=15)
    p.insert_image(fitz.Rect(50,100,550,270),stream=pix.tobytes('png'))
    elements,report=extract_pdf(doc.tobytes())
    assert any(e['source']=='native' and 'Introduction' in e['text'] for e in elements)
    assert any(e['source']=='ocr' and '300' in e['text'] for e in elements)
    assert any(e['kind']=='figure' for e in elements)


def test_cross_page_wrapped_paragraph_and_headers():
    doc=fitz.open()
    for i in range(2):
        p=doc.new_page();p.insert_text((50,25),'Repeated header')
        if i==0:
            p.insert_text((50,80),'1 Introduction',fontname='hebo',fontsize=15)
            p.insert_text((50,110),'A wrapped paragraph begins here and')
        else:
            p.insert_text((50,80),'continues on the next page with 299 mmHg.')
    elements,report=extract_pdf(doc.tobytes());nodes,_=parse_hierarchy(elements)
    assert len(report['suppressed_headers'])==2
    assert len(nodes)==1
    assert 'and continues on the next page' in nodes[0]['body_text']
    assert nodes[0]['page_end']==2


def test_blank_and_encrypted_pdf():
    doc=fitz.open();doc.new_page()
    _,report=extract_pdf(doc.tobytes())
    assert any('No readable' in w for w in report['warnings'])
    encrypted=doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='user')
    with pytest.raises(ValueError,match='Encrypted'):
        extract_pdf(encrypted)


def test_hash_preserves_thresholds_not_layout():
    a=[dict(kind='paragraph',text='Below 15% at 299 mmHg.',page=1)]
    b=[dict(kind='paragraph',text='Below  15% at\n299 mmHg.',page=2)]
    assert content_hash('Safety',a)==content_hash('Safety',b)
    b[0]['text']='Below 10% at 299 mmHg.'
    assert content_hash('Safety',a)!=content_hash('Safety',b)
