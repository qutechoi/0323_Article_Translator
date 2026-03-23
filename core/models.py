from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Provider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"
    google = "google"
    lmstudio = "lmstudio"


class ProviderConfig(BaseModel):
    provider: Provider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = "http://localhost:1234/v1"  # LM Studio default


class JobStatus(str, Enum):
    pending = "pending"
    parsing = "parsing"
    translating = "translating"
    complete = "complete"
    error = "error"


class TextPosition(BaseModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float


class DocumentSection(BaseModel):
    index: int
    heading: Optional[str] = None
    original_text: str
    translated_text: Optional[str] = None
    is_heading: bool = False
    position: Optional[TextPosition] = None  # 원본 PDF 내 좌표


class TextChunk(BaseModel):
    chunk_index: int
    section_indices: list[int]
    text: str
    context_prefix: str = ""


class JobState(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.pending
    total_chunks: int = 0
    completed_chunks: int = 0
    sections: list[DocumentSection] = []
    error_message: Optional[str] = None

    @property
    def percent(self) -> int:
        if self.total_chunks == 0:
            return 0
        return int(self.completed_chunks / self.total_chunks * 100)
