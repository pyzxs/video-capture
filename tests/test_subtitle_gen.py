"""测试 SRT 字幕生成。"""

from src.query.subtitle_gen import generate_srt


def test_empty_paragraphs():
    assert generate_srt("你好", []) == ""


def test_single_paragraph():
    paras = [{"start_time": 0.0, "end_time": 2.5}]
    result = generate_srt("你好世界", paras)
    assert "00:00:00,000 --> 00:00:02,500" in result
    assert "你好世界" in result


def test_multiple_paragraphs():
    paras = [
        {"start_time": 0.0, "end_time": 2.0},
        {"start_time": 3.0, "end_time": 5.0},
    ]
    result = generate_srt("你好世界", paras)
    lines = result.strip().split("\n\n")
    assert len(lines) == 2
    assert "你好" in lines[0] or "世界" in lines[0]
    assert "你好" in lines[1] or "世界" in lines[1]


def test_srt_format_structure():
    paras = [{"start_time": 1.0, "end_time": 3.0}]
    result = generate_srt("测试", paras)
    lines = result.splitlines()
    assert lines[0] == "1"                    # 序号
    assert "-->" in lines[1]                  # 时间轴
    assert lines[2] == "测试"                  # 文本
    assert result.endswith("\n")              # 以空行结尾
