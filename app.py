import os
import sys
import subprocess
import tempfile
from pathlib import Path

import streamlit as st

# ---------- CONFIG ----------

BASE_DIR = Path(__file__).resolve().parent
CLI_SCRIPT = BASE_DIR / "final2cli.py"

# NEW: directory to auto-scan fonts from
FONT_DIR = BASE_DIR / "fonts"

VOICE_OPTIONS = {
    "Hindi (hi-IN-SwaraNeural)": "hi-IN-SwaraNeural",
    "Telugu (te-IN-ShrutiNeural)": "te-IN-ShrutiNeural",
    "Kannada (kn-IN-SapnaNeural)": "kn-IN-SapnaNeural",
    "Tamil (ta-IN-PallaviNeural)": "ta-IN-PallaviNeural",
    "Malayalam (ml-IN-SobhanaNeural)": "ml-IN-SobhanaNeural",
    "English India (en-IN-NeerjaNeural)": "en-IN-NeerjaNeural",
    "Gujarati (gu-IN-DhwaniNeural)": "gu-IN-DhwaniNeural",
    "English US (en-US-AriaNeural)": "en-US-AriaNeural",
    "English UK (en-GB-LibbyNeural)": "en-GB-LibbyNeural",
    "Hindi (hi-IN-MadhurNeural) – Male": "hi-IN-MadhurNeural",
    "Telugu (te-IN-MohanNeural) – Male": "te-IN-MohanNeural",
    "Kannada (kn-IN-GaganNeural) – Male": "kn-IN-GaganNeural",
    "Tamil (ta-IN-ValluvarNeural) – Male": "ta-IN-ValluvarNeural",
    "Malayalam (ml-IN-MidhunNeural) – Male": "ml-IN-MidhunNeural",
    "English US (en-US-GuyNeural) – Male": "en-US-GuyNeural",
}

VIDEO_PRESETS = {
    "Instagram Reel (720×1280)": (720, 1280),
    "YouTube Shorts (1080×1920)": (1080, 1920),
    "Square (1080×1080)": (1080, 1080),
}

LOGO_POSITIONS = ["top-center", "top-left", "top-right", "bottom-center", "bottom-left", "bottom-right"]
TEXT_POSITIONS = ["center", "top", "bottom"]
STYLE_PRESETS = ["default", "caption", "subtitle"]

# ---------- PAGE SETUP ----------

st.set_page_config(
    page_title="Abbu Video Review Generator",
    page_icon="🎥",
    layout="wide",
)

