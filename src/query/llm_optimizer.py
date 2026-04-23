import re

from src.config import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, LLM_MODEL


def _call(text: str, prompt_template: str, max_tokens: int = 2000) -> str:
    """调用兼容 Anthropic 格式的 LLM API。"""
    if not ANTHROPIC_API_KEY:
        return text

    import anthropic

    kwargs = {"api_key": ANTHROPIC_API_KEY}
    if ANTHROPIC_BASE_URL:
        kwargs["base_url"] = ANTHROPIC_BASE_URL
    client = anthropic.Anthropic(**kwargs)

    prompt = prompt_template.format(text=text)

    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def optimize_text(text: str, style: str = "自然流畅") -> str:
    """使用 LLM API 优化字幕文本以提高可读性。

    如果未配置 API 密钥，则直接返回原文。
    """
    prompt = (
        "请优化下面的视频字幕文本，要求：\n"
        "0. 必须只输出优化后的文本，不要输出任何其他内容，不要解释，不要前缀\n"
        "1. 保持原意不变\n"
        f"2. 语言{style}，适合作为视频字幕展示\n"
        "3. 修正可能的语法错误和不自然的表达\n"
        "4. 保持原文的长度大致不变\n\n"
        "原文：\n{text}\n\n"
        "优化后的文本："
    )
    return _call(text, prompt)


def expand_text(text: str) -> str:
    """将简短的输入用 LLM 扩写为丰富连贯的叙事脚本。

    用于混剪流程：扩写文本 → 搜索素材 → 配音。
    如果未配置 API 密钥，则直接返回原文。
    """
    if not ANTHROPIC_API_KEY:
        return text

    prompt = (
        "请根据下面这段文字，扩写一段自然流畅的配音脚本。要求：\n"
        "0. 必须只输出扩写后的文本，不要输出任何其他内容，不要解释，不要前缀\n"
        "1. 保持原意不变，扩展细节和描述\n"
        "2. 语言口语化、自然，适合作为视频配音\n"
        "3. 长度在 200-500 字之间\n"
        "4. 不要使用任何格式标记或特殊符号\n\n"
        "原文：\n{text}\n\n"
        "扩写后的配音脚本："
    )
    return _call(text, prompt, max_tokens=3000)


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
