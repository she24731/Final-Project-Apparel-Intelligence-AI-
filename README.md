# Apparel Intelligence (AI) — Yale Course MVP

Apparel Intelligence is a **demo-ready, agentic wardrobe intelligence system** built for a Yale course on Generative AI and Social Media.

It helps you:
- **Ingest** wardrobe items from images (metadata + embeddings)
- **Recommend** an outfit given context (occasion / weather / vibe)
- **Analyze** whether a new item is worth buying (Buy / Maybe / No Buy)
- **Generate content** (short script + runway-style media prompt / preview)

This repo is designed to be **reliable on a laptop**:
- Works with **deterministic mock/fallback logic** when AI APIs are unavailable
- Uses **environment variables** for all secrets (no keys in source control)

---

## Quick start (local)

### 1) Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: copy env template and add your Gemini key
cp ../.env.example .env

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health:

```bash
curl http://127.0.0.1:8000/health
```

### 2) Frontend (React + Vite + Tailwind)

```bash
cd ../frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:
- Frontend: `http://127.0.0.1:5173/`
- Backend: `http://127.0.0.1:8000/`

---

## Product flow (what graders should click)

The UI is intentionally guided to reduce cognitive load:

1. **Wardrobe**: upload a few garment images (adds items to the digital wardrobe)
2. **Style**: enter context → click **Recommend outfit** → view a single clean outfit card
3. **Buy Analyzer**: enter a candidate item → get a deterministic Buy/Maybe/No Buy result
4. **Content**: generate a script/caption + runway preview (placeholder if no provider)
5. **Chat**: dedicated stylist chat page (demo-safe; backend chat endpoint can be added later)

---

## How the MVP works (architecture)

### Frontend
- **React + TypeScript + Vite + Tailwind**
- Pages: `Wardrobe`, `Style`, `Buy Analyzer`, `Content`, `Chat`
- Uses a lightweight API client (`src/lib/api.ts`)

### Backend
- **FastAPI** with typed Pydantic schemas
- Deterministic fallbacks for all critical features

Key modules:
- `app/schemas/`: request/response contracts
- `app/routers/`: HTTP endpoints
- `app/services/`: deterministic business logic
- `app/agents/`: PydanticAI agents with typed outputs (optional)
- `app/retrieval/`: **local vector retrieval** over wardrobe + style KB (no web search)
- `app/media/`: storyboard → prompt pipeline + provider abstraction (placeholder mode supported)

---

## Environment variables (no secrets in git)

Create `backend/.env` from the template:

```env
GEMINI_API_KEY=PASTE_YOUR_REAL_KEY_HERE
GEMINI_MODEL=gemini-2.5-flash
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
FRONTEND_API_BASE_URL=http://127.0.0.1:8000
MEDIA_PROVIDER=mock
```

Notes:
- If `GEMINI_API_KEY` is blank, the system uses **deterministic fallbacks** for a stable demo.
- Media generation is a **provider abstraction**; placeholder mode is always available.

---

## Backend API (MVP)

- `GET /health`
- `POST /ingest-garment` (multipart: `file`, optional `hints`)
- `POST /recommend-outfit` (JSON)
- `POST /analyze-purchase` (JSON)
- `POST /generate-script` (JSON)
- `POST /generate-video` (JSON; placeholder/provider abstraction)

---

## Demo notes / reliability

- If the backend is not reachable, the frontend will **quietly fall back** to demo results so the UI remains usable.
- No keys are committed. `.env` is ignored by git.

