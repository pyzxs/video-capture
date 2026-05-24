"""Timeline builder — fluent API for constructing video-editing data and compositing.

Canonical usage:

    # Compose from scratch
    t = timeline().track(
        video_track("主轨道").clip(
            video_clip("a.mp4").start(0).end(300).center(50, 50).scale(100)
        ).clip(
            text_clip("Hello").start(0).end(150).font_size(64).center(50, 90)
        )
    ).track(
        audio_track("BGM").clip(
            audio_clip("bgm.mp3").start(0).end(450)
        )
    ).tojson()

    # Create from existing GeneratedVideo data
    t = timeline().create(gen.data).todict()
    t = timeline().create(gen.data).tojson()
    t = timeline().create(gen.data).generate(db, output_path)
"""

import json
import uuid
from pathlib import Path
from typing import Optional


# ── helpers ──

def _new_id() -> str:
    return f"c-{uuid.uuid4().hex[:7]}"


# ── Clip ──

class Clip:
    """Leaf node — a single media / text segment on the timeline."""

    def __init__(self, filepath: str = ""):
        self._d: dict = {"id": _new_id()}
        if filepath:
            self._d["filepath"] = filepath
            # auto-detect type from extension
            ext = Path(filepath).suffix.lower()
            if ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                self._d["type"] = "image"
            elif ext in (".mp3", ".wav", ".aac", ".ogg", ".m4a", ".flac"):
                self._d["type"] = "audio"
            else:
                self._d["type"] = "video"

    # ── type ──

    def video(self) -> "Clip":
        self._d["type"] = "video"
        return self

    def image(self) -> "Clip":
        self._d["type"] = "image"
        return self

    def audio(self) -> "Clip":
        self._d["type"] = "audio"
        return self

    def text(self, content: str = "") -> "Clip":
        self._d["type"] = "text"
        if content:
            self._d["content"] = content
        return self

    # ── identity ──

    def id(self, cid: str) -> "Clip":
        self._d["id"] = cid
        return self

    def material_id(self, mid: int) -> "Clip":
        self._d["materialId"] = mid
        if "filepath" in self._d:
            del self._d["filepath"]
        return self

    def filepath(self, fp: str) -> "Clip":
        self._d["filepath"] = fp
        if "materialId" in self._d:
            del self._d["materialId"]
        return self

    def content(self, c: str) -> "Clip":
        self._d["content"] = c
        return self

    # ── timeline positioning (frames) ──

    def start(self, s: float) -> "Clip":
        self._d["start"] = s
        return self

    def end(self, e: float) -> "Clip":
        self._d["end"] = e
        return self

    def offset_l(self, ol: float) -> "Clip":
        self._d["offsetL"] = ol
        return self

    def offset_r(self, or_: float) -> "Clip":
        self._d["offsetR"] = or_
        return self

    # ── visual (video / image) ──

    def center(self, cx: float, cy: float) -> "Clip":
        self._d["centerX"] = cx
        self._d["centerY"] = cy
        return self

    def center_x(self, cx: float) -> "Clip":
        self._d["centerX"] = cx
        return self

    def center_y(self, cy: float) -> "Clip":
        self._d["centerY"] = cy
        return self

    def scale(self, s: float) -> "Clip":
        self._d["scale"] = s
        return self

    def opacity(self, o: float) -> "Clip":
        self._d["opacity"] = o
        return self

    def width(self, w: int) -> "Clip":
        self._d["width"] = w
        return self

    def height(self, h: int) -> "Clip":
        self._d["height"] = h
        return self

    # ── visual (text) ──

    def font_size(self, fs: int) -> "Clip":
        self._d["fontSize"] = fs
        return self

    def font_family(self, ff: str) -> "Clip":
        self._d["fontFamily"] = ff
        return self

    def font_color(self, fc: str) -> "Clip":
        self._d["fontColor"] = fc
        return self

    def text_align(self, ta: str) -> "Clip":
        self._d["textAlign"] = ta
        return self

    def bold(self, b: bool = True) -> "Clip":
        self._d["bold"] = b
        return self

    def italic(self, i: bool = True) -> "Clip":
        self._d["italic"] = i
        return self

    def outline(self, o: bool = True, color: str = "#000000") -> "Clip":
        self._d["outline"] = o
        self._d["outlineColor"] = color
        return self

    def shadow(self, s: bool = True) -> "Clip":
        self._d["shadow"] = s
        return self

    def background(self, enabled: bool = True, color: str = "#000000") -> "Clip":
        self._d["bgEnabled"] = enabled
        self._d["bgColor"] = color
        return self

    # ── effect ──

    def effect(self, name: str) -> "Clip":
        self._d["effect"] = name
        return self

    def transition_in(self, name: str, duration: int = 15) -> "Clip":
        self._d["transitionIn"] = name
        if duration != 15:
            self._d["transitionInDuration"] = duration
        return self

    # ── internals ──

    def _build(self) -> dict:
        s = self._d.get("start", 0) or 0
        e = self._d.get("end", 0) or 0
        if e > s and "frameCount" not in self._d:
            self._d["frameCount"] = e - s
        return self._d


