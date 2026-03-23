# Article Translator

영문 PDF 학술 논문을 한국어로 번역하는 웹앱입니다.
Anthropic, OpenAI, Google, LM Studio(로컬) 중 원하는 AI 모델을 선택해 번역할 수 있습니다.

---

## 주요 기능

- **PDF 업로드** — 드래그 앤 드롭 또는 클릭으로 파일 선택
- **멀티 프로바이더** — Claude / GPT / Gemini / LM Studio 지원
- **실시간 진행 표시** — 청크 단위 번역 진행률을 SSE로 실시간 업데이트
- **좌우 나란히 보기** — 원문(영어)과 번역문(한국어)을 동시에 비교
- **탭 전환** — 나란히 보기 / 번역문만 / 원문만
- **복사 및 저장** — 번역문 클립보드 복사, TXT 파일 저장
- **설정 저장** — 프로바이더·모델·API 키를 `localStorage`에 저장 (새로고침 후 유지)

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | Python 3.10+, FastAPI, Uvicorn |
| PDF 파싱 | PyMuPDF (fitz) |
| 토큰 계산 | tiktoken |
| 번역 SDK | anthropic, openai, google-genai |
| 프론트엔드 | Vanilla HTML / CSS / JavaScript (FastAPI StaticFiles 서빙) |

---

## 빠른 시작 (가상환경)

### 1. 저장소 클론

```bash
git clone <저장소 URL>
cd 0323_Article_Translator
```

### 2. 가상환경 생성 및 활성화

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt)**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### 3. 의존성 설치

```bash
pip install fastapi uvicorn python-multipart pymupdf tiktoken \
            anthropic openai google-genai python-dotenv aiofiles
```

### 4. 환경 변수 설정 (선택)

API 키를 미리 환경변수로 설정할 수 있습니다. UI에서 직접 입력해도 됩니다.

```bash
cp .env.example .env
# .env 파일을 열어 사용할 API 키를 입력
```

`.env` 예시:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

### 5. 서버 실행

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 브라우저에서 접속

```
http://localhost:8000
```

---

## 사용 방법

1. **프로바이더 선택** — 왼쪽 사이드바에서 Anthropic / OpenAI / Google / LM Studio 중 선택
2. **모델 선택** — 드롭다운에서 모델 선택 (LM Studio는 모델명 직접 입력)
3. **API 키 입력** — 해당 프로바이더의 API 키 입력 (LM Studio는 선택 사항)
4. **PDF 업로드** — 파일을 드래그하거나 클릭해서 선택
5. **번역 시작** — "번역 시작" 버튼 클릭
6. **결과 확인** — 번역이 진행되는 동안 실시간으로 결과를 확인

---

## 프로바이더별 설정

### Anthropic (Claude)
- [Anthropic Console](https://console.anthropic.com/)에서 API 키 발급
- 권장 모델: `claude-haiku-4-5-20251001` (빠름·저렴), `claude-sonnet-4-6` (고품질)

### OpenAI (GPT)
- [OpenAI Platform](https://platform.openai.com/)에서 API 키 발급
- 권장 모델: `gpt-4o-mini` (빠름·저렴), `gpt-4o` (고품질)

### Google (Gemini)
- [Google AI Studio](https://aistudio.google.com/)에서 API 키 발급
- 권장 모델: `gemini-2.0-flash` (빠름), `gemini-1.5-pro` (고품질)

### LM Studio (로컬)
- [LM Studio](https://lmstudio.ai/)를 설치하고 모델을 로드한 뒤 로컬 서버 실행
- Base URL: `http://localhost:1234/v1` (기본값)
- 모델명: LM Studio에 로드된 모델명 그대로 입력
- API 키: 입력하지 않아도 됩니다

---

## 파일 구조

```
0323_Article_Translator/
├── main.py                  # FastAPI 앱 진입점
├── .env                     # 환경변수 (gitignore 처리됨)
├── .env.example             # 환경변수 예시
├── .gitignore
├── core/
│   ├── models.py            # Pydantic 데이터 모델
│   ├── pdf_parser.py        # PDF 텍스트 추출 및 구조 분석
│   ├── chunker.py           # 토큰 기반 청크 분할
│   ├── translator.py        # 멀티 프로바이더 번역 클라이언트
│   └── assembler.py         # 비동기 번역 파이프라인
├── api/
│   ├── job_store.py         # 인메모리 작업 상태 관리
│   └── routes.py            # HTTP 엔드포인트 및 SSE
├── static/
│   ├── index.html           # 단일 페이지 앱
│   ├── style.css            # 스타일
│   └── app.js               # 프론트엔드 로직
└── uploads/                 # 임시 PDF 저장 (번역 후 자동 삭제)
```

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/upload` | PDF 업로드 및 번역 작업 시작 |
| `GET` | `/api/progress/{job_id}` | SSE 실시간 진행 상황 스트림 |
| `GET` | `/api/result/{job_id}` | 전체 번역 결과 JSON |

---

## 주의 사항

- 스캔된 이미지 PDF(텍스트 레이어 없음)는 번역할 수 없습니다. OCR 처리 후 사용해주세요.
- 업로드된 PDF는 번역 완료 후 서버에서 자동으로 삭제됩니다.
- API 키는 서버로 전송되어 번역 요청에 사용되며, 저장되지 않습니다. 로컬에서 실행하는 경우에만 사용하세요.
