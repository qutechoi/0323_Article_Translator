from pathlib import Path

import fitz

from core.models import DocumentSection


# ── 한국어 폰트 탐색 ──────────────────────────────────────────────────────────
_FONT_CANDIDATES = [
    # WSL2 — Windows 폰트 마운트
    "/mnt/c/Windows/Fonts/malgun.ttf",
    "/mnt/c/Windows/Fonts/malgunbd.ttf",
    "/mnt/c/Windows/Fonts/gulim.ttc",
    "/mnt/c/Windows/Fonts/batang.ttc",
    # Linux (apt install fonts-nanum)
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    # Noto CJK
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleSDGothicNeo.ttc",
]

_font_buffer_cache: bytes | None = None


def _load_korean_font() -> bytes | None:
    """폰트 파일을 메모리에 한 번만 읽어 캐싱한다."""
    global _font_buffer_cache
    if _font_buffer_cache is not None:
        return _font_buffer_cache
    for p in _FONT_CANDIDATES:
        path = Path(p)
        if path.exists():
            _font_buffer_cache = path.read_bytes()
            return _font_buffer_cache
    return None


# ── 번역 PDF 생성 ─────────────────────────────────────────────────────────────

def generate_translated_pdf(
    original_path: str,
    sections: list[DocumentSection],
    output_path: str,
) -> None:
    font_buffer = _load_korean_font()

    doc = fitz.open(original_path)

    # 위치 정보 + 번역문이 모두 있는 섹션만 페이지별 그룹핑
    page_sections: dict[int, list[DocumentSection]] = {}
    for sec in sections:
        if sec.position is None or not sec.translated_text:
            continue
        page_sections.setdefault(sec.position.page, []).append(sec)

    if not page_sections:
        doc.close()
        return

    for page_num in range(len(doc)):
        secs = page_sections.get(page_num)
        if not secs:
            continue

        page = doc[page_num]

        # 1단계: 원본 텍스트 영역을 흰색으로 redact
        for sec in secs:
            pos = sec.position
            rect = fitz.Rect(pos.x0, pos.y0, pos.x1, pos.y1)
            page.add_redact_annot(rect, fill=(1, 1, 1), text="")

        # images=0 → 이미지를 건드리지 않음 (상수 대신 정수 사용으로 호환성 보장)
        page.apply_redactions(images=0)

        # 2단계: 페이지에 한국어 폰트를 한 번만 등록
        if font_buffer:
            page.insert_font(fontname="KO", fontbuffer=font_buffer)
            fontname = "KO"
        else:
            fontname = "cjk"

        # 3단계: 같은 위치에 번역문 삽입 (fontbuffer/fontfile 재전달 불필요)
        for sec in secs:
            pos = sec.position
            rect = fitz.Rect(pos.x0, pos.y0, pos.x1, pos.y1)
            font_size = max(pos.font_size * 0.88, 6.5)

            rc = page.insert_textbox(
                rect,
                sec.translated_text,
                fontname=fontname,
                fontsize=font_size,
                color=(0, 0, 0),
                align=fitz.TEXT_ALIGN_LEFT,
            )

            # 박스 넘침 시 폰트 축소 재시도
            if rc < 0:
                page.insert_textbox(
                    rect,
                    sec.translated_text,
                    fontname=fontname,
                    fontsize=max(font_size * 0.7, 5.0),
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_LEFT,
                )

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
