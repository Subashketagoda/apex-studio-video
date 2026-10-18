import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from core.config import AppConfig
from core.schemas import ShortsScript, VisualSegment, FactualClaim
from core.script_generator import ScriptGenerator
from core.tts_engine import TTSEngine, AudioResult
from core.media_fetcher import MediaFetcher
from core.video_editor import VideoEditor
from core.youtube_publisher import YouTubePublisher
from core.pipeline import ShortsPipeline, PipelineResult
from core.job_manager import JobManager, JobRecord
from core.researcher import ResearchService
from core.video_providers import HardwareDetector, AIVideoEngine
from core.schemas import ScenePlanItem


# Page Setup
st.set_page_config(
    page_title="ApexGen Viral Shorts AI Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Glassmorphic Modern Styling
st.markdown("""
<style>
    .main { background-color: #0b0f19; }
    .stApp {
        background: linear-gradient(135deg, #0b0f19 0%, #111827 50%, #0d1322 100%);
        color: #f3f4f6;
    }
    .metric-card {
        background: rgba(31, 41, 55, 0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .fact-card {
        background: rgba(17, 24, 39, 0.7);
        border-left: 4px solid #10b981;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .highlight-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .pill-green { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #059669; }
    .pill-yellow { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #d97706; }
    .pill-blue { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #2563eb; }
    .pill-purple { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid #9333ea; }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)

# State initialization
if "oneclick_result" not in st.session_state:
    st.session_state.oneclick_result = None
if "step_script" not in st.session_state:
    st.session_state.step_script = None
if "step_audio" not in st.session_state:
    st.session_state.step_audio = None
if "step_clips" not in st.session_state:
    st.session_state.step_clips = None
if "step_final_video" not in st.session_state:
    st.session_state.step_final_video = None

# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚡ Studio Configuration")
    
    llm_provider = st.selectbox(
        "🧠 LLM Engine",
        options=["gemini", "openai"],
        index=0 if AppConfig.DEFAULT_LLM_PROVIDER == "gemini" else 1,
        help="Grounded in real-world Wikipedia and primary source verification"
    )

    voice_options = {
        "Christopher (US - Deep, Authoritative)": "en-US-ChristopherNeural",
        "Guy (US - Narrative, Discovery)": "en-US-GuyNeural",
        "Jenny (US - Warm, Documentary)": "en-US-JennyNeural",
        "Brian (UK - Scholarly, History)": "en-GB-BrianNeural",
        "Sonia (UK - Sophisticated)": "en-GB-SoniaNeural"
    }
    voice_label = st.selectbox("🎙️ Voice Character", options=list(voice_options.keys()), index=0)
    selected_voice = voice_options[voice_label]

    st.markdown("---")
    st.markdown("### 🎵 Audio & BGM Ducking")
    bgm_options = {
        "Dark Suspense / Mystery 🕵️": "cinematic_drone",
        "Cyberpunk / Science Energy ⚡": "cyberpunk_energy",
        "Lo-Fi / Documentary ☕": "chill_lofi",
        "None (Voiceover Only) 🔇": "none"
    }
    selected_bgm_label = st.selectbox("Soundtrack Mood", options=list(bgm_options.keys()), index=0)
    selected_bgm = bgm_options[selected_bgm_label]
    bgm_volume = st.slider("BGM Level (Auto-Ducked during speech)", 0.08, 0.40, 0.20, 0.02)

    st.markdown("---")
    st.markdown("### 🎬 Visual Engine")
    visual_engine_options = {
        "🤖 AI Cinematic Visuals (FLUX.1 SOTA AI + Ken-Burns)": "ai_cinematic",
        "🔀 Hybrid (FLUX.1 AI First, Stock Video Fallback)": "hybrid",
        "🎥 Stock Video Only (Pexels / Pixabay)": "stock",
        "📊 Topic Infographic Cards (Pillow 3D)": "infographic"
    }
    selected_visual_label = st.selectbox(
        "Visual Generation Mode",
        options=list(visual_engine_options.keys()),
        index=0,
        help="AI Cinematic generates 100% topic-matched photorealistic 9:16 visuals with smooth camera movement."
    )
    selected_visual_mode = visual_engine_options[selected_visual_label]

    st.markdown("---")
    st.markdown("### 🎨 Subtitles & Branding")
    sub_styles = {
        "🟡 MrBeast Active Gold": "mrbeast",
        "🟢 Alex Hormozi Punchy Green": "hormozi",
        "🔴 Red Alert Crimson": "red_alert",
        "🔵 Cyber Cyan Neon": "cyber_cyan"
    }
    sub_style_label = st.selectbox("Subtitle Styling", options=list(sub_styles.keys()), index=0)
    selected_sub_style = sub_styles[sub_style_label]
    watermark_input = st.text_input("🏷️ Channel Watermark", placeholder="e.g. @ApexGenShorts", value="")

    st.markdown("---")
    st.markdown("### 🔑 System Health")
    AppConfig.reload()
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Gemini")
        st.markdown(f'<span class="highlight-pill {"pill-green" if AppConfig.GEMINI_API_KEY else "pill-yellow"}">{"Active" if AppConfig.GEMINI_API_KEY else "Fallback"}</span>', unsafe_allow_html=True)
        st.caption("Pexels")
        st.markdown(f'<span class="highlight-pill {"pill-green" if AppConfig.PEXELS_API_KEY else "pill-blue"}">{"Active" if AppConfig.PEXELS_API_KEY else "Pixabay/Pillow"}</span>', unsafe_allow_html=True)
    with c2:
        st.caption("Edge-TTS")
        st.markdown('<span class="highlight-pill pill-green">Free Neural</span>', unsafe_allow_html=True)
        st.caption("FFmpeg 9.0")
        st.markdown('<span class="highlight-pill pill-green">Hardware Ready</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🖥️ Hardware & AI Inference")
    hw_info = HardwareDetector.detect()
    st.caption(f"**GPU**: {hw_info['gpu_name']}")
    st.caption(f"**RAM**: {hw_info['system_ram_gb']} GB | **Free Disk**: {hw_info['free_disk_space_gb']} GB")
    if not hw_info["has_cuda"]:
        st.markdown('<span class="highlight-pill pill-yellow">Intel iGPU (No CUDA)</span>', unsafe_allow_html=True)
        st.caption("⚠️ Heavy local video models (Wan2.1 / LTX) blocked to prevent OOM crash.")
    else:
        st.markdown('<span class="highlight-pill pill-green">CUDA Dedicated</span>', unsafe_allow_html=True)

    with st.expander("🌐 Remote Video API Setup", expanded=False):
        remote_key = st.text_input("Remote Video API Key", value=os.environ.get("REMOTE_VIDEO_API_KEY", ""), type="password", key="remote_key_input")
        if remote_key:
            os.environ["REMOTE_VIDEO_API_KEY"] = remote_key
            st.success("Remote API Key configured!")
        else:
            st.caption("Disabled by default. Provide key if using external video models.")


# Main Application Interface
st.markdown("""
# ⚡ ApexGen Viral Shorts AI Studio
**Autonomous 9:16 Vertical Documentary Pipeline with Verified Factual Research & TikTok Subtitles**
""")

tab_oneclick, tab_review, tab_batch, tab_step, tab_history, tab_docs = st.tabs([
    "🚀 One-Click Auto Studio",
    "🎬 Scene Review Studio",
    "⚡ Bulk Batch Studio",
    "🛠️ Step-by-Step Studio",
    "📊 Job History & Logs",
    "📖 Setup & Docs"
])

# -------------------------------------------------------------------
# TAB 1: ONE-CLICK AUTOMATED STUDIO
# -------------------------------------------------------------------
with tab_oneclick:
    st.markdown("### 1. Configure Video Subject")

    quick_topics = [
        "Coca-Cola vs Pepsi",
        "Black holes",
        "Eiffel Tower history",
        "Why Airplanes Never Fly Straight",
        "How Banks Create Money From Nothing"
    ]
    st.caption("Click any verified topic or type your custom subject:")
    q_cols = st.columns(len(quick_topics))
    chosen_topic = None
    for idx, t in enumerate(quick_topics):
        if q_cols[idx].button(f"📌 {t}", key=f"qtop_{idx}"):
            st.session_state.custom_topic_input = t
            st.rerun()

    input_topic = st.text_input(
        "🎯 Video Topic / Subject",
        key="custom_topic_input",
        value=st.session_state.get("custom_topic_input", "Coca-Cola vs Pepsi"),
        placeholder="e.g. Coca-Cola vs Pepsi, Black holes, Eiffel Tower history..."
    )

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        narrative_tone = st.selectbox(
            "🎭 Narrative Tone",
            options=["Suspenseful & Dramatic", "Fast-Paced & Curious", "Mind-Blowing & Scientific", "Historical Clash"],
            index=0
        )
    with col_t2:
        target_duration_choice = st.selectbox(
            "⏱️ Target Duration",
            options=["🔥 Balanced (~45s - 50s)", "⚡ Fast (~30s - 35s)", "📖 Full Story (~55s - 60s)"],
            index=0
        )

    if st.button("🚀 Render Verified Viral Short", type="primary", use_container_width=True):
        if not input_topic.strip():
            st.error("Please enter a valid video topic.")
        else:
            prog_bar = st.progress(0.0)
            status_box = st.empty()
            log_container = st.expander("📋 Live Pipeline Logs", expanded=True)
            log_text_area = log_container.empty()
            live_logs = []

            def on_progress(msg: str, frac: float):
                status_box.info(f"⏳ **{int(frac*100)}%**: {msg}")
                prog_bar.progress(min(max(float(frac), 0.0), 1.0))
                live_logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                log_text_area.code("\n".join(live_logs[-8:]), language="text")

            try:
                pipeline = ShortsPipeline(
                    llm_provider=llm_provider,
                    tts_provider="edge-tts",
                    voice=selected_voice
                )
                res = pipeline.run(
                    topic=input_topic.strip(),
                    tone=narrative_tone,
                    duration_pref=target_duration_choice,
                    progress_callback=on_progress,
                    bgm_track=selected_bgm,
                    bgm_volume=bgm_volume,
                    subtitle_style=selected_sub_style,
                    watermark_text=watermark_input,
                    visual_source=selected_visual_mode
                )
                st.session_state.oneclick_result = res
                st.success("🎉 Video successfully produced, burned, and validated!")
            except Exception as e:
                st.error(f"Render encountered error: {e}")

    # Render Result Display
    if st.session_state.oneclick_result:
        res: PipelineResult = st.session_state.oneclick_result
        st.markdown("---")
        st.markdown("### 🎬 Production Output & Verification Report")
        
        c_left, c_right = st.columns([1.2, 1.8])
        with c_left:
            st.markdown("#### 📱 Video Preview (1080x1920)")
            if Path(res.final_video_path).exists():
                st.video(res.final_video_path)
                st.caption(f"📁 Path: `{res.final_video_path}`")
            else:
                st.warning("Video file not found on disk.")

        with c_right:
            st.markdown("#### 📝 Script & Verified Facts")
            st.markdown(f"**Title**: {res.script.title}")
            st.markdown(f"**Hook (0-3s)**: *\"{res.script.hook}\"*")
            st.markdown(f"**Spoken Duration**: **{res.audio_duration:.1f}s** (~{len(res.script.voiceover_text.split())} words)")
            
            with st.expander("🎙️ Full Voiceover Script", expanded=False):
                st.write(res.script.voiceover_text)

            st.markdown("#### 🔍 Primary Research Sources & Claims")
            for cl in res.script.factual_claims:
                st.markdown(f"""
                <div class="fact-card">
                    <strong>{cl.claim}</strong><br/>
                    <small>Source: <a href="{cl.source_url}" target="_blank">{cl.source_name}</a> | Status: <span class="highlight-pill pill-green">{cl.verification_status.upper()}</span></small>
                </div>
                """, unsafe_allow_html=True)

            if res.validation_report:
                st.markdown("#### 🛡️ FFprobe Container Quality Check")
                v_rep = res.validation_report
                st.markdown(f"""
                - **Resolution**: `{v_rep.get('width')}x{v_rep.get('height')}` (Standard Vertical 9:16)
                - **Duration**: `{v_rep.get('duration')}s`
                - **File Size**: `{v_rep.get('size_mb')} MB`
                - **Video Codec**: `{v_rep.get('video_codec')}` | **Audio**: `{v_rep.get('audio_codec')}`
                """)

            if hasattr(res, "scene_plan") and res.scene_plan:
                st.markdown("#### 📋 Timestamped Scene Plan & Visual Sources")
                for sc in res.scene_plan.scenes:
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.5); padding: 10px 14px; border-radius: 8px; margin-bottom: 6px; border-left: 3px solid #3b82f6;">
                        <strong>Scene #{sc.scene_order} ({sc.start_time:.1f}s - {sc.end_time:.1f}s)</strong>: {sc.main_subject}<br/>
                        <small><em>"{sc.narration_segment}"</em></small><br/>
                        <small style="color: #94a3b8;">Tier: <strong>{sc.selected_asset_source or 'standard'}</strong> | Camera: {sc.camera_movement} | Status: <span style="color: #10b981;">{sc.validation_status}</span></small>
                    </div>
                    """, unsafe_allow_html=True)

            if hasattr(res, "qc_report") and res.qc_report:
                qc = res.qc_report
                with st.expander(f"🛡️ Quality Control & Asset Relevance Report ({len(qc.rejections)} rejected candidates)", expanded=False):
                    st.markdown(f"**Passed Scenes**: {qc.passed_scenes}/{qc.total_scenes} | **Overall Status**: {'✅ PASSED' if qc.overall_pass else '⚠️ REVIEW'}")
                    if qc.rejections:
                        st.markdown("**Rejected Asset Log**:")
                        for rej in qc.rejections:
                            st.markdown(f"- **Scene #{rej.scene_order}** ({rej.candidate_source}): Rejected `{rej.candidate_identifier}` — *{rej.rejection_reason}* (Dominant subject: `{rej.detected_dominant_subject}`)")
                    else:
                        st.markdown("No candidate assets violated relevance constraints.")

            if res.validation_report and "extracted_frames" in res.validation_report:
                frames = res.validation_report["extracted_frames"]
                if frames:
                    st.markdown("#### 🖼️ Representative Video Frame Inspection (10% - 90%)")
                    cols = st.columns(len(frames))
                    for idx, fr in enumerate(frames):
                        with cols[idx]:
                            if Path(fr["frame_path"]).exists():
                                st.image(fr["frame_path"], caption=f"{int(fr['fraction']*100)}% ({fr['timestamp_sec']}s)")
                                st.caption(f"Bright: {fr['average_brightness']}")


# -------------------------------------------------------------------
# TAB 2: SCENE REVIEW STUDIO & APPROVAL GATE
# -------------------------------------------------------------------
with tab_review:
    st.markdown("### 🎬 Scene Review Studio & Approval Gate")
    st.caption("Inspect, play, regenerate, replace, and approve every scene clip before rendering. Final export is strictly blocked until all scenes are approved.")

    # 1. Hardware & Policy Status Banner
    hw = HardwareDetector.detect()
    with st.expander("ℹ️ Hardware Environment & Generation Policies", expanded=False):
        st.markdown(f"**Detected Hardware**: `{hw['gpu_name']}` | **System RAM**: `{hw['system_ram_gb']} GB` | **Free Disk**: `{hw['free_disk_space_gb']} GB`")
        st.markdown(f"**Hardware Summary**: {hw['hardware_summary']}")
        st.markdown("""
        - **Local Video Diffusion Policy**: Wan 2.1 and LTX-Video require discrete CUDA GPUs with >=12GB VRAM. They are disabled here to prevent memory overflow and swap lockup.
        - **Provenance Tagging**: All animated still footage is explicitly marked as `[ANIMATED_STILL_FALLBACK]`, and simulated test footage is marked `[SIMULATED_TEST_CLIP]`. Unrelated footage is never silently substituted.
        - **Human Approval Gate**: Video export is strictly blocked until every scene is marked `APPROVED`.
        """)

    # 2. Select Project / Job to Review
    jobs_list = JobManager.list_jobs(limit=25)
    jobs_with_scenes = [j for j in jobs_list if j.scene_plan_data and j.scene_plan_data.get("scenes")]

    if not jobs_with_scenes:
        st.info("No active scene plans found. Generate a Short in Tab 1 or Tab 3 to plan scenes!")
    else:
        job_options = {f"{j.topic} ({j.job_id}) - {j.status}": j.job_id for j in jobs_with_scenes}
        selected_job_label = st.selectbox("Select Project for Scene Review:", list(job_options.keys()), index=0)
        selected_job_id = job_options[selected_job_label]
        current_job = JobManager.get_job(selected_job_id)

        if current_job and current_job.scene_plan_data:
            scene_data = current_job.scene_plan_data
            scenes = scene_data.get("scenes", [])
            all_approved, unapproved = JobManager.are_all_scenes_approved(selected_job_id)

            # Overall Approval Summary
            approved_count = len(scenes) - len(unapproved)
            progress_val = approved_count / len(scenes) if scenes else 0.0

            st.markdown("#### 🛡️ Project Approval Status")
            col_ap1, col_ap2 = st.columns([3, 1])
            with col_ap1:
                st.progress(progress_val)
                st.caption(f"Approved: **{approved_count} / {len(scenes)} scenes** ({int(progress_val * 100)}%)")
            with col_ap2:
                if all_approved:
                    st.success("🟢 READY TO RENDER")
                else:
                    st.warning(f"🛑 {len(unapproved)} PENDING")

            if not all_approved:
                unapp_str = ", ".join(f"Scene #{o}" for o in unapproved)
                st.warning(f"⚠️ **Rendering Blocked**: The following scenes require review and approval before final export: **{unapp_str}**")
            else:
                st.success("✅ **All scenes approved!** You can proceed to render the final synchronized vertical short below.")

            # Bulk Actions
            b_c1, b_c2 = st.columns(2)
            with b_c1:
                if st.button("✅ Approve All Remaining Scenes", use_container_width=True):
                    for sc in scenes:
                        JobManager.update_scene_approval(selected_job_id, sc.get("scene_order", 1), "APPROVED")
                    st.rerun()
            with b_c2:
                if st.button("🔄 Reset All Scenes to Pending", use_container_width=True):
                    for sc in scenes:
                        JobManager.update_scene_approval(selected_job_id, sc.get("scene_order", 1), "PENDING")
                    st.rerun()

            st.markdown("---")
            st.markdown("#### 📋 Scene Timeline & Card Review")

            # Loop through scenes
            for idx, sc in enumerate(scenes):
                order = sc.get("scene_order", idx + 1)
                app_status = sc.get("approval_status", "PENDING")
                status_color = "🟢" if app_status == "APPROVED" else ("🔴" if app_status == "REJECTED" else "🟡")
                
                with st.expander(f"{status_color} Scene #{order} ({sc.get('start_time', 0):.1f}s - {sc.get('end_time', 0):.1f}s): {sc.get('main_subject', 'Scene')} [{app_status}]", expanded=(app_status != "APPROVED")):
                    c_video, c_details = st.columns([5, 7])

                    with c_video:
                        clip_path = sc.get("selected_asset_path")
                        if clip_path and Path(clip_path).exists():
                            st.video(clip_path)
                            prov_note = sc.get("validation_notes") or sc.get("selected_asset_source") or "standard"
                            st.caption(f"📁 Asset: `{Path(clip_path).name}`\n\nProvenance: `{prov_note}`")
                        else:
                            st.info("No video clip associated with this scene yet.")
                            if st.button(f"🎬 Generate Clip for Scene #{order}", key=f"gen_sc_{order}"):
                                with st.spinner(f"Generating clip for Scene #{order}..."):
                                    sc_item = ScenePlanItem.model_validate(sc)
                                    AIVideoEngine.generate_scene_clip(sc_item)
                                    JobManager.replace_scene_clip(selected_job_id, order, sc_item.selected_asset_path, reason="initial_generation")
                                    st.rerun()

                    with c_details:
                        st.markdown(f"**🗣️ Spoken Narration**: *\"{sc.get('narration_segment')}\"*")
                        st.markdown(f"**📐 Camera Direction**: {sc.get('shot_type')} | {sc.get('camera_movement')} | {sc.get('camera_angle')}")
                        st.markdown(f"**🎨 Lighting & Atmosphere**: {sc.get('lighting_atmosphere')}")
                        
                        # Editable positive and negative prompts
                        curr_pos = sc.get("positive_prompt") or sc.get("visual_description", "")
                        curr_neg = sc.get("negative_prompt") or ", ".join(sc.get("negative_constraints", []))
                        new_pos = st.text_area(f"Visual Generation Prompt (v{sc.get('prompt_version', 1)})", value=curr_pos, key=f"pos_text_{order}", height=80)
                        new_neg = st.text_input(f"Negative Visual Constraints", value=curr_neg, key=f"neg_text_{order}")

                        # Action Buttons
                        btn_col1, btn_col2, btn_col3 = st.columns(3)
                        with btn_col1:
                            if st.button("💾 Save Prompt", key=f"save_btn_{order}", use_container_width=True, help="Updates prompt and invalidates previous approval"):
                                JobManager.update_scene_prompt(selected_job_id, order, new_pos, new_neg)
                                st.info("Prompt updated. Approval reset to PENDING.")
                                st.rerun()
                        with btn_col2:
                            if st.button("🔄 Regenerate", key=f"regen_btn_{order}", use_container_width=True, help="Reruns generation and invalidates approval"):
                                with st.spinner(f"Regenerating Scene #{order}..."):
                                    sc_item = ScenePlanItem.model_validate(sc)
                                    sc_item.positive_prompt = new_pos
                                    sc_item.negative_prompt = new_neg
                                    new_clip = AIVideoEngine.generate_scene_clip(sc_item)
                                    JobManager.replace_scene_clip(selected_job_id, order, str(new_clip.resolve()), reason="regeneration")
                                    st.rerun()
                        with btn_col3:
                            if st.button("✅ Approve Scene", key=f"app_btn_{order}", type="primary" if app_status != "APPROVED" else "secondary", use_container_width=True):
                                JobManager.update_scene_approval(selected_job_id, order, "APPROVED")
                                st.rerun()

                        # Replacement and Rejection row
                        st.markdown("---")
                        rep_col, rej_col = st.columns(2)
                        with rep_col:
                            upload_file = st.file_uploader(f"📁 Replace Clip with Custom Video", type=["mp4", "mov"], key=f"upload_sc_{order}")
                            if upload_file is not None:
                                custom_dir = AppConfig.CACHE_DIR / "custom_clips"
                                custom_dir.mkdir(parents=True, exist_ok=True)
                                saved_path = custom_dir / f"custom_scene_{order}_{upload_file.name}"
                                saved_path.write_bytes(upload_file.read())
                                JobManager.replace_scene_clip(selected_job_id, order, str(saved_path.resolve()), reason="user_upload")
                                st.success("Custom clip attached! Approval reset to PENDING.")
                                st.rerun()

                        with rej_col:
                            rej_reason = st.text_input("Rejection Reason", key=f"rej_note_input_{order}", placeholder="e.g. Unrelated object, bad framing...")
                            if st.button("❌ Reject Scene", key=f"rej_btn_{order}", use_container_width=True):
                                JobManager.update_scene_approval(selected_job_id, order, "REJECTED", notes=rej_reason or "Rejected by reviewer.")
                                st.rerun()

            st.markdown("---")
            # 3. Final Render Button (Gated)
            st.markdown("#### 🚀 Final Video Rendering")
            if not all_approved:
                st.button(
                    "🚀 Render Approved Final Short (1080x1920 MP4)",
                    disabled=True,
                    use_container_width=True,
                    help="Rendering is blocked because one or more scenes are unapproved."
                )
                st.error("🛑 Rendering is BLOCKED. All scenes must be marked 'APPROVED' before export.")
            else:
                if st.button("🚀 Render Approved Final Short (1080x1920 MP4)", type="primary", use_container_width=True):
                    r_prog = st.progress(0.0)
                    r_status = st.empty()

                    def r_cb(msg: str, frac: float):
                        r_status.info(f"⏳ **{int(frac*100)}%**: {msg}")
                        r_prog.progress(min(max(float(frac), 0.0), 1.0))

                    try:
                        pipeline = ShortsPipeline()
                        rendered_video = pipeline.render_approved_job(
                            job_id=selected_job_id,
                            progress_callback=r_cb,
                            bgm_track=selected_bgm,
                            bgm_volume=bgm_volume,
                            subtitle_style=selected_sub_style,
                            watermark_text=watermark_input
                        )
                        r_status.success(f"🎉 Final Video Rendered: `{rendered_video.name}`")
                        st.video(str(rendered_video.resolve()))
                        st.balloons()
                    except Exception as ex:
                        r_status.error(f"Render failed: {ex}")


# -------------------------------------------------------------------
# TAB 3: BULK BATCH STUDIO
# -------------------------------------------------------------------
with tab_batch:
    st.markdown("### ⚡ Bulk Batch Video Production")
    st.caption("Queue multiple topics to generate back-to-back verified Shorts with automated job management.")

    batch_default_text = "Coca-Cola vs Pepsi\nBlack holes\nEiffel Tower history"
    batch_input = st.text_area(
        "Topics (One per line):",
        value=batch_default_text,
        height=130
    )

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        batch_tone = st.selectbox("Batch Tone", ["Suspenseful & Dramatic", "Fast-Paced & Curious", "Historical Clash"], key="batch_tone")
    with col_b2:
        batch_dur = st.selectbox("Batch Duration", ["🔥 Balanced (~45s - 50s)", "⚡ Fast (~30s - 35s)"], key="batch_dur")

    if st.button("🚀 Start Bulk Batch Processing", type="primary"):
        topics = [t.strip() for t in batch_input.splitlines() if t.strip()]
        if not topics:
            st.error("Please enter at least one topic.")
        else:
            st.info(f"Queued {len(topics)} topics for sequential production.")
            batch_container = st.container()
            
            for i, topic in enumerate(topics):
                with batch_container.expander(f"📦 Job #{i+1}: {topic}", expanded=True):
                    b_bar = st.progress(0.0)
                    b_status = st.empty()
                    
                    def batch_cb(msg: str, frac: float):
                        b_status.text(f"[{int(frac*100)}%] {msg}")
                        b_bar.progress(min(max(float(frac), 0.0), 1.0))

                    try:
                        pipeline = ShortsPipeline(llm_provider=llm_provider, tts_provider="edge-tts", voice=selected_voice)
                        res = pipeline.run(
                            topic=topic,
                            tone=batch_tone,
                            duration_pref=batch_dur,
                            progress_callback=batch_cb,
                            bgm_track=selected_bgm,
                            bgm_volume=bgm_volume,
                            subtitle_style=selected_sub_style,
                            visual_source=selected_visual_mode
                        )
                        b_status.success(f"✅ Rendered in {res.audio_duration:.1f}s: `{Path(res.final_video_path).name}`")
                        if Path(res.final_video_path).exists():
                            st.video(res.final_video_path)
                    except Exception as e:
                        b_status.error(f"Failed: {e}")


# -------------------------------------------------------------------
# TAB 3: STEP-BY-STEP STUDIO
# -------------------------------------------------------------------
with tab_step:
    st.markdown("### 🛠️ Step-by-Step Human-in-the-Loop Studio")
    st.caption("Inspect and modify the script, scene camera plan, and voiceover before final video rendering.")

    # Step 1: Research & Script
    st.markdown("#### Step 1: Research & Generate Script")
    s_col1, s_col2 = st.columns([3, 1])
    with s_col1:
        step_topic = st.text_input("Topic for Step-by-Step", value="Coca-Cola vs Pepsi", key="step_topic_input")
    with s_col2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        gen_script_btn = st.button("🔍 Generate & Verify Script", use_container_width=True)

    if gen_script_btn:
        with st.spinner("Researching and synthesizing verified script..."):
            generator = ScriptGenerator(provider=llm_provider)
            st.session_state.step_script = generator.generate(topic=step_topic)
            st.session_state.step_audio = None
            st.session_state.step_clips = None
            st.session_state.step_final_video = None
            st.success("Script generated with primary sources!")

    if st.session_state.step_script:
        scr: ShortsScript = st.session_state.step_script
        st.markdown("##### ✏️ Edit Script & Scene Plan")
        
        edit_title = st.text_input("Title", value=scr.title)
        edit_hook = st.text_input("Opening Hook (0-3s)", value=scr.hook)
        edit_voiceover = st.text_area("Voiceover Text", value=scr.voiceover_text, height=120)
        edit_cta = st.text_input("Closing CTA", value=scr.closing_cta)

        # Allow scene query and camera directions editing
        st.markdown("##### 🎥 Scene Visual Queries & Camera Motion")
        edited_scenes: List[VisualSegment] = []
        for i, sc in enumerate(scr.visual_segments):
            with st.expander(f"Scene #{i+1}: {sc.search_query} ({sc.approx_duration_sec}s)", expanded=False):
                c_sc1, c_sc2, c_sc3 = st.columns(3)
                with c_sc1:
                    new_q = st.text_input(f"Stock Query #{i+1}", value=sc.search_query, key=f"sq_{i}")
                    new_metric = st.text_input(f"On-Screen Metric #{i+1}", value=sc.on_screen_text, key=f"sm_{i}")
                with c_sc2:
                    new_shot = st.text_input(f"Shot Framing #{i+1}", value=sc.shot_type, key=f"ss_{i}")
                    new_cam = st.text_input(f"Camera Motion #{i+1}", value=sc.camera_movement, key=f"sc_{i}")
                with c_sc3:
                    new_desc = st.text_area(f"Description #{i+1}", value=sc.scene_description, key=f"sd_{i}", height=90)
                
                edited_scenes.append(
                    VisualSegment(
                        order=i + 1,
                        search_query=new_q,
                        pexels_keywords=[new_q],
                        scene_description=new_desc,
                        shot_type=new_shot,
                        camera_movement=new_cam,
                        on_screen_text=new_metric,
                        approx_duration_sec=sc.approx_duration_sec
                    )
                )

        if st.button("💾 Update Script State"):
            scr.title = edit_title
            scr.hook = edit_hook
            scr.voiceover_text = edit_voiceover
            scr.closing_cta = edit_cta
            scr.visual_segments = edited_scenes
            st.session_state.step_script = scr
            st.success("Script state updated!")

        st.markdown("---")
        # Step 2: Audio Synthesis
        st.markdown("#### Step 2: Voiceover Audio Generation")
        if st.button("🎙️ Synthesize Voiceover Audio"):
            with st.spinner("Synthesizing neural speech..."):
                tts = TTSEngine(provider="edge-tts", voice=selected_voice)
                audio_res = tts.generate_voiceover(text=scr.voiceover_text, filename=f"step_voice_{int(time.time())}.mp3")
                st.session_state.step_audio = audio_res
                st.success(f"Audio synthesized! Duration: {audio_res.duration_seconds:.2f}s ({len(audio_res.words_timing)} word timestamps)")

        if st.session_state.step_audio:
            st.audio(st.session_state.step_audio.audio_path)

        st.markdown("---")
        # Step 3: Stock Video Sourcing
        st.markdown("#### Step 3: Source Stock Clips or Topic Motion Graphics")
        if st.button("🔍 Sourcing Scenes Media"):
            with st.spinner("Downloading vertical stock footage / rendering topic graphics..."):
                fetcher = MediaFetcher()
                clips = fetcher.fetch_all_segments(
                    topic=step_topic,
                    visual_segments=scr.visual_segments,
                    visual_mode=selected_visual_mode
                )
                st.session_state.step_clips = clips
                st.success(f"Successfully sourced {len(clips)} scene clips!")

        if st.session_state.step_clips:
            clip_cols = st.columns(min(len(st.session_state.step_clips), 5))
            for i, c in enumerate(st.session_state.step_clips[:5]):
                with clip_cols[i]:
                    st.caption(f"Scene #{c.order}: {c.keyword[:20]}")
                    if Path(c.file_path).exists():
                        st.video(c.file_path)

        st.markdown("---")
        # Step 4: Final Render
        st.markdown("#### Step 4: Final 1080x1920 MP4 Render & Subtitle Burn")
        if st.button("🔥 Render Complete Short", type="primary"):
            if not st.session_state.step_audio or not st.session_state.step_clips:
                st.error("Please complete Step 2 (Audio) and Step 3 (Clips) first.")
            else:
                with st.spinner("Stitching video, ducking music, and burning TikTok subtitles..."):
                    editor = VideoEditor()
                    vpath = editor.build_short_video(
                        audio_result=st.session_state.step_audio,
                        clip_paths=[c.file_path for c in st.session_state.step_clips],
                        fallback_text=scr.voiceover_text,
                        bgm_track=selected_bgm,
                        bgm_volume=bgm_volume,
                        subtitle_style=selected_sub_style,
                        watermark_text=watermark_input
                    )
                    st.session_state.step_final_video = str(vpath.resolve())
                    st.success("Render complete!")

        if st.session_state.step_final_video and Path(st.session_state.step_final_video).exists():
            st.video(st.session_state.step_final_video)

            # Step 5: Human Approval for Publishing
            st.markdown("---")
            st.markdown("#### Step 5: Human Approval & YouTube Publication")
            st.caption("Human confirmation is required before broadcasting to YouTube Shorts.")
            confirm_pub = st.checkbox("✅ I have reviewed this video and approve it for YouTube Shorts publication.")
            
            if st.button("🚀 Publish to YouTube Shorts", disabled=not confirm_pub):
                with st.spinner("Authorizing OAuth2 and uploading to YouTube..."):
                    try:
                        publisher = YouTubePublisher()
                        vid_id = publisher.publish_short(
                            video_path=Path(st.session_state.step_final_video),
                            title=scr.title,
                            description=scr.description,
                            tags=scr.tags
                        )
                        st.success(f"🎉 Successfully published to YouTube! Video ID: {vid_id}")
                    except Exception as e:
                        st.error(f"Publication failed: {e}")


# -------------------------------------------------------------------
# TAB 4: JOB HISTORY & LOGS
# -------------------------------------------------------------------
with tab_history:
    st.markdown("### 📊 Production History & Verification Records")
    jobs = JobManager.list_jobs(limit=30)
    if not jobs:
        st.info("No render jobs found yet. Run a Short from Tab 1 or Tab 2!")
    else:
        for job in jobs:
            status_color = "pill-green" if job.status == "COMPLETED" else ("pill-yellow" if job.status in {"RUNNING", "QUEUED"} else "pill-red")
            created_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(job.created_at))
            
            with st.expander(f"🎬 {job.topic} | {job.job_id} ({job.status}) - {created_str}"):
                st.markdown(f"**Status**: <span class='highlight-pill {status_color}'>{job.status}</span> | **Stage**: `{job.current_stage}`", unsafe_allow_html=True)
                
                if job.video_path and Path(job.video_path).exists():
                    st.video(job.video_path)
                    st.caption(f"📁 Video: `{job.video_path}`")
                
                if job.validation_report:
                    st.json(job.validation_report)
                
                if job.logs:
                    st.code("\n".join(job.logs), language="text")


