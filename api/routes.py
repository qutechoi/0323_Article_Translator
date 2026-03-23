import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from api.job_store import job_store
from core.assembler import run_translation_job
from core.models import Provider, ProviderConfig

router = APIRouter(prefix="/api")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(""),
    base_url: str = Form("http://localhost:1234/v1"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    try:
        prov = Provider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 프로바이더: {provider}")

    if prov != Provider.lmstudio and not api_key:
        raise HTTPException(status_code=400, detail="API 키를 입력해주세요.")

    cfg = ProviderConfig(
        provider=prov,
        model=model,
        api_key=api_key or None,
        base_url=base_url,
    )

    job_id = str(uuid.uuid4())
    job_store.create(job_id)

    pdf_path = UPLOAD_DIR / f"{job_id}.pdf"
    content = await file.read()
    pdf_path.write_bytes(content)

    background_tasks.add_task(run_translation_job, job_id, str(pdf_path), cfg)

    return JSONResponse({"job_id": job_id})


@router.get("/progress/{job_id}")
async def progress(job_id: str):
    state = job_store.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    async def event_stream():
        while True:
            event = await job_store.get_event(job_id)
            if event is None:
                break

            name = event.get("event", "message")
            data = event.get("data", {})
            yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            if name in ("pdf_ready", "error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/pdf/{job_id}")
async def serve_pdf(job_id: str):
    pdf_path = UPLOAD_DIR / f"{job_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없습니다.")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@router.get("/translated-pdf/{job_id}")
async def serve_translated_pdf(job_id: str):
    pdf_path = UPLOAD_DIR / f"{job_id}_translated.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="번역 PDF가 아직 준비되지 않았습니다.")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@router.delete("/job/{job_id}")
async def cleanup_job(job_id: str):
    for suffix in [".pdf", "_translated.pdf"]:
        try:
            (UPLOAD_DIR / f"{job_id}{suffix}").unlink(missing_ok=True)
        except OSError:
            pass
    job_store.cleanup(job_id)
    return JSONResponse({"ok": True})


@router.get("/result/{job_id}")
async def result(job_id: str):
    state = job_store.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    return JSONResponse(
        {
            "job_id": state.job_id,
            "status": state.status,
            "percent": state.percent,
            "total_chunks": state.total_chunks,
            "completed_chunks": state.completed_chunks,
            "error_message": state.error_message,
            "sections": [
                {
                    "index": s.index,
                    "is_heading": s.is_heading,
                    "original_text": s.original_text,
                    "translated_text": s.translated_text,
                }
                for s in state.sections
            ],
        }
    )
