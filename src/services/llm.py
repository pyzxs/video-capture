"""基于智能体的文本扩写与优化，搜索查询切分。"""

import re

from src.services.agents import call_agent


def optimize_text(text: str, style: str = "自然流畅") -> str:
    """使用智能体「字幕优化」优化字幕文本。

    如果智能体未配置则直接返回原文。
    """
    user_message = f"文本：\n{text}\n\n风格：{style}"
    return call_agent("srt_sub", user_message)


def expand_text(text: str) -> str:
    """使用智能体「内容扩写」将简短输入扩写为叙事脚本。

    如果智能体未配置则直接返回原文。
    """
    return call_agent("content-extend", text, max_tokens=3000)


_SENTENCE_SPLIT_RE = re.compile(r"[。！？\n]+")


def split_sentences(text: str) -> list[str]:
    """将文本按句号、感叹号、问号、换行拆分为句子列表，过滤空白。"""
    raw = _SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in raw if s.strip()]


def search_queries(script: str) -> list[str]:
    """将扩写脚本拆分为多个搜索查询。

    先按句拆分，再将过短的句子（< 8 字）合并到上一句，
    保证每个查询有足够语义信息量。
    """
    sentences = split_sentences(script)
    if not sentences:
        return []

    queries = []
    buf = sentences[0]
    for s in sentences[1:]:
        if len(s) < 8:
            buf += s
        else:
            queries.append(buf)
            buf = s
    if buf:
        queries.append(buf)
    return queries
