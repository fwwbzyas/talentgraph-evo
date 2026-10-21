from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree


MAX_RESUME_BYTES = 20 * 1024 * 1024


class ResumeFileError(ValueError):
    pass


def extract_resume_text(filename: str, content: bytes) -> dict[str, object]:
    if not content:
        raise ResumeFileError("resume file is empty")
    if len(content) > MAX_RESUME_BYTES:
        raise ResumeFileError("resume file exceeds 20 MB")

    suffix = Path(filename or "").suffix.lower()
    images = []
    document_parse: dict[str, object] = {
        "file_type": suffix.lstrip(".") or "unknown",
        "page_count": None,
        "methods": [],
        "text_quality": "unknown",
        "layout_warnings": [],
        "used_vision": False,
    }
    if suffix == ".pdf":
        text = _extract_pdf_text(content)
        text_quality = _text_quality_label(text)
        images = _render_pdf_images(content) if text_quality in {"empty", "low"} else []
        page_count = None
        methods = ["pdf_text_extractors"]
        try:
            from pypdf import PdfReader
            page_count = len(PdfReader(BytesIO(content)).pages)
            methods = ["pypdf"]
        except Exception:
            pass
        document_parse.update({
            "page_count": page_count,
            "methods": methods,
            "text_quality": text_quality,
            "layout_warnings": ["pdf_text_quality_low"] if text_quality in {"empty", "low"} else [],
            "used_vision": bool(images),
        })
    elif suffix in {".docx", ".docm"}:
        text = _extract_docx_text(content)
        document_parse.update(
            {
                "methods": ["docx_zip_xml"],
                "text_quality": _text_quality_label(text),
                "layout_warnings": [],
                "used_vision": False,
            }
        )
    elif suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        text = ""
        images = [_image_payload(content, _image_mime_type(suffix), "page_1")]
        document_parse.update(
            {
                "methods": ["image_payload"],
                "page_count": 1,
                "text_quality": "empty",
                "layout_warnings": ["image_resume_requires_vision_parse"],
                "used_vision": True,
            }
        )
    elif suffix in {".txt", ".md", ".json", ".csv"}:
        text = _decode_text(content)
        document_parse.update(
            {
                "methods": ["plain_text_decode"],
                "text_quality": _text_quality_label(text),
                "layout_warnings": [],
                "used_vision": False,
            }
        )
    elif suffix == ".doc":
        raise ResumeFileError("legacy .doc is not supported; please save the Word resume as .docx and upload again")
    else:
        raise ResumeFileError("unsupported resume file type; please upload .pdf, .docx, .docm, or .txt")

    normalized = _normalize_text(text)
    if not normalized and not images:
        raise ResumeFileError("could not extract readable text from resume file")

    return {
        "filename": filename,
        "file_type": suffix.lstrip(".") or "unknown",
        "text": normalized,
        "text_length": len(normalized),
        "images": images,
        "image_count": len(images),
        "document_parse": {
            **document_parse,
            "text_quality": _text_quality_label(normalized),
            "used_vision": bool(document_parse.get("used_vision")),
        },
    }


def _extract_pdf_text(content: bytes) -> str:
    result = _extract_pdf_document(content)
    return str(result["text"])


def _extract_pdf_document(content: bytes) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    warnings: list[str] = []
    page_count: int | None = None

    for extractor in (_extract_pdf_text_pypdf, _extract_pdf_text_pymupdf, _extract_pdf_text_pdfplumber):
        try:
            candidate = extractor(content)
        except ImportError as exc:
            warnings.append(f"{extractor.__name__}_missing: {exc}")
            continue
        except Exception as exc:
            warnings.append(f"{extractor.__name__}_failed: {exc}")
            continue
        text = str(candidate.get("text", ""))
        if candidate.get("page_count"):
            page_count = int(candidate["page_count"])
        if text.strip():
            candidates.append(candidate)

    if not candidates:
        if warnings:
            raise ResumeFileError(f"failed to parse PDF resume: {'; '.join(warnings[:3])}")
        raise ResumeFileError("failed to parse PDF resume")

    best = max(candidates, key=lambda item: _text_quality_score(str(item.get("text", ""))))
    merged_text = _merge_pdf_text_candidates(str(best.get("text", "")), candidates)
    methods = [str(item.get("method")) for item in candidates if item.get("method")]
    quality = _text_quality_label(merged_text)
    if quality in {"empty", "low"}:
        warnings.append("pdf_text_quality_low")
    return {
        "text": merged_text,
        "document_parse": {
            "file_type": "pdf",
            "page_count": page_count,
            "methods": methods,
            "text_quality": quality,
            "layout_warnings": warnings[:8],
            "used_vision": False,
        },
    }


def _extract_pdf_text_pypdf(content: bytes) -> dict[str, object]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError("pypdf is not installed") from exc

    reader = PdfReader(BytesIO(content))
    text = "\n".join(f"[page:{index + 1}]\n{page.extract_text() or ''}" for index, page in enumerate(reader.pages))
    return {"method": "pypdf", "text": text, "page_count": len(reader.pages)}


