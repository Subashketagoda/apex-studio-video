# ApexGen Studio Video

A local-first Python/Streamlit studio for researching a topic, drafting a YouTube Shorts script, generating narration, planning topic-specific scenes, reviewing visual assets, and rendering a vertical MP4.

## Important workflow

**Human scene approval is required by default.** A normal run creates the script, voiceover, timestamped scene plan, and visual assets, then pauses in **AWAITING_APPROVAL**. Open **Scene Review Studio**, inspect each scene, replace or edit unsuitable visuals, and approve every scene before choosing final render.

Only explicitly trusted callers that need an unattended render should pass `auto_approve_scenes=True`. The UI does not enable that option.

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10 or 3.11 recommended
- FFmpeg and FFprobe available on `PATH`
- Internet connection for research, cloud image fallbacks, and Edge TTS
- At least one LLM key for the best script-generation experience (Gemini or OpenAI)
- Optional Pexels API key for stock video

The current Intel integrated-graphics workflow intentionally avoids heavy local CUDA-only video diffusion models. AI still images with local FFmpeg camera motion and stock/archival fallbacks are more realistic for low-VRAM machines; this is not the same as local text-to-video diffusion.

## Install on Windows

1. Install Python and FFmpeg. Confirm both are on PATH:

   ```powershell
   python --version
   ffmpeg -version
   ffprobe -version
   ```

2. Open PowerShell in the project folder and create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Create your local environment file and add whichever API keys you have:

   ```powershell
   Copy-Item .env.example .env
   ```

   Keep `.env`, YouTube credentials, and OAuth tokens private. Never commit real keys.

4. Start the app:

   ```powershell
   streamlit run web/app.py
   ```

Streamlit prints a local URL, usually `http://localhost:8501`.

## Run regression checks

Install pytest if needed, then run the approval and hardware/render smoke tests:

```powershell
pip install pytest
pytest -q tests/test_pipeline_approval_default.py tests/test_scene_approval_engine.py -k "not full_pipeline_render_approved_job"
```

Some legacy tests are integration scripts that call external APIs or generate real speech/video. They require network access, configured credentials where applicable, and working FFmpeg.

## Key folders

- `web/app.py` — Streamlit UI and Scene Review Studio
- `core/pipeline.py` — research-to-video orchestration and approval gate
- `core/scene_planner.py` / `core/visual_director.py` — timestamped scene planning and prompt direction
- `core/media_fetcher.py` / `core/ai_visual_generator.py` — stock, archival, and AI visual acquisition
- `core/video_editor.py` / `core/subtitles.py` — final vertical video, audio, and captions
- `core/job_manager.py` — persistent jobs and per-scene approval state
- `tests/` — regression and integration checks

## Troubleshooting

- **Final render is blocked:** approve every scene in Scene Review Studio; editing a prompt or replacing a clip resets that scene to pending.
- **AI image generation is unavailable:** check network access and provider rate limits; the pipeline can use archival or designed motion-graphic fallbacks.
- **FFmpeg/FFprobe not found:** install FFmpeg and restart the terminal so PATH is refreshed.
- **LLM setup:** add `GEMINI_API_KEY` or `OPENAI_API_KEY` to your local `.env` file.
