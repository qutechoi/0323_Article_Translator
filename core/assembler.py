from pathlib import Path

from core.models import JobStatus, ProviderConfig
from core.pdf_parser import parse_pdf
from core.chunker import build_chunks
from core.translator import translate_chunk
from api.job_store import job_store


async def run_translation_job(job_id: str, pdf_path: str, cfg: ProviderConfig) -> None:
    state = job_store.get(job_id)
    if state is None:
        return

    try:
        # --- Parse PDF ---
        state.status = JobStatus.parsing
        job_store.update(state)
        await job_store.push_event(job_id, {"event": "status", "data": {"status": "parsing"}})

        sections = parse_pdf(pdf_path)
        state.sections = sections

        # --- Build chunks ---
        chunks = build_chunks(sections)
        state.total_chunks = len(chunks)
        state.status = JobStatus.translating
        job_store.update(state)

        await job_store.push_event(
            job_id,
            {
                "event": "status",
                "data": {"status": "translating", "total": len(chunks)},
            },
        )

        # --- Translate chunk by chunk ---
        for chunk in chunks:
            translated = await translate_chunk(chunk.text, cfg, chunk.context_prefix)

            parts = _split_translation(translated, len(chunk.section_indices))
            for i, sec_idx in enumerate(chunk.section_indices):
                if i < len(parts):
                    state.sections[sec_idx].translated_text = parts[i].strip()
                else:
                    state.sections[sec_idx].translated_text = translated.strip()

            state.completed_chunks += 1
            job_store.update(state)

            await job_store.push_event(
                job_id,
                {
                    "event": "chunk_done",
                    "data": {
                        "chunk": state.completed_chunks,
                        "total": state.total_chunks,
                        "percent": state.percent,
                        "sections": [
                            {
                                "index": s.index,
                                "is_heading": s.is_heading,
                                "original_text": s.original_text,
                                "translated_text": s.translated_text,
                            }
                            for s in state.sections
                            if s.index in chunk.section_indices
                        ],
                    },
                },
            )

        # --- Done ---
        state.status = JobStatus.complete
        job_store.update(state)
        await job_store.push_event(job_id, {"event": "complete", "data": {}})

    except Exception as exc:
        state.status = JobStatus.error
        state.error_message = str(exc)
        job_store.update(state)
        await job_store.push_event(
            job_id, {"event": "error", "data": {"message": str(exc)}}
        )
        # PDF는 에러 시에도 유지 (뷰어에서 볼 수 있도록)


def _split_translation(text: str, count: int) -> list[str]:
    """Try to split translated text into `count` parts at paragraph boundaries."""
    if count == 1:
        return [text]
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(parts) >= count:
        result = parts[: count - 1]
        result.append("\n\n".join(parts[count - 1 :]))
        return result
    return parts + [""] * (count - len(parts))