# -------------------------------------------------------------------
# TAB 5: SETUP & DOCUMENTATION
# -------------------------------------------------------------------
with tab_docs:
    st.markdown("### 📖 Setup & Architectural Documentation")
    st.markdown("""
    #### 🌟 Key Architecture
    1. **Factual Research Engine (`core/researcher.py`)**:
       - Queries live Wikipedia REST API for canonical definitions, exact numbers, and source URLs.
       - Built-in verified historical/scientific repository for instant reliable grounding.
    2. **Structured AI Synthesis (`core/script_generator.py`)**:
       - Pydantic schema validation rejecting generic filler or malformed scene plans.
       - Topic-adapted synthesis ensuring every video is genuinely different and grounded.
    3. **Stock Footage & Motion Graphics (`core/media_fetcher.py`, `core/motion_graphics.py`)**:
       - Pexels/Pixabay vertical portrait footage search avoiding repeated clips.
       - Pillow 1080x1920 topic motion graphics with cinematic Ken-Burns zoom when stock is unavailable.
    4. **Accurate Animated Subtitles (`core/subtitles.py`)**:
       - Faster-Whisper word-by-word acoustic alignment with Edge-TTS event fallback.
       - Dynamic active-word golden yellow highlighting with vertical safe margins.
    5. **Native FFmpeg Rendering (`core/video_editor.py`)**:
       - 1080x1920 30FPS normalization, sidechain audio ducking, and FFprobe quality validation.
    """)
