import os
import random
import asyncio
import argparse
from moviepy.editor import *
from moviepy.audio.fx.audio_loop import audio_loop
from PIL import Image, ImageDraw, ImageFont, ImageColor
import edge_tts
import uharfbuzz as hb
import freetype
import textwrap
from tqdm import tqdm

# Fix for PIL compatibility
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS


def parse_args():
    parser = argparse.ArgumentParser(description="Indian Language Review Video Generator")
    parser.add_argument("--input", required=True, help="Text file with review chunks")
    parser.add_argument("--output", default="review_output.mp4", help="Output video path")
    parser.add_argument("--background", help="Background image or folder of images")
    parser.add_argument("--music", help="Background music (mp3)")
    parser.add_argument("--font", required=True, help="Path to multilingual TTF font")
    parser.add_argument("--voice", required=True, help="Edge TTS voice (e.g. hi-IN-SwaraNeural)")
    parser.add_argument("--rate", default="+10%", help="TTS speech rate")

    # ✅ Original customization args
    parser.add_argument("--font-size", type=int, default=60, help="Font size for text")
    parser.add_argument("--font-color", default="#FFFFFF", help="Font color (hex)")
    parser.add_argument("--box-color", default="#000000", help="Text box color (hex)")
    parser.add_argument("--box-alpha", type=float, default=0.6, help="Box transparency (0.0 to 1.0)")

    # ✅ NEW: video size + logo
    parser.add_argument("--width", type=int, default=720, help="Video width in pixels")
    parser.add_argument("--height", type=int, default=1280, help="Video height in pixels")
    parser.add_argument("--logo", help="Optional logo image to overlay on video")
    parser.add_argument(
        "--logo-position",
        choices=["top-left", "top-right", "bottom-left", "bottom-right", "top-center", "bottom-center"],
        default="top-center",
        help="Logo position on video",
    )
    parser.add_argument("--logo-opacity", type=float, default=1.0, help="Logo opacity (0.0–1.0)")

    # ✅ NEW: text layout / style
    parser.add_argument(
        "--text-position",
        choices=["center", "top", "bottom"],
        default="center",
        help="Vertical position of text block",
    )
    parser.add_argument(
        "--style",
        choices=["default", "caption", "subtitle"],
        default="default",
        help="Preset style: default / caption-bar / subtitle-bar",
    )

    # ✅ NEW: shadow/glow
    parser.add_argument("--enable-shadow", action="store_true", help="Enable text shadow")
    parser.add_argument("--shadow-color", default="#000000", help="Shadow color (hex)")
    parser.add_argument("--shadow-offset-x", type=int, default=2, help="Shadow offset X in pixels")
    parser.add_argument("--shadow-offset-y", type=int, default=2, help="Shadow offset Y in pixels")

    # ✅ NEW: timing
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.0,
        help="Minimum duration per slide in seconds (0 = disabled)",
    )

    # ✅ NEW: progress bar overlay
    parser.add_argument(
        "--enable-progress-bar",
        action="store_true",
        help="Show a simple progress bar at the bottom",
    )
    parser.add_argument("--progress-color", default="#FFFFFF", help="Progress bar color (hex)")
    parser.add_argument("--progress-height", type=int, default=6, help="Progress bar height in pixels")

    return parser.parse_args()


async def generate_tts(text, out_path, voice, rate):
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(out_path)


