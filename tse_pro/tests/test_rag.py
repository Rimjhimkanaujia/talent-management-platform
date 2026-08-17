import io
import pytest

streamlit = pytest.importorskip("streamlit", reason="requires `pip install -r requirements.txt`")
pytest.importorskip("pypdf")
pytest.importorskip("reportlab")
import rag


def _make_test_pdf():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "GS1 standards enable traceability across supply chains. " * 3)
    c.showPage()
    c.drawString(72, 720, "EPCIS shares real time supply chain events between partners. " * 3)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_extract_pdf_chunks_page_count():
    pages, chunks = rag.extract_pdf_chunks(_make_test_pdf(), words_per_chunk=10, overlap=2)
    assert pages == 2
    assert len(chunks) > 0
    assert all(p in (1, 2) for p, _, _ in chunks)


def test_extract_pdf_chunks_preserves_page_numbers():
    _, chunks = rag.extract_pdf_chunks(_make_test_pdf(), words_per_chunk=10, overlap=2)
    page1_chunks = [t for p, _, t in chunks if p == 1]
    page2_chunks = [t for p, _, t in chunks if p == 2]
    assert any("GS1" in t for t in page1_chunks)
    assert any("EPCIS" in t for t in page2_chunks)
