from core.models import ProviderConfig, Provider

SYSTEM_PROMPT = """당신은 영어 학술 논문을 한국어로 번역하는 전문 번역가입니다.

번역 규칙:
1. [HEADING], [PARA], [FIGURE_CAPTION] 등 마커가 있으면 그대로 유지하세요.
2. 인용 형식은 원본 그대로 유지하세요: (Author, Year), [1] 형식 등.
3. 전문 용어는 영어 원어를 괄호 안에 병기하세요: 어텐션 메커니즘 (attention mechanism).
4. 저자명, URL, DOI, 수식 기호는 번역하지 마세요.
5. 학술 격식체(합니다/입니다)를 사용하세요.
6. 번역문만 출력하고, 설명이나 메모는 추가하지 마세요."""

USER_TEMPLATE = """{context}다음 학술 논문 텍스트를 한국어로 번역하세요:

{text}"""


def _build_user_prompt(text: str, context_prefix: str) -> str:
    ctx = f"[이전 문맥]: {context_prefix}\n\n" if context_prefix.strip() else ""
    return USER_TEMPLATE.format(context=ctx, text=text)


async def translate_chunk(text: str, cfg: ProviderConfig, context_prefix: str = "") -> str:
    user_msg = _build_user_prompt(text, context_prefix)

    if cfg.provider == Provider.anthropic:
        return await _translate_anthropic(user_msg, cfg)
    elif cfg.provider == Provider.openai:
        return await _translate_openai(user_msg, cfg)
    elif cfg.provider == Provider.google:
        return await _translate_google(user_msg, cfg)
    elif cfg.provider == Provider.lmstudio:
        return await _translate_lmstudio(user_msg, cfg)
    else:
        raise ValueError(f"Unknown provider: {cfg.provider}")


async def _translate_anthropic(user_msg: str, cfg: ProviderConfig) -> str:
    import anthropic
    import asyncio

    client = anthropic.Anthropic(api_key=cfg.api_key)

    def _call():
        msg = client.messages.create(
            model=cfg.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return msg.content[0].text

    return await asyncio.get_event_loop().run_in_executor(None, _call)


async def _translate_openai(user_msg: str, cfg: ProviderConfig) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=cfg.api_key)
    resp = await client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=4096,
    )
    return resp.choices[0].message.content


async def _translate_google(user_msg: str, cfg: ProviderConfig) -> str:
    from google import genai
    from google.genai import types
    import asyncio

    client = genai.Client(api_key=cfg.api_key)

    def _call():
        resp = client.models.generate_content(
            model=cfg.model,
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=4096,
            ),
        )
        return resp.text

    return await asyncio.get_event_loop().run_in_executor(None, _call)


async def _translate_lmstudio(user_msg: str, cfg: ProviderConfig) -> str:
    from openai import AsyncOpenAI

    base_url = cfg.base_url or "http://localhost:1234/v1"
    api_key = cfg.api_key or "lm-studio"

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    resp = await client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=4096,
    )
    return resp.choices[0].message.content
