import re
from core.models import DocumentSection, TextChunk

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_enc.encode(text))

except ImportError:
    # Fallback: approximate 4 chars per token
    def _count_tokens(text: str) -> int:
        return len(text) // 4


MAX_TOKENS = 3000
CONTEXT_SENTENCES = 2


def _last_sentences(text: str, n: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[-n:]) if sentences else ""


def build_chunks(sections: list[DocumentSection]) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    current_texts: list[str] = []
    current_indices: list[int] = []
    current_tokens = 0
    last_chunk_tail = ""

    def flush():
        nonlocal current_texts, current_indices, current_tokens, last_chunk_tail
        if not current_texts:
            return
        combined = "\n\n".join(current_texts)
        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                section_indices=list(current_indices),
                text=combined,
                context_prefix=last_chunk_tail,
            )
        )
        last_chunk_tail = _last_sentences(combined, CONTEXT_SENTENCES)
        current_texts = []
        current_indices = []
        current_tokens = 0

    for sec in sections:
        text = sec.original_text
        tok = _count_tokens(text)

        # Single section exceeds limit — flush then emit alone
        if tok >= MAX_TOKENS:
            flush()
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    section_indices=[sec.index],
                    text=text,
                    context_prefix=last_chunk_tail,
                )
            )
            last_chunk_tail = _last_sentences(text, CONTEXT_SENTENCES)
            continue

        # Would exceed limit — flush first
        if current_tokens + tok > MAX_TOKENS and current_texts:
            flush()

        current_texts.append(text)
        current_indices.append(sec.index)
        current_tokens += tok

    flush()
    return chunks