def _extract_pdf_text_pymupdf(content: bytes) -> dict[str, object]:
    try:
        import fitz
    except ImportError as exc:
        raise ImportError("PyMuPDF is not installed") from exc

    document = fitz.open(stream=content, filetype="pdf")
    pages: list[str] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        blocks = page.get_text("blocks") or []
        ordered = sorted(blocks, key=lambda block: (round(float(block[1]) / 8), float(block[0])))
        block_text = "\n".join(str(block[4]).strip() for block in ordered if len(block) > 4 and str(block[4]).strip())
        pages.append(f"[page:{page_index + 1}]\n{block_text}")
    return {"method": "pymupdf_blocks", "text": "\n".join(pages), "page_count": document.page_count}


def _extract_pdf_text_pdfplumber(content: bytes) -> dict[str, object]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber is not installed") from exc

    pages: list[str] = []
    with pdfplumber.open(BytesIO(content)) as document:
        for page_index, page in enumerate(document.pages):
            chunks = [page.extract_text(layout=True) or ""]
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [str(cell or "").strip() for cell in row]
                    line = "\t".join(cell for cell in cells if cell)
                    if line:
                        chunks.append(line)
            pages.append(f"[page:{page_index + 1}]\n" + "\n".join(chunk for chunk in chunks if chunk.strip()))
    return {"method": "pdfplumber_layout_tables", "text": "\n".join(pages), "page_count": len(pages)}


def _merge_pdf_text_candidates(primary_text: str, candidates: list[dict[str, object]]) -> str:
    lines: list[str] = []
    seen: set[str] = set()

    def add_lines(text: str, *, limit: int | None = None) -> None:
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            key = re.sub(r"\s+", "", line.lower())
            if key in seen:
                continue
            seen.add(key)
            lines.append(line)
            if limit and len(lines) >= limit:
                break

    add_lines(primary_text)
    for candidate in candidates:
        if candidate.get("method") == "pdfplumber_layout_tables":
            add_lines(str(candidate.get("text", "")), limit=len(lines) + 80)
    return "\n".join(lines)


def _text_quality_score(text: str) -> float:
    normalized = _normalize_text(text)
    if not normalized:
        return 0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    latin = len(re.findall(r"[A-Za-z0-9]", normalized))
    useful = len(re.findall(r"技能|项目|经历|教育|证书|求职|经验|Skills|Project|Experience|Education|Certificate", normalized, re.I))
    return len(normalized) + useful * 180 + (chinese + latin) * 0.2


def _text_quality_label(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return "empty"
    score = _text_quality_score(normalized)
    if len(normalized) < 120 or score < 220:
        return "low"
    if len(normalized) < 800:
        return "medium"
    return "high"


def _extract_docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ResumeFileError("invalid DOCX resume file")
            xml_names = [
                name for name in _docx_text_part_order(archive.namelist()) if name in names
            ]
            chunks = []
            for name in xml_names:
                part_text = _extract_docx_xml_text(archive.read(name))
                if part_text:
                    chunks.append(part_text)
            return "\n\n".join(chunks)
    except zipfile.BadZipFile as exc:
        raise ResumeFileError("invalid DOCX resume file") from exc
    except ResumeFileError:
        raise
    except Exception as exc:
        raise ResumeFileError(f"failed to parse DOCX resume: {exc}") from exc


def _docx_text_part_order(names: list[str]) -> list[str]:
    def part_key(name: str) -> tuple[int, str]:
        if name == "word/document.xml":
            return (0, name)
        if name.startswith("word/header"):
            return (1, name)
        if name.startswith("word/footer"):
            return (2, name)
        if name.startswith("word/footnotes"):
            return (3, name)
        if name.startswith("word/endnotes"):
            return (4, name)
        return (9, name)

    return sorted(
        [
            name
            for name in names
            if name == "word/document.xml"
            or name.startswith("word/header")
            or name.startswith("word/footer")
            or name.startswith("word/footnotes")
            or name.startswith("word/endnotes")
        ],
        key=part_key,
    )


def _extract_docx_xml_text(xml_content: bytes) -> str:
    root = ElementTree.fromstring(xml_content)
    paragraphs: list[str] = []

    for paragraph in root.iter(_w_tag("p")):
        text = _extract_docx_paragraph_text(paragraph)
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _extract_docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    chunks: list[str] = []
    for node in paragraph.iter():
        if node.tag == _w_tag("t") and node.text:
            chunks.append(node.text)
        elif node.tag == _w_tag("tab"):
            chunks.append("\t")
        elif node.tag == _w_tag("br"):
            chunks.append("\n")
    text = "".join(chunks)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _w_tag(local_name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{local_name}"


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _render_pdf_images(content: bytes, *, max_pages: int = 3) -> list[dict[str, str]]:
    try:
        import fitz
    except ImportError:
        return []

    images: list[dict[str, str]] = []
    try:
        document = fitz.open(stream=content, filetype="pdf")
        for page_index in range(min(max_pages, document.page_count)):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            images.append(_image_payload(pixmap.tobytes("png"), "image/png", f"page_{page_index + 1}"))
    except Exception:
        return []
    return images


def _image_payload(content: bytes, mime_type: str, label: str) -> dict[str, str]:
    return {
        "label": label,
        "mime_type": mime_type,
        "base64": base64.b64encode(content).decode("ascii"),
    }


def _image_mime_type(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
