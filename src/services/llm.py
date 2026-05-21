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


def generate_title(script: str, materials: list[dict] | None = None) -> str:
    """根据脚本内容和素材文本生成简短视频标题。

    尝试调用 LLM 生成标题，失败则提取首句。
    """
    from src.config import get_config
    from src.logger import default_logger as logger

    context = script[:300]
    if materials:
        mat_texts = [m.get("content", "") for m in materials[:5] if m.get("content")]
        if mat_texts:
            context += "\n素材关键词：" + "；".join(t[:30] for t in mat_texts)

    try:
        from src.auth import get_auth_headers, update_local_quota
        from src.http_client import sync_post
        from src.services.agents import _llm_model

        api_key = get_config("api_key")
        cms_url = get_config("cms_base_url")
        if api_key and cms_url:
            headers = {"Content-Type": "application/json", **get_auth_headers()}
            body = {
                "model": _llm_model(),
                "messages": [
                    {"role": "system", "content": "根据用户提供的视频脚本和素材信息，生成一个简短的视频标题。要求：不超过15个字，不加引号，不解释，只输出标题本身。"},
                    {"role": "user", "content": context},
                ],
                "max_tokens": 50,
            }
            resp = sync_post(f"{cms_url}/api/proxy/llm", json=body, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                llm_resp = data.get("data", {})
                title = llm_resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                remaining = llm_resp.get("x_quota_remaining")
                if remaining is not None:
                    update_local_quota(remaining)
                if title:
                    return title[:30]
    except Exception as e:
        logger.debug("LLM 标题生成失败，使用回退: %s", e)

    return _title_fallback(script)


def _title_fallback(text: str) -> str:
    """从文本中提取首句作为标题。"""
    text = re.sub(r"[#*\-\[\]()（）]", "", text).strip()
    first_line = text.split("\n")[0].strip()
    sentence = re.split(r"[。！？，,\n]", first_line)[0].strip()
    if len(sentence) > 20:
        sentence = sentence[:20]
    return sentence or text[:20]


def refine_dubbing_script(theme: str, material_texts: list[str], duration: float, variation: int = 0) -> str:
    """根据核心主题、素材文案和视频时长，生成适配配音的脚本。

    参数：
        theme: 核心职责/主题描述
        material_texts: 检索出的素材文案列表（按顺序）
        duration: 拼接视频总时长（秒）
        variation: 变体编号，>0 时提示 LLM 生成不同版本

    返回优化后的配音脚本文本。
    """
    from src.config import get_config
    from src.logger import default_logger as logger

    max_chars = int(duration * 4)
    merged = "\n".join(t for t in material_texts if t.strip())
    if not merged.strip():
        return theme[:max_chars]

    try:
        from src.auth import get_auth_headers, update_local_quota
        from src.http_client import sync_post
        from src.services.agents import _llm_model

        api_key = get_config("api_key")
        cms_url = get_config("cms_base_url")
        if not api_key or not cms_url:
            logger.warning("CMS 未配置，使用素材文案拼接")
            return merged[:max_chars]

        variation_hint = ""
        if variation > 0:
            variation_hint = (
                f"\n7. 这是第 {variation + 1} 个版本，请使用不同的叙述角度、语气和表达方式，"
                "与其他版本产生明显差异，可以调整素材的侧重点和详略"
            )

        system_prompt = (
            "你是视频配音脚本优化专家。用户会提供：核心主题、素材文案片段列表、目标时长。\n"
            "请根据核心主题的方向，将素材文案合并、梳理、优化为一段连贯自然的配音文稿。\n"
            "要求：\n"
            f"1. 总字数严格控制在 {max_chars} 字以内（视频 {duration:.0f} 秒，语速约4字/秒）\n"
            "2. 保持素材的顺序逻辑，使内容衔接流畅\n"
            "3. 围绕核心主题进行内容取舍和润色，删除与主题无关的内容\n"
            "4. 语言口语化、自然，适合作为视频旁白/配音\n"
            "5. 不要使用任何格式标记或特殊符号\n"
            "6. 只输出优化后的配音文稿，不要解释、不要前缀"
            f"{variation_hint}"
        )
        user_content = f"核心主题：{theme}\n\n素材文案（按视频顺序）：\n{merged[:2000]}\n\n目标时长：{duration:.0f}秒（约{max_chars}字）"

        headers = {"Content-Type": "application/json", **get_auth_headers()}
        body = {
            "model": _llm_model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": min(max_chars * 2, 4000),
        }
        if variation > 0:
            body["temperature"] = 1.0
        resp = sync_post(f"{cms_url}/api/proxy/llm", json=body, headers=headers, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            llm_resp = data.get("data", {})
            result = llm_resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            remaining = llm_resp.get("x_quota_remaining")
            if remaining is not None:
                update_local_quota(remaining)
            if result:
                return result[:max_chars]
    except Exception as e:
        logger.warning("配音脚本优化失败，使用素材文案拼接: %s", e)

    return merged[:max_chars]


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
