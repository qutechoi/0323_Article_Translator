import os
import sys
from pathlib import Path

import fitz

from core.models import DocumentSection


# ── 한국어 폰트 탐색 ──────────────────────────────────────────────────────────
_FONT_CANDIDATES = [
    # Windows 네이티브
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/gulim.ttc",
    "C:/Windows/Fonts/batang.ttc",
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
_font_searched: bool = False


def _load_korean_font() -> bytes | None:
    global _font_buffer_cache, _font_searched
    if _font_searched:
        return _font_buffer_cache
    _font_searched = True

    # Windows 사용자 폰트 폴더도 검색
    if sys.platform == "win32":
        local_fonts = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
        if local_fonts.is_dir():
            for f in local_fonts.glob("*.ttf"):
                try:
                    _font_buffer_cache = f.read_bytes()
                    return _font_buffer_cache
                except OSError:
                    continue

    for p in _FONT_CANDIDATES:
        path = Path(p)
        if path.exists():
            try:
                _font_buffer_cache = path.read_bytes()
                return _font_buffer_cache
            except OSError:
                continue

    return None


# ── 번역 PDF 생성 ─────────────────────────────────────────────────────────────

def generate_translated_pdf(
    original_path: str,
    sections: list[DocumentSection],
    output_path: str,
) -> None:
    font_buffer = _load_korean_font()
    if font_buffer is None:
        raise RuntimeError(
            "한국어 폰트를 찾을 수 없습니다. "
            "C:\\Windows\\Fonts\\malgun.ttf 등 한국어 폰트가 설치되어 있는지 확인해주세요."
        )

    doc = fitz.open(original_path)

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

        page.apply_redactions(images=0)

        # 2단계: 같은 위치에 번역문 삽입
        # 페이지에 폰트를 먼저 등록한 뒤 insert_textbox로 텍스트 삽입
        page.insert_font(fontname="KO", fontbuffer=font_buffer)

        for sec in secs:
            pos = sec.position
            rect = fitz.Rect(pos.x0, pos.y0, pos.x1, pos.y1)
            font_size = max(pos.font_size * 0.88, 6.5)

            rc = page.insert_textbox(
                rect,
                sec.translated_text,
                fontname="KO",
                fontsize=font_size,
                color=(0, 0, 0),
                align=fitz.TEXT_ALIGN_LEFT,
            )

            # 박스 넘침 시 폰트 축소 재시도
            if rc < 0:
                smaller = max(font_size * 0.7, 5.0)
                page.insert_textbox(
                    rect,
                    sec.translated_text,
                    fontname="KO",
                    fontsize=smaller,
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_LEFT,
                )

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
