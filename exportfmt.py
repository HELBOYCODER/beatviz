"""exportfmt.py — multi-format export engine for BeatViz.

Encodes a frame directory (+ audio) into: mp4 h264, mp4 h265, webm vp9,
gif (palettegen/paletteuse), animated webp, or png frame-sequence zip.
"""
import io
import os
import shutil
import subprocess
import tempfile
import zipfile

# codec key -> (description, ffmpeg args after -c:v, ext, muxed audio?)
FORMATS = {
    "mp4":  ("H.264 MP4 (default)", ["libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"], ".mp4", True),
    "h265": ("H.265/HEVC MP4",     ["libx265", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-tag:v", "hvc1"], ".mp4", True),
    "webm": ("VP9 WebM",           ["libvpx-vp9", "-pix_fmt", "yuv420p", "-b:v", "0", "-crf", "32"], ".webm", True),
    "gif":  ("Palette-optimized GIF", [None, "-lavfi", "split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle"], ".gif", False),
    "webp": ("Animated WebP",      ["libwebp_anim", "-lossless", "0", "-q:v", "80", "-loop", "0"], ".webp", False),
    "png":  ("PNG frame sequence (zip)", None, ".zip", False),
}


def available_encoders():
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return {}
    names = ("libx264", "libx265", "libvpx-vp9", "libwebp_anim")
    return {n: (n in out) for n in names}


def encode(frames_dir, audio_path, out_path, fmt="mp4", fps=30,
           start=None, duration=None, crf=16, preset="slow"):
    """Encode frames in frames_dir (f%05d.png) + audio into out_path."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format '{fmt}'; one of {list(FORMATS)}")
    desc, vcodec_args, ext, with_audio = FORMATS[fmt]
    if not out_path.lower().endswith(ext):
        out_path = os.path.splitext(out_path)[0] + ext

    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(fps),
           "-i", os.path.join(frames_dir, "f%05d.png")]
    if with_audio and audio_path and os.path.exists(audio_path):
        cmd += ["-i", audio_path]
    if start is not None:
        cmd += ["-ss", str(start)] if False else []  # frames are already the exact segment; audio seek below
    if duration is not None:
        cmd += ["-t", str(duration)]
    if fmt == "png":
        tmpd = tempfile.mkdtemp(prefix="bvzip_")
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps),
                            "-i", os.path.join(frames_dir, "f%05d.png"),
                            "-c:v", "png", os.path.join(tmpd, "f%05d.png")], check=True)
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
                for f in sorted(os.listdir(tmpd)):
                    z.write(os.path.join(tmpd, f), arcname=f)
        finally:
            shutil.rmtree(tmpd, ignore_errors=True)
        return out_path
    if fmt == "gif":
        cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(fps),
               "-i", os.path.join(frames_dir, "f%05d.png")]
        if with_audio and audio_path and os.path.exists(audio_path):
            cmd += ["-i", audio_path]
        cmd += ["-lavfi",
                "split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];"
                "[s1][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle"]
        cmd += ["-loop", "0", out_path]
        subprocess.run(cmd, check=True)
        return out_path
    codec, extra = vcodec_args[0], vcodec_args[1:]
    cmd += ["-c:v", codec]
    if codec == "libx264":
        cmd += ["-preset", preset, "-crf", str(crf), "-profile:v", "high"]
    elif codec == "libx265":
        cmd += ["-preset", preset, "-crf", str(crf + 2)]
    elif codec == "libwebp_anim":
        cmd += ["-compression_level", "5"]
    cmd += extra
    if with_audio and audio_path and os.path.exists(audio_path):
        if fmt == "webm":
            cmd += ["-c:a", "libopus", "-b:a", "192k", "-shortest"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "256k", "-shortest"]
    cmd += ["-r", str(fps), out_path]
    subprocess.run(cmd, check=True)
    return out_path


def concat_clips(clips, out_path):
    """Concatenate rendered segment files (same codec/params) via concat demuxer."""
    tmp = tempfile.mktemp(suffix=".txt")
    with open(tmp, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", tmp, "-c", "copy", out_path], check=True)
    finally:
        os.unlink(tmp)
    return out_path
