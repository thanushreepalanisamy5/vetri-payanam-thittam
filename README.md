# ComicCraft - AI Comic Story Creator

Type a story idea, pick a character, setting, tone and art style, and ComicCraft writes a 5-panel comic
(Gemini), draws every panel (Stable Diffusion), shows a preview in the browser and exports a PDF.

```
Browser form -> FastAPI -> Gemini Flash (outline) -> Gemini Pro (story + dialogue)
             -> Stable Diffusion (5 images) -> layout_builder -> exporters (PDF) -> preview / download
```

## 1. Prerequisites

- **Python 3.10 or newer** (check with `python --version`)
- **VS Code** with the **Python** extension (and optionally *Python Debugger*)
- A free **Gemini API key**: https://aistudio.google.com/apikey
- For real image generation: ~6 GB free disk space (model download) and ideally an NVIDIA GPU.
  CPU works too but each image takes roughly 1-3 minutes.

## 2. Open the project in VS Code

1. `File -> Open Folder...` and select the `comiccraft` folder.
2. Open a terminal: `Terminal -> New Terminal` (make sure it is in the project root).

## 3. Create a virtual environment and install dependencies

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `cmd` and `.venv\Scripts\activate.bat`.

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then install (both systems):
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **NVIDIA GPU?** Install the CUDA build of PyTorch *before* the command above, using the selector at
> https://pytorch.org/get-started/locally/ (for example `pip install torch --index-url https://download.pytorch.org/whl/cu121`).
> Without it, pip installs the CPU build.

VS Code will usually offer to use the new `.venv`. If not: `Ctrl+Shift+P` -> **Python: Select Interpreter** -> pick `.venv`.

## 4. Add your API keys

Copy `.env.example` to `.env` (same folder) and edit it:

```
GEMINI_API_KEY=paste_your_key_here
IMAGE_BACKEND=placeholder      # start with this for a quick first test
```

Set `IMAGE_BACKEND=diffusers` when you want real Stable Diffusion images. The first generation downloads
the model (about 4 GB) and loads it - this is slow once, then faster. `HF_API_KEY` is optional.

## 5. Run the app

Option A - terminal (from the project root, venv active):
```bash
uvicorn app.main:app --reload
```
Option B - VS Code: open the **Run and Debug** panel (`Ctrl+Shift+D`), choose **ComicCraft: FastAPI (uvicorn)** and press **F5**.

Open:
- App: http://127.0.0.1:8000
- Interactive API docs: http://127.0.0.1:8000/docs
- Configuration check: http://127.0.0.1:8000/health (shows whether your key is set and which backend is active)

## 6. Use it

1. Fill in the form (the defaults give a fox in an enchanted forest) and click **Generate Comic**.
2. Wait for the preview page (seconds with `placeholder`, minutes with real Stable Diffusion).
3. Click **Download Your Comic as PDF** - you are taken to the export-success page.
4. Change tone/style (e.g. *funny* + *comic book*) and generate again to iterate.

## 7. Test it

**Automated tests** (no API key, GPU or internet needed - Gemini is mocked and images use the placeholder backend):
```bash
pip install -r requirements-dev.txt
pytest -v
```
Or use VS Code's **Testing** panel (beaker icon) - pytest is already configured in `.vscode/settings.json`.

**Manual checks**

| What | How |
|---|---|
| Server is up and configured | open `/health` |
| Image generation only | open `http://127.0.0.1:8000/test-image?prompt=a robot&style=pixel art` |
| Full JSON API | see below |
| Full browser flow | use the form on `/` |

```bash
curl -X POST http://127.0.0.1:8000/generate-comic/json \
  -H "Content-Type: application/json" \
  -d '{"prompt":"A brave fox explores an enchanted forest","character_name":"Finn","setting":"forest","tone":"funny","style":"comic book"}'
```
The response contains `layout` (5 panels) and `pdf_path` (open it at `http://127.0.0.1:8000<pdf_path>`).
PowerShell users can do the same in the `/docs` page via **Try it out**.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `GEMINI_API_KEY is not set` | create `.env` from `.env.example` and restart uvicorn |
| `None of the configured Gemini models exist` (404) | Google retired every model in your chain. Set `GEMINI_FLASH_MODELS` / `GEMINI_PRO_MODELS` in `.env` to models listed at https://ai.google.dev/gemini-api/docs/models |
| `503 UNAVAILABLE` / `429` / quota errors | Google's model is overloaded or rate-limited. The app already retries and falls back through the model chain (`GEMINI_FLASH_MODELS` / `GEMINI_PRO_MODELS`); if every model is busy you get a 503 page, so just try again in a minute. |
| `torch/diffusers are not installed` | run `pip install -r requirements.txt` inside the active `.venv`, or use `IMAGE_BACKEND=placeholder` |
| Very slow images | normal on CPU. Lower `SD_SIZE=384` and `SD_STEPS=15` in `.env`, or use a GPU. |
| Out of GPU memory | set `SD_SIZE=384`, close other GPU programs |
| Image is completely black | the Stable Diffusion safety filter triggered; reword the story prompt |
| Port 8000 busy | `uvicorn app.main:app --reload --port 8001` |
| Edited `.env` but nothing changed | restart the server (the reloader only watches code files) |

## 9. Project structure

```
comiccraft/
├── app/
│   ├── main.py            FastAPI app, static files, startup
│   ├── routes.py          /, /generate, /generate-comic/json, /export-success, /test-image, /health
│   ├── config.py          paths, env vars, model names
│   ├── gemini_client.py   shared Gemini client (retries, clear errors)
│   ├── gemini_flash.py    generate_outline()  - 5-panel JSON outline
│   ├── gemini_pro.py      generate_story()    - narration + dialogue
│   ├── image_generator.py generate_image()    - Stable Diffusion / placeholder
│   ├── layout_builder.py  build_comic_layout()
│   ├── exporters.py       save_pdf()          - FPDF
│   └── schemas.py         PromptRequest (Pydantic)
├── templates/             index.html, comic_preview.html, export_success.html
├── static/                panels/ (images), exports/ (PDFs), fonts/ (DejaVu), images/ (background)
├── tests/                 pytest suite
├── .vscode/               launch + pytest settings
├── .env.example           copy to .env
├── requirements.txt       runtime dependencies
└── requirements-dev.txt   + pytest, httpx
```

## 10. Where this differs from the original documentation (and why)

- **Gemini models**: the docs name `gemini-1.5-flash` / `gemini-1.5-pro`. Google has shut those down (requests return 404),
  so each step uses an ordered fallback chain of stable models (outline starts with `gemini-3.5-flash-lite`, story with `gemini-3.8-flash`). If a model is overloaded (503) or retired (404) the next one is used automatically. Configure the chains in `.env`.
- **Gemini SDK**: uses the current `google-genai` package instead of the deprecated `google-generativeai`.
- **Stable Diffusion repo**: `runwayml/stable-diffusion-v1-5` was removed from Hugging Face; the default is the community
  mirror `stable-diffusion-v1-5/stable-diffusion-v1-5` (override with `SD_MODEL_ID`).
- **PDF library**: `fpdf2` (maintained fork, same `from fpdf import FPDF` import) replaces the legacy `fpdf`.
- **Lazy model loading** and a `placeholder` image backend so the app starts instantly and can be tested without a GPU.
- **Errors** from Gemini / image generation are shown on the form page instead of a raw 500 JSON.
- Fonts: `DejaVuSans.ttf` and `DejaVuSans-Oblique.ttf` are bundled in `static/fonts/` (DejaVu fonts are freely redistributable).
