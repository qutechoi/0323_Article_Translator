from pathlib import Path

import fitz

from core.models import DocumentSection


# ── 한국어 폰트 탐색 ──────────────────────────────────────────────────────────
_FONT_CANDIDATES = [
    # WSL2 — Windows 폰트 마운트
    "/mnt/c/Windows/Fonts/malgun.ttf",        # 맑은 고딕
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


def _find_korean_font() -> str | None:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


# ── 번역 PDF 생성 ─────────────────────────────────────────────────────────────

def generate_translated_pdf(
    original_path: str,
    sections: list[DocumentSection],
    output_path: str,
) -> None:
    """
    원본 PDF의 텍스트 블록을 한국어 번역문으로 교체한 새 PDF를 생성합니다.
    이미지, 표, 배경 등 텍스트 외 요소는 원본 그대로 유지됩니다.
    """
    font_path = _find_korean_font()

    doc = fitz.open(original_path)

    # 페이지별로 섹션 그룹핑 (위치 정보 있고 번역문 있는 것만)
    page_sections: dict[int, list[DocumentSection]] = {}
    for sec in sections:
        if sec.position is None or not sec.translated_text:
            continue
        page_sections.setdefault(sec.position.page, []).append(sec)

    for page_num in range(len(doc)):
        secs = page_sections.get(page_num)
        if not secs:
            continue

        page = doc[page_num]

        # 1단계: 원본 텍스트 블록 영역을 흰색으로 redact
        for sec in secs:
            pos = sec.position
            rect = fitz.Rect(pos.x0, pos.y0, pos.x1, pos.y1)
            page.add_redact_annot(rect, fill=(1, 1, 1), text="")

        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # 2단계: 같은 위치에 번역문 삽입
        for sec in secs:
            pos = sec.position
            rect = fitz.Rect(pos.x0, pos.y0, pos.x1, pos.y1)

            # 한국어는 영문보다 글자폭이 커서 약간 축소
            font_size = max(pos.font_size * 0.88, 6.5)

            if font_path:
                rc = page.insert_textbox(
                    rect,
                    sec.translated_text,
                    fontname="KO",
                    fontfile=font_path,
                    fontsize=font_size,
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_LEFT,
                )
            else:
                # 폰트 파일 없으면 PyMuPDF 내장 CJK 폰트 사용
                rc = page.insert_textbox(
                    rect,
                    sec.translated_text,
                    fontname="cjk",
                    fontsize=font_size,
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_LEFT,
                )

            # rc < 0 이면 박스 넘침 → 폰트 더 축소 후 재시도
            if rc < 0:
                smaller = max(font_size * 0.75, 5.0)
                kwargs = dict(
                    rect=rect,
                    text=sec.translated_text,
                    fontsize=smaller,
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_LEFT,
                )
                if font_path:
                    kwargs["fontname"] = "KO"
                    kwargs["fontfile"] = font_path
                else:
                    kwargs["fontname"] = "cjk"
                page.insert_textbox(**kwargs)

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