# Minimal custom CSS for a trendy look
st.markdown(
    """
    <style>
    .main {
        background-color: #f5f7fa;
    }
    .stButton>button {
        border-radius: 999px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        background: linear-gradient(90deg, #ff6f91, #ff4b6e);
        border: none;
    }
    .stButton>button:hover {
        filter: brightness(1.05);
    }
    .small-label {
        font-size: 0.85rem;
        color: #666666;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎥 Abbu Video Review Generator (Web)")
st.write("Create vertical review videos with TTS, stylish captions, and overlays – right from your browser.")


# ---------- HELPERS ----------

def save_uploaded_file(uploaded_file, dest_path: Path):
    if uploaded_file is None:
        return None
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.read())
    return str(dest_path)


def build_cli_command(
    workdir: Path,
    review_path: str,
    font_path: str,
    output_path: str,
    background_path: str | None,
    logo_path: str | None,
    music_path: str | None,
    options: dict,
    flags: list[str],
):
    cmd = [sys.executable, str(CLI_SCRIPT)]

    def add_arg(k, v):
        if v is not None and v != "":
            cmd.extend([k, str(v)])

    add_arg("--input", review_path)
    add_arg("--background", background_path)
    add_arg("--logo", logo_path)
    add_arg("--music", music_path)
    add_arg("--font", font_path)
    add_arg("--output", output_path)

    for k, v in options.items():
        add_arg(k, v)

    cmd.extend(flags)
    return cmd


# ---------- DISCOVER SERVER FONTS (NEW) ----------

server_font_names: list[str] = []
server_font_map: dict[str, str] = {}

if FONT_DIR.exists() and FONT_DIR.is_dir():
    for p in sorted(FONT_DIR.glob("*.ttf")):
        server_font_names.append(p.name)
        server_font_map[p.name] = str(p)
    for p in sorted(FONT_DIR.glob("*.otf")):
        server_font_names.append(p.name)
        server_font_map[p.name] = str(p)


# ---------- LAYOUT ----------

left_col, right_col = st.columns([1, 1.1], gap="large")

with left_col:
    st.subheader("1️⃣ Files & basic settings")

    review_file = st.file_uploader("Review Text File (.txt)", type=["txt"])
    bg_file = st.file_uploader("Background Image (.jpg/.png) or none", type=["jpg", "jpeg", "png"], accept_multiple_files=False)
    logo_file = st.file_uploader("Logo Image (optional)", type=["jpg", "jpeg", "png"])
    music_file = st.file_uploader("Background Music (optional, .mp3)", type=["mp3"])
    font_file = st.file_uploader("Font File (.ttf / .otf, required)", type=["ttf", "otf"])

    # NEW: dropdown to choose from fonts folder
    if server_font_names:
        font_choice = st.selectbox(
            "Or choose from installed fonts (./fonts)",
            options=["(None)"] + server_font_names,
            index=0,
            help="Fonts are loaded from the 'fonts' folder next to this app.",
        )
    else:
        font_choice = "(None)"

    st.markdown("#### Output")
    output_name = st.text_input("Output video filename", value="review_output.mp4")

    st.markdown("#### Video size")
    preset_name = st.selectbox("Preset", list(VIDEO_PRESETS.keys()), index=0)
    width, height = VIDEO_PRESETS[preset_name]
    col_w, col_h = st.columns(2)
    with col_w:
        custom_width = st.number_input("Width", min_value=320, max_value=2160, value=width, step=10)
    with col_h:
        custom_height = st.number_input("Height", min_value=320, max_value=4096, value=height, step=10)

    st.markdown("#### Timing & progress")
    min_duration = st.number_input("Min slide duration (seconds, 0 = auto)", min_value=0.0, value=0.0, step=0.5)
    enable_progress_bar = st.checkbox("Show progress bar at bottom", value=False)

with right_col:
    st.subheader("2️⃣ Voice & styling")

    st.markdown("##### Voice / TTS")
    voice_name = st.selectbox("Voice / Language", list(VOICE_OPTIONS.keys()), index=0)
    tts_rate = st.text_input("TTS speaking rate (e.g. +10%, -5%)", value="+10%")

    st.markdown("##### Text styling")
    col_fs, col_style = st.columns(2)
    with col_fs:
        font_size = st.slider("Font size", min_value=24, max_value=100, value=60, step=2)
    with col_style:
        style_preset = st.selectbox("Style preset", STYLE_PRESETS, index=0)

    col_fcolor, col_box = st.columns(2)
    with col_fcolor:
        font_color = st.color_picker("Font color", "#FFFFFF")
    with col_box:
        box_color = st.color_picker("Text box color", "#000000")

    box_alpha_255 = st.slider("Text box transparency (0 = fully transparent, 255 = solid)", 0, 255, 160)
    box_alpha = box_alpha_255 / 255.0

    col_textpos, col_logopos = st.columns(2)
    with col_textpos:
        text_position = st.selectbox("Text block position", TEXT_POSITIONS, index=0)
    with col_logopos:
        logo_position = st.selectbox("Logo position", LOGO_POSITIONS, index=0)

    logo_opacity = st.slider("Logo opacity", min_value=0.1, max_value=1.0, value=1.0, step=0.05)

    st.markdown("##### Shadows & effects")
    enable_shadow = st.checkbox("Enable text shadow", value=False)
    col_scol, col_off = st.columns(2)
    with col_scol:
        shadow_color = st.color_picker("Shadow color", "#000000")
    with col_off:
        shadow_offset_x = st.number_input("Shadow offset X", value=2, step=1)
        shadow_offset_y = st.number_input("Shadow offset Y", value=2, step=1)

    st.markdown("##### Progress bar style (if enabled)")
    col_pcol, col_ph = st.columns(2)
    with col_pcol:
        progress_color = st.color_picker("Progress bar color", "#FFFFFF")
    with col_ph:
        progress_height = st.number_input("Progress bar height (px)", min_value=1, max_value=40, value=6, step=1)


st.markdown("---")
st.subheader("3️⃣ Generate & Logs")

generate_col, _ = st.columns([1, 3])
with generate_col:
    generate_btn = st.button("🚀 Generate Video")

log_placeholder = st.empty()
download_placeholder = st.empty()

# ---------- RUN PIPELINE ----------

if generate_btn:
    # Basic validation
    if review_file is None:
        st.error("Please upload a **Review Text File (.txt)**.")
    elif font_file is None and (font_choice == "(None)" or font_choice not in server_font_map):
        # NEW: allow either upload OR dropdown
        st.error("Please upload a **Font File (.ttf / .otf)** or choose one from the dropdown.")
    elif not output_name.strip().lower().endswith(".mp4"):
        st.error("Output filename must end with `.mp4`.")
    else:
        with st.spinner("Generating video... this may take a bit."):
            # Create temp working directory
            workdir = Path(tempfile.mkdtemp(prefix="Video_review_"))

            review_path = save_uploaded_file(review_file, workdir / "review.txt")

            # NEW: decide where font comes from
            if font_file is not None:
                font_path = save_uploaded_file(font_file, workdir / "font.ttf")
            else:
                # using server font directly
                font_path = server_font_map.get(font_choice)

            bg_path = save_uploaded_file(bg_file, workdir / "background.png") if bg_file else None
            logo_path = save_uploaded_file(logo_file, workdir / "logo.png") if logo_file else None
            music_path = save_uploaded_file(music_file, workdir / "music.mp3") if music_file else None

            output_path = str(workdir / output_name.strip())

            options = {
                "--voice": VOICE_OPTIONS[voice_name],
                "--rate": tts_rate,
                "--font-size": font_size,
                "--font-color": font_color,
                "--box-color": box_color,
                "--box-alpha": str(box_alpha),
                "--width": int(custom_width),
                "--height": int(custom_height),
                "--style": style_preset,
                "--text-position": text_position,
                "--shadow-color": shadow_color,
                "--shadow-offset-x": int(shadow_offset_x),
                "--shadow-offset-y": int(shadow_offset_y),
                "--logo-position": logo_position,
                "--logo-opacity": float(logo_opacity),
                "--min-duration": float(min_duration),
                "--progress-color": progress_color,
                "--progress-height": int(progress_height),
            }

            flags = []
            if enable_shadow:
                flags.append("--enable-shadow")
            if enable_progress_bar:
                flags.append("--enable-progress-bar")

            cmd = build_cli_command(
                workdir=workdir,
                review_path=review_path,
                font_path=font_path,
                output_path=output_path,
                background_path=bg_path,
                logo_path=logo_path,
                music_path=music_path,
                options=options,
                flags=flags,
            )

            # Run CLI and stream logs
            log_lines = []
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(BASE_DIR),
                )

                for line in proc.stdout:
                    log_lines.append(line.rstrip("\n"))
                    log_placeholder.code("\n".join(log_lines), language="bash")

                proc.wait()
                exit_code = proc.returncode

                if exit_code == 0 and os.path.exists(output_path):
                    log_lines.append("✅ Video generation completed successfully.")
                    log_placeholder.code("\n".join(log_lines), language="bash")

                    with open(output_path, "rb") as f:
                        video_bytes = f.read()
                    download_placeholder.download_button(
                        label="⬇️ Download Video",
                        data=video_bytes,
                        file_name=os.path.basename(output_path),
                        mime="video/mp4",
                    )
                else:
                    log_lines.append(f"❌ Video generation failed (exit code {exit_code}).")
                    log_placeholder.code("\n".join(log_lines), language="bash")

            except Exception as e:
                log_lines.append(f"❌ Error: {e}")
                log_placeholder.code("\n".join(log_lines), language="bash")
