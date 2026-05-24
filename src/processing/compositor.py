"""Multi-track timeline compositing via ffmpeg filter_complex overlay chains.

Replaces the flat sequential concat pipeline in _execute_generate().
Matches the Canvas 2D preview rendering behaviour (bottom-to-top overlay,
per-clip scale/position/effect, per-track mute/visibility).
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ffmpeg import FFMPEG, FFPROBE, EFFECT_FILTERS, _run, _get_encoder
from ..logger import default_logger as logger


# ── Data model ──

@dataclass
class CompositorClip:
    """Normalised video/image clip for the overlay chain."""
    clip_id: str
    type: str               # "video" | "image"
    filepath: str
    input_index: int         # which ffmpeg -i input this file maps to
    src_width: int
    src_height: int
    has_audio: bool          # True if source has an audio stream
    # Timeline positioning (seconds)
    timeline_in: float
    timeline_out: float
    # Source trim (seconds)
    source_in: float
    source_out: float
    # Visual
    center_x: float          # 0-100
    center_y: float          # 0-100
    scale: float             # 0-100 (default 100)
    opacity: float           # 0-100 (default 100)
    effect: str              # filter key or ""
    transition_in: Optional[dict]  # {key, duration}
    # Layer order
    track_index: int
    is_image: bool


@dataclass
class CompositorAudioClip:
    """Normalised audio clip for the amix chain."""
    filepath: str
    input_index: int
    timeline_in: float
    timeline_out: float
    source_in: float
    source_out: float
    track_index: int



# ── Probe helpers ──

_dim_cache: dict[str, tuple[int, int]] = {}


def _probe_dimensions(filepath: str) -> tuple[int, int]:
    """Get source width/height via ffprobe. Cached per filepath."""
    if filepath in _dim_cache:
        return _dim_cache[filepath]
    try:
        result = _run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             str(filepath)],
            capture_output=True, text=True, timeout=15,
        )
        parts = result.stdout.strip().split(",")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            w, h = int(parts[0]), int(parts[1])
            _dim_cache[filepath] = (w, h)
            return w, h
    except Exception:
        pass
    _dim_cache[filepath] = (1920, 1080)
    return 1920, 1080


def _probe_has_audio(filepath: str) -> bool:
    """Check if a media file has an audio stream."""
    try:
        result = _run(
            [FFPROBE, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0",
             str(filepath)],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() == "audio"
    except Exception:
        return False


# ── Geometry ──

def _compute_geometry(
    src_w: int, src_h: int,
    canvas_w: int, canvas_h: int,
    center_x: float, center_y: float, scale_pct: float,
) -> tuple[int, int, int, int]:
    """Compute (scaled_w, scaled_h, overlay_x, overlay_y) matching drawMediaToCanvas."""
    clip_scale = scale_pct / 100.0
    base_scale = min(canvas_w / src_w, canvas_h / src_h) if src_w > 0 and src_h > 0 else 1.0
    final_scale = base_scale * clip_scale
    dw = int(src_w * final_scale)
    dh = int(src_h * final_scale)
    cx = center_x / 100.0
    cy = center_y / 100.0
    ox = int((canvas_w - dw) * cx)
    oy = int((canvas_h - dh) * cy)
    return dw, dh, ox, oy


# ── Normalisation ──

def _is_image_path(fp: str) -> bool:
    return fp.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))


def _normalise_tracks(
    tracks: list[dict],
    fps: float,
    target_w: int,
    target_h: int,
) -> tuple[list[CompositorClip], list[CompositorAudioClip], float, list[str]]:
    """Parse track JSON into clips + unique input files.

    Returns (video_clips, audio_clips, total_duration_sec, input_files).
    Clips are sorted by track_index ASC (bottom track first), so the overlay
    chain paints bottom-to-top.
    """
    video_clips: list[CompositorClip] = []
    audio_clips: list[CompositorAudioClip] = []
    max_end = 0.0

    # Deduplicate input files (same file used across multiple clips)
    file_to_input: dict[str, int] = {}
    input_files: list[str] = []

    def _get_input_index(fp: str) -> int:
        fp = str(Path(fp).resolve())
        if fp not in file_to_input:
            file_to_input[fp] = len(input_files)
            input_files.append(fp)
        return file_to_input[fp]

    for ti, track in enumerate(tracks):
        t_type = track.get("type", "")
        t_visible = track.get("visible", True)
        t_muted = track.get("muted", False)

        if t_type == "group":
            # Group tracks handled separately in batch_generate_groups
            continue

        if t_type == "text":
            continue  # Text handled as ASS subtitle post-processing

        if t_type == "audio":
            # Audio-only track: each clip contributes audio
            for clip in track.get("list", []):
                fp = clip.get("filepath", "")
                if not fp or not Path(fp).exists():
                    continue
                start_f = clip.get("start", 0) or 0
                end_f = clip.get("end", 0) or 0
                offset_l = clip.get("offsetL", 0) or 0
                offset_r = clip.get("offsetR", 0) or 0
                clip_frames = max(end_f - start_f, 1)
                tl_in = start_f / fps
                tl_out = end_f / fps
                src_dur = (offset_l + clip_frames - offset_r) / fps
                src_in = max(offset_l / fps, 0)
                src_out = src_in + max(src_dur, 0.01)
                max_end = max(max_end, tl_out)

                idx = _get_input_index(fp)
                audio_clips.append(CompositorAudioClip(
                    filepath=str(Path(fp).resolve()),
                    input_index=idx,
                    timeline_in=tl_in,
                    timeline_out=tl_out,
                    source_in=src_in,
                    source_out=src_out,
                    track_index=ti,
                ))
            continue

        # Video / image track
        for clip in track.get("list", []):
            ctype = clip.get("type", "")
            fp = clip.get("filepath", "")
            if not fp or not Path(fp).exists():
                continue

            is_img = _is_image_path(fp) or ctype == "image"
            if ctype == "audio":
                # Audio clip on a non-audio track
                if not t_muted:
                    start_f = clip.get("start", 0) or 0
                    end_f = clip.get("end", 0) or 0
                    offset_l = clip.get("offsetL", 0) or 0
                    offset_r = clip.get("offsetR", 0) or 0
                    clip_frames = max(end_f - start_f, 1)
                    tl_in = start_f / fps
                    tl_out = end_f / fps
                    src_dur = (offset_l + clip_frames - offset_r) / fps
                    src_in = max(offset_l / fps, 0)
                    src_out = src_in + max(src_dur, 0.01)
                    max_end = max(max_end, tl_out)
                    idx = _get_input_index(fp)
                    audio_clips.append(CompositorAudioClip(
                        filepath=str(Path(fp).resolve()),
                        input_index=idx,
                        timeline_in=tl_in,
                        timeline_out=tl_out,
                        source_in=src_in,
                        source_out=src_out,
                        track_index=ti,
                    ))
                continue

            if ctype not in ("video", "image") and not is_img:
                continue

            start_f = clip.get("start", 0) or 0
            end_f = clip.get("end", 0) or 0
            if end_f <= start_f:
                continue

            offset_l = clip.get("offsetL", 0) or 0
            offset_r = clip.get("offsetR", 0) or 0
            clip_frames = end_f - start_f
            tl_in = start_f / fps
            tl_out = end_f / fps
            src_dur = max((offset_l + clip_frames - offset_r) / fps, 0.01)
            src_in = max(offset_l / fps, 0)
            src_out = src_in + src_dur
            max_end = max(max_end, tl_out)

            idx = _get_input_index(fp)
            has_audio = False if is_img else _probe_has_audio(fp)

            src_w, src_h = clip.get("width") or 0, clip.get("height") or 0
            if not src_w or not src_h:
                src_w, src_h = _probe_dimensions(fp)

            transition_in = clip.get("transitionIn")

            # Video layer: only render when track is visible (eye open).
            # Audio from the same clip is extracted separately below and is
            # gated by muted, not by visible — so invisible tracks can still
            # contribute audio (eye closed, ear open).
            if t_visible:
                video_clips.append(CompositorClip(
                    clip_id=clip.get("id", ""),
                    type="image" if is_img else "video",
                    filepath=str(Path(fp).resolve()),
                    input_index=idx,
                    src_width=src_w,
                    src_height=src_h,
                    has_audio=has_audio and not t_muted,
                    timeline_in=tl_in,
                    timeline_out=tl_out,
                    source_in=src_in,
                    source_out=src_out,
                    center_x=clip.get("centerX", 50),
                    center_y=clip.get("centerY", 50),
                    scale=clip.get("scale", 100),
                    opacity=clip.get("opacity", 100),
                    effect=clip.get("effect", ""),
                    transition_in=transition_in if transition_in and transition_in.get("key") else None,
                    track_index=ti,
                    is_image=is_img,
                ))

            # Audio from video clips: gated by muted only (not visible).
            # An invisible but unmuted track still contributes its audio.
            if has_audio and not t_muted:
                audio_clips.append(CompositorAudioClip(
                    filepath=str(Path(fp).resolve()),
                    input_index=idx,
                    timeline_in=tl_in,
                    timeline_out=tl_out,
                    source_in=src_in,
                    source_out=src_out,
                    track_index=ti,
                ))

    # Sort video clips: frontend convention — track[0] is the top layer.
    # Higher track_index = deeper layer (rendered first).  Within the same
    # track layers are sorted by timeline_in so earlier clips draw first.
    # This is the reverse of the timeline spec, matching actual editor usage.
    video_clips.sort(key=lambda c: (-c.track_index, c.timeline_in))
    audio_clips.sort(key=lambda c: (c.track_index, c.timeline_in))

    return video_clips, audio_clips, max_end, input_files


# ── Filter graph builder ──

def _build_filter_complex(
    video_clips: list[CompositorClip],
    audio_clips: list[CompositorAudioClip],
    total_dur: float,
    canvas_w: int,
    canvas_h: int,
    fps: int,
) -> tuple[str, str, bool]:
    """Build the complete ffmpeg filter_complex string.

    Returns (filter_graph, final_video_label, has_audio).
    """
    parts: list[str] = []

    saf = lambda v: f"{max(v, 0.01):.6f}"  # safe float for ffmpeg expressions

    # ── Phase A: Background canvas ──
    # Use color source then trim to exact duration
    parts.append(
        f"color=black:s={canvas_w}x{canvas_h}:r={fps},"
        f"trim=duration={saf(total_dur)},setpts=PTS-STARTPTS[bg0]"
    )
    current_bg = "bg0"

    # ── Phase B: Pre-compute gap-fill end times ──
    # Extend each clip's overlay to the next clip on the same track,
    # eliminating black frames caused by 1-frame gaps.
    def _next_same_track_start(this_i: int, this_track: int) -> Optional[float]:
        for j in range(this_i + 1, len(video_clips)):
            if video_clips[j].track_index == this_track:
                return video_clips[j].timeline_in
        return None

    # ── Phase C: Per-clip layer + overlay ──
    for i, clip in enumerate(video_clips):
        if not clip.filepath or not Path(clip.filepath).exists():
            continue

        layer_label = f"L{i}"
        bg_next = f"bg{i + 1}"

        # Compute geometry matching drawMediaToCanvas
        scaled_w, scaled_h, ox, oy = _compute_geometry(
            clip.src_width, clip.src_height,
            canvas_w, canvas_h,
            clip.center_x, clip.center_y, clip.scale,
        )

        clip_dur = clip.timeline_out - clip.timeline_in
        src_dur = clip.source_out - clip.source_in

        # Build the layer filter chain
        if clip.is_image:
            # Image: loop to create continuous video, then trim to duration,
            # then setpts to shift to timeline position
            trim_setpts = (
                f"loop=-1:1:0,"
                f"trim=duration={saf(src_dur)},"
                f"setpts=PTS-STARTPTS+{saf(clip.timeline_in)}/TB"
            )
        else:
            # Video: trim source range, then shift to timeline position
            trim_setpts = (
                f"trim=start={saf(clip.source_in)}:duration={saf(src_dur)},"
                f"setpts=PTS-STARTPTS+{saf(clip.timeline_in)}/TB"
            )

        # Scale to exact display size matching drawMediaToCanvas geometry
        scale_filter = f"scale={max(scaled_w, 2)}:{max(scaled_h, 2)}"

        # Effect filter
        fx = EFFECT_FILTERS.get(clip.effect, "")
        effect_chain = ""
        if fx:
            effect_chain = f",{fx}"

        # Opacity
        opacity_chain = ""
        if clip.opacity < 99.5:
            alpha = clip.opacity / 100.0
            opacity_chain = f",format=rgba,colorchannelmixer=aa={alpha:.3f}"

        # Transition fade-in
        fade_chain = ""
        if clip.transition_in:
            t_dur = (clip.transition_in.get("duration", 15) or 15) / fps
            fade_chain = f",fade=t=in:st=0:d={saf(t_dur)}"

        parts.append(
            f"[{clip.input_index}:v]"
            f"{trim_setpts},"
            f"{scale_filter}"
            f"{effect_chain}"
            f"{opacity_chain}"
            f"{fade_chain}"
            f"[{layer_label}]"
        )

        # Overlay this layer on the accumulated background.
        # Extend the enable window to the next clip on the same track so
        # 1-frame (or larger) gaps don't show as black frames.
        effective_out = _next_same_track_start(i, clip.track_index)
        if effective_out is None or effective_out <= clip.timeline_out:
            effective_out = clip.timeline_out
        enable = f"between(t,{saf(clip.timeline_in)},{saf(effective_out)})"
        parts.append(
            f"[{current_bg}][{layer_label}]"
            f"overlay={ox}:{oy}:enable='{enable}':eof_action=pass"
            f"[{bg_next}]"
        )

        current_bg = bg_next

    parts.append("")  # blank line for readability

    # ── Phase D: Audio ──
    has_audio = len(audio_clips) > 0
    if has_audio:
        a_labels = []
        for i, aclip in enumerate(audio_clips):
            if not aclip.filepath or not Path(aclip.filepath).exists():
                continue
            a_label = f"A{i}"
            a_labels.append(f"[{a_label}]")
            src_dur = aclip.source_out - aclip.source_in
            delay_ms = int(aclip.timeline_in * 1000)
            parts.append(
                f"[{aclip.input_index}:a]"
                f"atrim=start={saf(aclip.source_in)}:duration={saf(src_dur)},"
                f"adelay={delay_ms}|{delay_ms}"
                f"[{a_label}]"
            )

        if a_labels:
            mix_inputs = len(a_labels)
            a_labels_str = "".join(a_labels)
            parts.append(
                f"{a_labels_str}"
                f"amix=inputs={mix_inputs}:duration=longest:dropout_transition=0"
                f"[aout]"
            )
        else:
            has_audio = False

    result = ";".join(p for p in parts if p.strip())
    return result, current_bg, has_audio


# ── Execution ──

def composite_tracks(
    tracks: list[dict],
    output_path: str,
    fps: float = 30,
    target_w: int = 1920,
    target_h: int = 1080,
    temp_dir: str = "",
) -> str:
    """Composite multi-track timeline into a single video file.

    Args:
        tracks: Track data from GeneratedVideo.data.tracks JSON.
        output_path: Path for the output mp4 file.
        fps: Frame rate (default 30).
        target_w: Output width (default 1920).
        target_h: Output height (default 1080).
        temp_dir: Unused (kept for API compat); compositing is single-pass.

    Returns:
        Path to the composited output video.
    """
    video_clips, audio_clips, total_dur, input_files = _normalise_tracks(
        tracks, fps, target_w, target_h,
    )

    if not video_clips and not audio_clips:
        raise ValueError("没有可见的视频或音频素材可供合成")

    # Fallback duration if no video clips (audio-only)
    if total_dur <= 0 and audio_clips:
        total_dur = max(
            (ac.timeline_out for ac in audio_clips), default=3.0
        )
    if total_dur <= 0:
        total_dur = 3.0

    # Ensure output directory exists
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # Special case: audio-only, no video clips → black video with audio
    if not video_clips:
        # Create black video from color source with silent audio, then mix
        enc = _get_encoder()
        temp_vid = str(out.parent / f"_audio_only_bg_{out.stem}.mp4")
        dur = max(total_dur, 1.0)
        cmd_bg = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", f"color=black:s={target_w}x{target_h}:r={fps}:d={dur:.3f}",
            *enc,
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(temp_vid),
        ]
        _run(cmd_bg, check=True, capture_output=True)
        # Now mix audio into this black video
        from .ffmpeg import mix_audio_tracks
        audio_files = list(dict.fromkeys(ac.filepath for ac in audio_clips))
        output_path = mix_audio_tracks(temp_vid, audio_files, output_path)
        try:
            Path(temp_vid).unlink(missing_ok=True)
        except Exception:
            pass
        return output_path

    # Build filter complex
    filter_graph, final_bg_label, has_audio_out = _build_filter_complex(
        video_clips, audio_clips,
        total_dur, target_w, target_h, int(fps),
    )

    enc = _get_encoder()

    # Build ffmpeg command
    cmd = [FFMPEG, "-y"]

    # Input files — loop image inputs so -shortest doesn't truncate them
    _img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    for fp in input_files:
        if Path(fp).suffix.lower() in _img_exts:
            cmd.extend(["-stream_loop", "-1"])
        cmd.extend(["-i", str(fp)])

    cmd.extend(["-filter_complex", filter_graph])

    # Map final video label
    cmd.extend(["-map", f"[{final_bg_label}]"])

    # Map audio
    if has_audio_out:
        cmd.extend(["-map", "[aout]"])
    else:
        cmd.extend(["-an"])

    cmd.extend(enc)
    cmd.extend(["-pix_fmt", "yuv420p"])
    cmd.extend(["-t", f"{total_dur:.6f}"])
    cmd.extend(["-map_metadata", "-1"])
    cmd.append(str(out))

    logger.info("compositor: %d video layers, %d audio layers, %.1fs duration",
                 len(video_clips), len(audio_clips), total_dur)

    try:
        result = _run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr[-2000:] if result.stderr else "(no stderr)"
            raise RuntimeError(
                f"ffmpeg compositor failed (exit {result.returncode}):\n{stderr}"
            )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr[-2000:] if e.stderr else "(no stderr)"
        raise RuntimeError(
            f"ffmpeg compositor failed (exit {e.returncode}):\n{stderr}"
        )

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("合成输出文件为空")

    return str(out)
