from __future__ import annotations

from io import BytesIO
import zipfile

from agents.assessment.resume_files import extract_resume_text


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _docx_bytes(document_xml: str, *, header_xml: str = "", footer_xml: str = "") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>""")
        archive.writestr("word/document.xml", document_xml)
        if header_xml:
            archive.writestr("word/header1.xml", header_xml)
        if footer_xml:
            archive.writestr("word/footer1.xml", footer_xml)
    return buffer.getvalue()


def test_extract_resume_text_from_word_docx_preserves_sections_and_tables():
    namespace = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <w:document {namespace}>
      <w:body>
        {_paragraph("候选人：李雷")}
        {_paragraph("技能栏：Python、FastAPI、RAG、LangGraph、Redis")}
        <w:tbl>
          <w:tr>
            <w:tc>{_paragraph("项目名称")}</w:tc>
            <w:tc>{_paragraph("企业知识库 Agent 平台")}</w:tc>
          </w:tr>
          <w:tr>
            <w:tc>{_paragraph("项目成果")}</w:tc>
            <w:tc>{_paragraph("命中率提升 18%，接口延迟 230ms")}</w:tc>
          </w:tr>
        </w:tbl>
        {_paragraph("期望薪资：25-35K")}
      </w:body>
    </w:document>
    """
    header_xml = f"""<?xml version="1.0" encoding="UTF-8"?><w:hdr {namespace}>{_paragraph("五年后端和 AI 应用开发经验，本科")}</w:hdr>"""

    result = extract_resume_text("resume.docx", _docx_bytes(document_xml, header_xml=header_xml))

    assert result["file_type"] == "docx"
    assert result["image_count"] == 0
    assert "候选人：李雷" in result["text"]
    assert "项目名称" in result["text"]
    assert "企业知识库 Agent 平台" in result["text"]
    assert "五年后端和 AI 应用开发经验，本科" in result["text"]


def test_extract_resume_text_accepts_word_docm_package():
    namespace = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <w:document {namespace}><w:body>{_paragraph("技能栏：Java、Spring Boot、MySQL")}</w:body></w:document>
    """

    result = extract_resume_text("resume.docm", _docx_bytes(document_xml))

    assert result["file_type"] == "docm"
    assert "Spring Boot" in result["text"]


def test_extract_resume_text_from_pdf_returns_document_parse_metadata():
    import fitz

    buffer = BytesIO()
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((80, 80), "Skills: Python, FastAPI, Redis")
    page.insert_text((80, 110), "Project: Retail Agent platform reduced latency by 30 percent")
    page.insert_text((80, 140), "Certificate: AWS")
    page.insert_text((80, 170), "Experience: 3 years backend development, Education: Bachelor of Computer Science")
    buffer.write(pdf.tobytes())

    result = extract_resume_text("resume.pdf", buffer.getvalue())

    assert result["file_type"] == "pdf"
    assert "Python" in result["text"]
    assert result["document_parse"]["file_type"] == "pdf"
    assert result["document_parse"]["page_count"] == 1
    assert result["document_parse"]["text_quality"] in {"medium", "high"}
    assert "pypdf" in result["document_parse"]["methods"]
