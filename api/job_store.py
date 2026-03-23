import asyncio
from typing import Optional
from core.models import JobState, JobStatus


class JobStore:
    def __init__(self):
        self._jobs: dict[str, JobState] = {}
        self._queues: dict[str, asyncio.Queue] = {}

    def create(self, job_id: str) -> JobState:
        state = JobState(job_id=job_id)
        self._jobs[job_id] = state
        self._queues[job_id] = asyncio.Queue()
        return state

    def get(self, job_id: str) -> Optional[JobState]:
        return self._jobs.get(job_id)

    def update(self, state: JobState) -> None:
        self._jobs[state.job_id] = state

    async def push_event(self, job_id: str, event: dict) -> None:
        q = self._queues.get(job_id)
        if q:
            await q.put(event)

    async def get_event(self, job_id: str) -> Optional[dict]:
        q = self._queues.get(job_id)
        if q is None:
            return None
        try:
            return await asyncio.wait_for(q.get(), timeout=30.0)
        except asyncio.TimeoutError:
            return {"event": "heartbeat"}

    def cleanup(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        self._queues.pop(job_id, None)


job_store = JobStore()