# ── Track ──

class Track:
    """Intermediate node — a single track (video / audio / subtitle / effect)."""

    def __init__(self, type: str = "video", name: str = ""):
        self._d = {
            "type": type,
            "name": name,
            "list": [],
            "visible": True,
            "locked": False,
            "muted": False,
        }

    def clip(self, clip: Clip) -> "Track":
        self._d["list"].append(clip._build())
        return self

    def name(self, n: str) -> "Track":
        self._d["name"] = n
        return self

    def muted(self, m: bool = True) -> "Track":
        self._d["muted"] = m
        return self

    def visible(self, v: bool = True) -> "Track":
        self._d["visible"] = v
        return self

    def locked(self, l: bool = True) -> "Track":
        self._d["locked"] = l
        return self

    def main(self) -> "Track":
        self._d["mainTrack"] = True
        return self

    def _build(self) -> dict:
        return self._d


# ── Timeline ──

class Timeline:
    """Top-level builder. Holds a list of tracks and supports serialisation + compositing."""

    def __init__(self, data: dict | str | None = None):
        self._tracks: list[dict] = []
        self._show_subtitles = False
        self._fps = 30
        if data is not None:
            self._parse(data)

    # ── factory ──

    @classmethod
    def create(cls, data: dict | str) -> "Timeline":
        """Create a Timeline from existing data (dict or JSON string)."""
        return cls(data)

    def _parse(self, data: dict | str):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}
        if not isinstance(data, dict):
            return
        self._tracks = data.get("tracks", [])
        self._show_subtitles = data.get("showSubtitles", False)
        self._fps = data.get("fps", 30)

    # ── builder ──

    def track(self, track: Track) -> "Timeline":
        self._tracks.append(track._build())
        return self

    def show_subtitles(self, v: bool = True) -> "Timeline":
        self._show_subtitles = v
        return self

    def fps(self, v: int) -> "Timeline":
        self._fps = v
        return self

    # ── serialisation ──

    def todict(self) -> dict:
        result: dict = {"tracks": self._tracks}
        if self._show_subtitles:
            result["showSubtitles"] = self._show_subtitles
        if self._fps != 30:
            result["fps"] = self._fps
        return result

    def tojson(self, indent: int = 2) -> str:
        return json.dumps(self.todict(), ensure_ascii=False, indent=indent)

    # ── compositing ──

    def generate(
        self,
        output_path: str,
        fps: float = 30,
        target_w: int = 1920,
        target_h: int = 1080,
        temp_dir: str = "",
    ) -> str:
        """Composite tracks into a video file.

        Returns the output_path on success.  Raises ValueError / RuntimeError on failure.
        """
        from .compositor import composite_tracks
        return composite_tracks(self._tracks, output_path, fps, target_w, target_h, temp_dir)

    def generate_with_subtitles(
        self,
        output_path: str,
        fps: float = 30,
        target_w: int = 1920,
        target_h: int = 1080,
        temp_dir: str = "",
        gen_id: int = 0,
    ) -> str:
        """Composite tracks + apply text-subtitle overlays.

        Post-processing: renders text clips as ASS subtitles and burns them in.
        Also runs ASR if showSubtitles=True and no text clips present.
        """
        from ..api.services.generated_service import _write_ass, _write_asr_ass, _post_composite_subtitles

        out = self.generate(output_path, fps, target_w, target_h, temp_dir)
        out, _ = _post_composite_subtitles(
            self._tracks, out, fps, target_w, target_h, gen_id, self._show_subtitles,
        )
        return out


# ── public constructors (short names) ──

def timeline(data: dict | str | None = None) -> Timeline:
    """Create a new Timeline, optionally from existing data."""
    return Timeline(data)


def video_track(name: str = "") -> Track:
    """Create a video track."""
    return Track("video", name)


def audio_track(name: str = "") -> Track:
    """Create an audio track."""
    return Track("audio", name)


def subtitle_track(name: str = "") -> Track:
    """Create a subtitle track."""
    return Track("subtitle", name)


def video_clip(filepath: str = "") -> Clip:
    """Create a video clip."""
    c = Clip(filepath)
    c._d["type"] = "video"
    return c


def image_clip(filepath: str = "") -> Clip:
    """Create an image clip."""
    c = Clip(filepath)
    c._d["type"] = "image"
    return c


def audio_clip(filepath: str = "") -> Clip:
    """Create an audio clip."""
    c = Clip(filepath)
    c._d["type"] = "audio"
    return c


def text_clip(content: str = "") -> Clip:
    """Create a text clip."""
    c = Clip()
    c._d["type"] = "text"
    if content:
        c._d["content"] = content
    return c


def clip(filepath: str = "") -> Clip:
    """Create a generic clip (type auto-detected from extension)."""
    return Clip(filepath)
