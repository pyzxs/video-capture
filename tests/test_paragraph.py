"""测试段落合并逻辑。"""

from unittest.mock import patch

from src.processing.paragraph import merge_into_paragraphs

# ── 基于时间间隔的合并 ──


def test_empty_segments():
    assert merge_into_paragraphs([], use_llm=False) == []


def test_single_segment():
    segs = [{"start": 0.0, "end": 2.5, "text": "你好"}]
    result = merge_into_paragraphs(segs, use_llm=False)
    assert len(result) == 1
    assert result[0]["text"] == "你好"
    assert result[0]["start"] == 0.0
    assert result[0]["end"] == 2.5
    assert result[0]["seq_index"] == 0


def test_merge_adjacent_segments():
    segs = [
        {"start": 0.0, "end": 2.0, "text": "你好"},
        {"start": 2.5, "end": 4.0, "text": "世界"},
    ]
    result = merge_into_paragraphs(segs, use_llm=False)
    assert len(result) == 1
    assert result[0]["text"] == "你好世界"
    assert result[0]["start"] == 0.0
    assert result[0]["end"] == 4.0


def test_split_distant_segments():
    segs = [
        {"start": 0.0, "end": 2.0, "text": "你好"},
        {"start": 10.0, "end": 12.0, "text": "世界"},
    ]
    result = merge_into_paragraphs(segs, use_llm=False)
    assert len(result) == 2
    assert result[0]["text"] == "你好"
    assert result[1]["text"] == "世界"
    assert result[1]["seq_index"] == 1


def test_seq_index_assignment():
    segs = [
        {"start": 0.0, "end": 1.0, "text": "A"},
        {"start": 5.0, "end": 6.0, "text": "B"},
        {"start": 6.5, "end": 7.0, "text": "C"},
    ]
    result = merge_into_paragraphs(segs, use_llm=False)
    assert len(result) == 2  # B 和 C 合并
    assert result[0]["seq_index"] == 0
    assert result[1]["seq_index"] == 1


# ── 基于大模型分析的合并 ──


def test_llm_merge_basic():
    segs = [
        {"start": 0.0, "end": 1.0, "text": "今天天气真不错。"},
        {"start": 1.5, "end": 2.5, "text": "我们一起去公园吧。"},
        {"start": 5.0, "end": 6.0, "text": "明天要开会。"},
    ]
    with patch(
        "src.processing.paragraph._call_llm",
        return_value="[0-1]\n[2-2]",
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) == 2
    assert result[0]["text"] == "今天天气真不错。我们一起去公园吧。"
    assert result[0]["start"] == 0.0
    assert result[0]["end"] == 2.5
    assert result[0]["seq_index"] == 0

    assert result[1]["text"] == "明天要开会。"
    assert result[1]["start"] == 5.0
    assert result[1]["end"] == 6.0
    assert result[1]["seq_index"] == 1


def test_llm_merge_all_in_one():
    segs = [
        {"start": 0.0, "end": 1.0, "text": "第一步"},
        {"start": 1.5, "end": 2.0, "text": "第二步"},
        {"start": 2.5, "end": 3.0, "text": "第三步"},
    ]
    with patch(
        "src.processing.paragraph._call_llm",
        return_value="[0-2]",
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) == 1
    assert result[0]["text"] == "第一步第二步第三步"


def test_llm_merge_unparseable_fallback():
    """LLM 返回无法解析的格式时，回退到时间间隔合并。"""
    segs = [
        {"start": 0.0, "end": 1.0, "text": "A"},
        {"start": 5.0, "end": 6.0, "text": "B"},
    ]
    with patch(
        "src.processing.paragraph._call_llm",
        return_value="我不确定怎么分",
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) == 2  # 回退，间隔 > 2s 所以分开


def test_llm_merge_api_error_fallback():
    """API 调用异常时回退到时间间隔合并。"""
    segs = [
        {"start": 0.0, "end": 1.0, "text": "A"},
        {"start": 1.5, "end": 2.0, "text": "B"},
    ]
    with patch(
        "src.processing.paragraph._call_llm",
        side_effect=RuntimeError("API error"),
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) == 1  # 回退后间隔 <= 2s 合并


def test_llm_merge_skip_intro():
    """LLM 应丢弃与主题无关的片头片段。"""
    segs = [
        {"start": 0.0, "end": 1.0, "text": "大家好欢迎来到我的频道"},
        {"start": 1.5, "end": 3.0, "text": "今天我们来聊聊人工智能。"},
        {"start": 3.5, "end": 5.0, "text": "AI正在改变我们的生活方式。"},
        {"start": 6.0, "end": 7.0, "text": "别忘了点赞订阅我们下期再见"},
    ]
    # 丢弃 [0] 片头和 [3] 片尾，只保留正文 [1-2]
    with patch(
        "src.processing.paragraph._call_llm",
        return_value="[1-2]",
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) == 1
    assert result[0]["start"] == 1.5
    assert result[0]["end"] == 5.0
    assert "人工智能" in result[0]["text"]
    assert "大家好" not in result[0]["text"]


def test_llm_merge_skip_multiple_irrelevant():
    """丢弃多个无关片段，只保留中间主题段落。"""
    segs = [
        {"start": 0.0, "end": 2.0, "text": "赞助商广告"},
        {"start": 2.5, "end": 4.0, "text": "正文内容第一部分"},
        {"start": 4.5, "end": 6.0, "text": "正文内容第二部分"},
        {"start": 7.0, "end": 9.0, "text": "感谢观看下次再见"},
    ]
    with patch(
        "src.processing.paragraph._call_llm",
        return_value="[1-2]",
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) == 1
    assert "赞助商" not in result[0]["text"]
    assert "感谢观看" not in result[0]["text"]
    assert result[0]["text"] == "正文内容第一部分正文内容第二部分"


def test_llm_merge_all_filtered_fallback():
    """所有片段都被丢弃时回退到时间间隔合并。"""
    segs = [
        {"start": 0.0, "end": 1.0, "text": "广告1"},
        {"start": 5.0, "end": 6.0, "text": "广告2"},
    ]
    with patch(
        "src.processing.paragraph._call_llm",
        return_value="",  # 没有输出任何段落
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) == 2  # 回退到时间间隔合并


def test_llm_merge_large_pre_grouping():
    """超过 50 个片段时先粗分组再 LLM 精分。"""
    segs = [
        {"start": float(i), "end": float(i) + 0.5, "text": f"片段{i}"}
        for i in range(55)
    ]
    with patch(
        "src.processing.paragraph._call_llm",
        return_value="[0-3]",
    ):
        result = merge_into_paragraphs(segs)

    assert len(result) > 0
    for p in result:
        assert "start" in p
        assert "end" in p
        assert "text" in p
        assert "seq_index" in p
