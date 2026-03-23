import statistics
from dataclasses import dataclass, field
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    raise ImportError("PyMuPDF is required: pip install pymupdf")

from core.models import DocumentSection, TextPosition


@dataclass
class Block:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    font_size: float
    page: int
    is_image: bool = False


def _median_font_size(blocks: list[Block]) -> float:
    sizes = [b.font_size for b in blocks if not b.is_image and b.text.strip()]
    if not sizes:
        return 12.0
    return statistics.median(sizes)


def _detect_columns(blocks: list[Block], page_width: float) -> bool:
    """Return True if page appears to have 2 columns."""
    x_centers = [
        (b.x0 + b.x1) / 2 for b in blocks if not b.is_image and b.text.strip()
    ]
    if len(x_centers) < 4:
        return False
    mid = page_width / 2
    left = sum(1 for x in x_centers if x < mid)
    right = sum(1 for x in x_centers if x >= mid)
    # Both sides must have content to be considered 2-column
    ratio = min(left, right) / max(left, right) if max(left, right) > 0 else 0
    return ratio > 0.3


def _sort_blocks(blocks: list[Block], two_column: bool, page_width: float) -> list[Block]:
    if not two_column:
        return sorted(blocks, key=lambda b: (b.page, b.y0, b.x0))
    mid = page_width / 2
    left = [b for b in blocks if (b.x0 + b.x1) / 2 < mid]
    right = [b for b in blocks if (b.x0 + b.x1) / 2 >= mid]
    left_sorted = sorted(left, key=lambda b: (b.page, b.y0))
    right_sorted = sorted(right, key=lambda b: (b.page, b.y0))
    return left_sorted + right_sorted


def parse_pdf(path: str) -> list[DocumentSection]:
    doc = fitz.open(path)

    if len(doc) == 0:
        raise ValueError("PDF has no pages.")

    all_blocks: list[Block] = []
    page_widths: list[float] = []

    for page_num, page in enumerate(doc):
        page_widths.append(page.rect.width)
        raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in raw.get("blocks", []):
            btype = block.get("type", 0)

            if btype == 1:  # image block
                all_blocks.append(
                    Block(
                        x0=block["bbox"][0], y0=block["bbox"][1],
                        x1=block["bbox"][2], y1=block["bbox"][3],
                        text="[그림]", font_size=0, page=page_num, is_image=True,
                    )
                )
                continue

            lines_text = []
            max_size = 0.0
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "").strip()
                    if txt:
                        lines_text.append(txt)
                        max_size = max(max_size, span.get("size", 12.0))

            text = " ".join(lines_text).strip()
            if not text:
                continue

            all_blocks.append(
                Block(
                    x0=block["bbox"][0], y0=block["bbox"][1],
                    x1=block["bbox"][2], y1=block["bbox"][3],
                    text=text, font_size=max_size, page=page_num,
                )
            )

    doc.close()

    # Check for scanned PDF (no text at all)
    text_blocks = [b for b in all_blocks if not b.is_image and b.text.strip()]
    if not text_blocks:
        raise ValueError(
            "이 PDF에서 텍스트를 추출할 수 없습니다. 스캔된 이미지 PDF일 수 있습니다. "
            "OCR 처리 후 다시 시도해주세요."
        )

    avg_width = statistics.mean(page_widths) if page_widths else 595.0
    median_size = _median_font_size(text_blocks)
    heading_threshold = median_size * 1.4

    two_column = _detect_columns(text_blocks, avg_width)
    sorted_blocks = _sort_blocks(all_blocks, two_column, avg_width)

    sections: list[DocumentSection] = []
    fig_counter = 0

    for block in sorted_blocks:
        if block.is_image:
            fig_counter += 1
            sections.append(
                DocumentSection(
                    index=len(sections),
                    original_text=f"[그림 {fig_counter}]",
                    is_heading=False,
                )
            )
            continue

        text = block.text.strip()
        if not text:
            continue

        is_heading = block.font_size >= heading_threshold and len(text) < 200
        sections.append(
            DocumentSection(
                index=len(sections),
                heading=text if is_heading else None,
                original_text=text,
                is_heading=is_heading,
                position=TextPosition(
                    page=block.page,
                    x0=block.x0,
                    y0=block.y0,
                    x1=block.x1,
                    y1=block.y1,
                    font_size=block.font_size,
                ),
            )
        )

    return sections
