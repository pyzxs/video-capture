"""测试字幕文件解析（SRT / ASS）。"""

import tempfile
from pathlib import Path

from src.utils import parse_ass, parse_srt


def test_parse_srt_basic():
    content = """1
00:00:01,000 --> 00:00:04,000
你好世界

2
00:00:05,000 --> 00:00:08,500
这是第二句
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        segs = parse_srt(path)
        assert len(segs) == 2
        assert segs[0]["start"] == 1.0
        assert segs[0]["end"] == 4.0
        assert segs[0]["text"] == "你好世界"
        assert segs[1]["start"] == 5.0
        assert segs[1]["end"] == 8.5
        assert segs[1]["text"] == "这是第二句"
    finally:
        Path(path).unlink()


def test_parse_srt_html_tags():
    content = """1
00:00:01,000 --> 00:00:03,000
<b>粗体</b>和<i>斜体</i>
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        segs = parse_srt(path)
        assert len(segs) == 1
        assert segs[0]["text"] == "粗体和斜体"
    finally:
        Path(path).unlink()


def test_parse_srt_multiline():
    content = """1
00:00:01,000 --> 00:00:03,000
第一行
第二行
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        segs = parse_srt(path)
        assert len(segs) == 1
        assert segs[0]["text"] == "第一行 第二行"
    finally:
        Path(path).unlink()


def test_parse_srt_empty_text():
    content = """1
00:00:01,000 --> 00:00:03,000

"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        segs = parse_srt(path)
        assert len(segs) == 0
    finally:
        Path(path).unlink()


def test_parse_ass_basic():
    content = """[Script Info]
Title: test

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,你好世界
Dialogue: 0,0:00:05.00,0:00:08.50,Default,,0,0,0,,这是第二句
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        segs = parse_ass(path)
        assert len(segs) == 2
        assert segs[0]["start"] == 1.0
        assert segs[0]["end"] == 4.0
        assert segs[0]["text"] == "你好世界"
        assert segs[1]["start"] == 5.0
        assert segs[1]["end"] == 8.5
    finally:
        Path(path).unlink()


def test_parse_ass_override_tags():
    content = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\\fn微软雅黑}你好{\\r}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        segs = parse_ass(path)
        assert len(segs) == 1
        assert segs[0]["text"] == "你好"
    finally:
        Path(path).unlink()


def test_parse_ass_newline():
    content = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,第一行\\N第二行
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", encoding="utf-8", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        segs = parse_ass(path)
        assert len(segs) == 1
        assert segs[0]["text"] == "第一行 第二行"
    finally:
        Path(path).unlink()
