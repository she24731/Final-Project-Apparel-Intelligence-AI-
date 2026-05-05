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
2. **Style (main)**: enter context → click **Recommend outfit** → view a single clean outfit card
3. **Buy Analyzer**: enter a candidate item → get a deterministic Buy/Maybe/No Buy result
4. **Content**: generate a script/caption + runway preview (placeholder if no provider)
5. **Chat**: use the bottom-right chat button anytime for quick tweaks and alternatives

### Simulation (Gemini Reel Lab) — 3-step workflow

This is the demo path for multi-scene media generation (vertical reel preview).

**Step 1: Wardrobe → Style**

- Upload garment images in **Wardrobe**
- Go to **Style** → click **Recommend outfit**
  - This produces the recommended outfit **garment anchors** (stored as `uploads/...`)

**Step 2: Content → Simulation → Generate scenes**

1. Upload a **Face anchor** (selfie). This is the identity reference.
2. Enter a one-sentence **Movie idea** (concept + vibe).
3. Click **Generate scenes**.

What happens under the hood:

- The backend analyzes anchors and builds a **premise (structured JSON)** for the run:
  - `premise.json`, `story_state.json`, and `anchors_analysis.json` are written under `backend/data/reel_runs/<job_id>/`
- The reel is generated as a **fixed 4-scene** storyboard for predictable grading/demo flow.
- For each scene, the backend produces a per-scene **description** (JSON beat) and generates a new still image:
  - Scene outputs are saved under `backend/data/generated_media/`
  - The UI shows either the still (`generated_image_path`) or a short preview MP4 (`generated_video_path`)

**Step 3: Generate video**

- Click **Generate video** to render/mux the scene sequence into a single MP4 (provider-dependent).

### Scene conditioning logic (identity + outfit + continuity)

Each scene is generated with:

- **Face anchor** (identity; always highest priority)
- **Garment anchors** (outfit constraints from the recommended outfit)
- **Premise JSON** (shared story spine across all scenes)
- **Description JSON** (per-scene beat; updated as scenes are generated)
- **Prior scene context** (for scenes 2–4, continuity is enforced using prior scene description and, when possible, the prior scene still)

### Reference image limits (Gemini constraint)

Gemini image generation can have implicit limits on how many **reference images** can be attached, and flat-lay garment photos can cause “composition hugging” (outputs that resemble catalog shots or appear warped when constraints conflict).

You can control the max attached reference images with:

```env
MEDIA_MAX_REF_IMAGES=3
```

Priority rules when reference images are limited:

- If limit = 1: **Face anchor only**
- If limit = 2: **Face anchor + prior generated frame** (scene 2+) or **Face + 1 garment** (scene 1)
- If limit = 3: **Face anchor + prior generated frame + 1 garment** (scene 2+) or **Face + 2 garments** (scene 1)

If you need **Face + 2 garments + prior generated frame** as attached references for scenes 2–4, set:

```env
MEDIA_MAX_REF_IMAGES=4
```

Notes:
- The face anchor is always prioritized first for identity stability.
- For scenes 2–4, using the **previous generated frame** is often more stable than attaching multiple flat-lay garment references.

### Suggested “2-minute demo” (for graders)

1) Go to **Wardrobe** and upload **3–6 items** (ideally: top, bottom, shoes, outerwear).  
2) Go to **Style** and set:
- occasion: `work_presentation`
- weather: `mild_clear` (or `cold_rain`)
- vibe: `quiet_luxury`
Then click **Recommend outfit**.  
3) Go to **Buy Analyzer**, pick a candidate (e.g., shoes in brown), click **Analyze purchase**.  
4) Go to **Content**, generate a script and runway preview.  
5) Click the **Chat** button (bottom-right) and ask: “Give me a rain-safe alternative.”

### Accepted upload formats

- **Images**: JPG/JPEG, PNG, WebP, HEIC/HEIF, AVIF, GIF  
- **Max size**: 10MB

---

## How the MVP works (architecture)

### Frontend
- **React + TypeScript + Vite + Tailwind**
- Pages: `Wardrobe`, `Style`, `Buy Analyzer`, `Content`
- Floating: bottom-right **Chat widget**
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
MEDIA_MAX_REF_IMAGES=3
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