async def generate_all_audios(chunks, voice, rate, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    tasks = []
    for i, text in enumerate(tqdm(chunks, desc="Generating Audio")):
        out_path = os.path.join(out_dir, f"chunk_{i}.mp3")
        tasks.append(generate_tts(text, out_path, voice, rate))
    await asyncio.gather(*tasks)


def contains_complex_script(text):
    for ch in text:
        if '\u0900' <= ch <= '\u0FFF':
            return True
    return False


def render_text_image(
    text,
    out_path,
    font_path,
    size=(720, 1280),
    bg_path=None,
    font_size=60,
    font_color="#FFFFFF",
    box_color="#000000",
    box_alpha=0.6,
    text_position="center",
    enable_shadow=False,
    shadow_color="#000000",
    shadow_offset_x=2,
    shadow_offset_y=2,
):
    """Draw text (complex or simple) onto an image with optional bg, box, and shadow."""
    if bg_path and os.path.exists(bg_path):
        bg = Image.open(bg_path).convert("RGBA").resize(size)
    else:
        bg = Image.new("RGBA", size, (40, 40, 40, 255))

    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    box_rgba = (*ImageColor.getrgb(box_color), int(max(0.0, min(1.0, box_alpha)) * 255))
    shadow_rgb = ImageColor.getrgb(shadow_color)

    if contains_complex_script(text):
        # --- Complex script path (your original logic) ---
        face = freetype.Face(font_path)
        with open(font_path, "rb") as f:
            font_bytes = f.read()
        hb_face = hb.Face(font_bytes)
        hb_font = hb.Font(hb_face)
        hb.ot_font_set_funcs(hb_font)
        upem = hb_face.upem
        hb_font.scale = (upem, upem)

        font_rgb = ImageColor.getrgb(font_color)

        def shape_line(txt, size_px):
            buf = hb.Buffer()
            buf.add_str(txt)
            buf.guess_segment_properties()
            hb.shape(hb_font, buf)
            width = sum(pos.x_advance for pos in buf.glyph_positions) / upem * size_px
            return buf, width

        max_width = size[0] - 100
        line_spacing = 1.3
        words = text.split()
        lines, current = [], ""
        while words:
            trial = current + " " + words[0] if current else words[0]
            _, w = shape_line(trial, font_size)
            if w <= max_width:
                current = trial
                words.pop(0)
            else:
                lines.append(current)
                current = ""
        if current:
            lines.append(current)

        # Total text height
        total_h = len(lines) * font_size * line_spacing + 40
        # Vertical anchor
        if text_position == "top":
            y = 60
        elif text_position == "bottom":
            y = max(size[1] - int(total_h) - 60, 30)
        else:  # center
            y = max((size[1] - total_h) // 2, 30)

        box_top = y - 20
        box_bottom = y + total_h
        draw.rectangle([30, box_top, size[0] - 30, box_bottom], fill=box_rgba)

        for line in lines:
            buf, line_width = shape_line(line, font_size)
            infos = buf.glyph_infos
            positions = buf.glyph_positions
            x = (size[0] - line_width) / 2

            for info, pos in zip(infos, positions):
                gid = info.codepoint
                face.set_char_size(font_size * 64)
                face.load_glyph(gid, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
                bmp = face.glyph.bitmap
                top = face.glyph.bitmap_top
                left = face.glyph.bitmap_left

                glyph_img = Image.new("L", (bmp.width, bmp.rows), 0)
                glyph_img.frombytes(bytes(bmp.buffer))

                rgba = Image.new("RGBA", (bmp.width, bmp.rows), font_rgb + (0,))
                rgba.putalpha(glyph_img)

                pos_x = int(x + (pos.x_offset / upem) * font_size) + left
                pos_y = int(y + (font_size - top) + (pos.y_offset / upem) * font_size)

                if enable_shadow:
                    shadow_rgba = Image.new("RGBA", (bmp.width, bmp.rows), shadow_rgb + (0,))
                    shadow_rgba.putalpha(glyph_img)
                    overlay.paste(
                        shadow_rgba,
                        (pos_x + shadow_offset_x, pos_y + shadow_offset_y),
                        shadow_rgba,
                    )

                overlay.paste(rgba, (pos_x, pos_y), rgba)
                x += (pos.x_advance / upem) * font_size
            y += font_size * line_spacing
    else:
        # --- Simple script path ---
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            font = ImageFont.load_default()
        lines = textwrap.wrap(text, width=28)
        if not lines:
            lines = [text]

        line_h = font.getsize("A")[1]
        total_h = len(lines) * (line_h + 10)

        # Vertical anchor
        if text_position == "top":
            y = 60
        elif text_position == "bottom":
            y = max(size[1] - total_h - 60, 30)
        else:  # center
            y = max((size[1] - total_h) // 2, 30)

        box_top = y - 20
        box_bottom = y + total_h + 20
        draw.rectangle([30, box_top, size[0] - 30, box_bottom], fill=box_rgba)

        for line in lines:
            w, _ = draw.textsize(line, font=font)
            x = (size[0] - w) / 2
            if enable_shadow:
                draw.text(
                    (x + shadow_offset_x, y + shadow_offset_y),
                    line,
                    font=font,
                    fill=shadow_color,
                )
            draw.text((x, y), line, font=font, fill=font_color)
            y += line_h + 10

    final = Image.alpha_composite(bg, overlay).convert("RGB")
    final.save(out_path)


def generate_images(
    chunks,
    font_path,
    image_dir,
    bg_img,
    font_size,
    font_color,
    box_color,
    box_alpha,
    size=(720, 1280),
    text_position="center",
    enable_shadow=False,
    shadow_color="#000000",
    shadow_offset_x=2,
    shadow_offset_y=2,
):
    os.makedirs(image_dir, exist_ok=True)
    paths = []

    # Background rotation: if bg_img is a folder, pick random image per chunk
    bg_files = None
    if bg_img and os.path.isdir(bg_img):
        exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
        bg_files = [
            os.path.join(bg_img, f)
            for f in os.listdir(bg_img)
            if f.lower().endswith(exts)
        ]
        if not bg_files:
            bg_files = None  # fallback to solid bg

    for i, txt in enumerate(tqdm(chunks, desc="Generating Images")):
        out = os.path.join(image_dir, f"img_{i}.png")

        if bg_files:
            chosen_bg = random.choice(bg_files)
        else:
            chosen_bg = bg_img

        render_text_image(
            txt,
            out,
            font_path,
            size=size,
            bg_path=chosen_bg,
            font_size=font_size,
            font_color=font_color,
            box_color=box_color,
            box_alpha=box_alpha,
            text_position=text_position,
            enable_shadow=enable_shadow,
            shadow_color=shadow_color,
            shadow_offset_x=shadow_offset_x,
            shadow_offset_y=shadow_offset_y,
        )
        paths.append(out)
    return paths


def assemble_video(
    images,
    audio_dir,
    output_path,
    bg_music,
    size=(720, 1280),
    logo_path=None,
    logo_position="top-center",
    logo_opacity=1.0,
    min_duration=0.0,
    enable_progress_bar=False,
    progress_color="#FFFFFF",
    progress_height=6,
):
    clips = []
    durations = []

    for i, img in enumerate(tqdm(images, desc="Making Clips")):
        audio = AudioFileClip(os.path.join(audio_dir, f"chunk_{i}.mp3"))
        duration = audio.duration
        if min_duration > 0 and duration < min_duration:
            duration = min_duration
            audio = audio.set_duration(duration)

        img_clip = ImageClip(img).set_duration(duration).set_audio(audio)
        img_clip = img_clip.resize(size)
        clips.append(img_clip)
        durations.append(duration)

    final = concatenate_videoclips(clips, method="compose")

    # Background music
    if bg_music and os.path.exists(bg_music):
        music = AudioFileClip(bg_music).volumex(0.1)
        music = audio_loop(music, duration=final.duration)
        final = final.set_audio(CompositeAudioClip([final.audio, music]))

    # Logo overlay
    if logo_path and os.path.exists(logo_path):
        try:
            logo_clip = ImageClip(logo_path)
            target_w = size[0] * 0.2  # ~20% of width
            logo_clip = logo_clip.resize(width=target_w).set_opacity(
                max(0.0, min(1.0, logo_opacity))
            )

            pos_map = {
                "top-left": ("left", "top"),
                "top-right": ("right", "top"),
                "bottom-left": ("left", "bottom"),
                "bottom-right": ("right", "bottom"),
                "top-center": ("center", "top"),
                "bottom-center": ("center", "bottom"),
            }
            pos = pos_map.get(logo_position, ("center", "top"))
            # margin
            if "bottom" in logo_position:
                logo_clip = logo_clip.margin(bottom=20, opacity=0)
            else:
                logo_clip = logo_clip.margin(top=20, opacity=0)
            if "left" in logo_position:
                logo_clip = logo_clip.margin(left=20, opacity=0)
            elif "right" in logo_position:
                logo_clip = logo_clip.margin(right=20, opacity=0)

            logo_clip = logo_clip.set_duration(final.duration).set_position(pos)
            final = CompositeVideoClip([final, logo_clip])
        except Exception as e:
            print(f"[WARN] Could not overlay logo: {e}")

    # Progress bar overlay (simple: jumps per slide)
    if enable_progress_bar and durations:
        try:
            bar_rgb = ImageColor.getrgb(progress_color)
            total_slides = len(durations)

            new_clips = []
            for idx, base_clip in enumerate(clips):
                dur = durations[idx]
                progress_fraction = float(idx + 1) / total_slides
                bar_width = int(size[0] * progress_fraction)

                bar_bg = ColorClip(
                    size=(size[0], progress_height),
                    color=(30, 30, 30),
                ).set_duration(dur).set_position(("center", "bottom"))

                bar_fg = ColorClip(
                    size=(bar_width, progress_height),
                    color=bar_rgb,
                ).set_duration(dur).set_position(("left", "bottom"))

                comp = CompositeVideoClip([base_clip, bar_bg, bar_fg])
                new_clips.append(comp)

            final = concatenate_videoclips(new_clips, method="compose")
        except Exception as e:
            print(f"[WARN] Could not draw progress bar: {e}")

    final = final.fadein(1).fadeout(1)
    final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")


def main():
    args = parse_args()
    with open(args.input, encoding="utf-8") as f:
        chunks = [line.strip() for line in f if line.strip()]

    print(f"[INFO] Generating TTS for {len(chunks)} chunks...")
    asyncio.run(generate_all_audios(chunks, args.voice, args.rate, "audio_chunks"))

    size = (args.width, args.height)

    # Apply style presets on top of base args (without breaking your GUI inputs)
    text_position = args.text_position
    font_color = args.font_color
    box_color = args.box_color
    box_alpha = args.box_alpha

    if args.style == "caption":
        text_position = "top"
        box_color = "#000000"
        box_alpha = 0.7
        font_color = "#FFFF00"
    elif args.style == "subtitle":
        text_position = "bottom"
        box_color = "#000000"
        box_alpha = 0.7
        font_color = "#FFFFFF"

    print("[INFO] Rendering images...")
    images = generate_images(
        chunks,
        args.font,
        "images",
        args.background,
        font_size=args.font_size,
        font_color=font_color,
        box_color=box_color,
        box_alpha=box_alpha,
        size=size,
        text_position=text_position,
        enable_shadow=args.enable_shadow,
        shadow_color=args.shadow_color,
        shadow_offset_x=args.shadow_offset_x,
        shadow_offset_y=args.shadow_offset_y,
    )

    print("[INFO] Assembling final video...")
    assemble_video(
        images,
        "audio_chunks",
        args.output,
        args.music,
        size=size,
        logo_path=args.logo,
        logo_position=args.logo_position,
        logo_opacity=args.logo_opacity,
        min_duration=args.min_duration,
        enable_progress_bar=args.enable_progress_bar,
        progress_color=args.progress_color,
        progress_height=args.progress_height,
    )
    print("[DONE] Video saved at:", args.output)


if __name__ == "__main__":
    main()
