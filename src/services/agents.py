"""智能体查找与调用（大模型从系统配置读取）。"""

from src.config import get_config
from src.logger import get_logger

logger = get_logger("agents")


def _llm_model():
    """返回带 provider 前缀的完整模型名，例如 deepseek/DeepSeek-V3.2。"""
    model = get_config("llm_model")
    provider = get_config("llm_provider")
    if provider and "/" not in model:
        return f"{provider}/{model}"
    return model


def get_agent_by_key(key: str) -> dict | None:
    """按 key 查询智能体。

    返回 {"agent": agent} 字典，未找到时返回 None。
    """
    from src.db.engine import SessionLocal
    from src.db.models import Agent

    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.key == key).first()
        if not agent:
            return None
        return {"agent": agent}
    finally:
        db.close()


def call_agent(agent_key: str, user_message: str, max_tokens: int = 2000) -> str:
    """调用指定 key 的智能体，使用系统配置的大模型，返回响应文本。

    流程：查询 agent → 获取系统 LLM 配置 → 通过 litellm 调用。
    若智能体不存在或 LLM 未配置则返回 user_message 原文。
    """
    from litellm import completion

    cfg = get_agent_by_key(agent_key)
    if not cfg:
        logger.warning("智能体 %s 未配置，返回原文", agent_key)
        return user_message

    agent = cfg["agent"]
    api_key = get_config("llm_api_key")
    if not api_key:
        logger.warning("系统未配置 llm_api_key，返回原文")
        return user_message

    try:
        response = completion(
            model=_llm_model(),
            messages=[
                {"role": "system", "content": agent.prompt},
                {"role": "user", "content": user_message},
            ],
            api_key=api_key,
            api_base=get_config("llm_base_url") or None,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("智能体 %s 调用失败: %s", agent_key, e)
        return user_message


def ensure_default_agents():
    """确保默认智能体条目存在（首次启动时调用）。"""
    from src.db.engine import SessionLocal
    from src.db.models import Agent

    db = SessionLocal()
    try:
        defaults = [
            {
                "key": "content-extend",
                "name": "内容扩写",
                "prompt": (
                    "你是一个视频配音脚本创作专家。请根据用户提供的文字，扩写一段自然流畅的配音脚本。\n"
                    "要求：\n"
                    "1. 保持原意不变，扩展细节和描述\n"
                    "2. 语言口语化、自然，适合作为视频配音\n"
                    "3. 长度在 200-500 字之间\n"
                    "4. 不要使用任何格式标记或特殊符号\n"
                    "5. 只输出扩写后的文本，不要输出任何其他内容，不要解释，不要前缀"
                ),
            },
            {
                "key": "srt_sub",
                "name": "字幕优化",
                "prompt": (
                    "你是一个视频字幕优化专家。请按照用户指定的风格优化字幕文本。\n"
                    "要求：\n"
                    "1. 保持原意不变\n"
                    "2. 修正可能的语法错误和不自然的表达\n"
                    "3. 保持原文的长度大致不变\n"
                    "4. 只输出优化后的文本，不要输出任何其他内容，不要解释，不要前缀"
                ),
            },
            {
                "key": "str_sem",
                "name": "字幕分段",
                "prompt": (
                    "你是一个视频字幕分段专家。请分析用户提供的 ASR 识别片段，完成两项任务：\n"
                    "任务一：识别哪些片段属于视频的主题内容（正文），"
                    "哪些属于无关的片头、片尾、过渡、开场白、赞助口播等，丢弃无关片段。\n"
                    "任务二：将保留的主题片段按语义完整性、话题转换合并为自然段落。\n\n"
                    "规则：\n"
                    "1. 保持片段原有的顺序，不能打乱\n"
                    "2. 每个段落包含至少1个连续保留的片段\n"
                    "3. 语义完整的地方断开（话题转换、完整句子结束等）\n"
                    "4. 只输出方括号格式，不要任何解释或额外文字\n"
                    "5. 被丢弃的片段不要出现在输出中\n\n"
                    "输出格式示例（丢弃了 [0] 和 [5] 两个无关片段）：\n"
                    "[1-2]\n"
                    "[3-4]"
                ),
            },
            {
                "key": "note_ast",
                "name": "笔记助手",
                "prompt": (
                    "你是一个笔记助手，帮助用户整理和优化笔记内容。\n"
                    "要求：\n"
                    "1. 保持原意不变\n"
                    "2. 优化表达，使内容更清晰有条理\n"
                    "3. 适当使用 Markdown 格式增强可读性\n"
                    "4. 只输出优化后的文本，不要输出任何其他内容"
                ),
            },
        ]

        for d in defaults:
            existing = db.query(Agent).filter(Agent.key == d["key"]).first()
            if not existing:
                agent = Agent(key=d["key"], name=d["name"], prompt=d["prompt"])
                db.add(agent)
                logger.info("已创建智能体: %s (%s)", d["name"], d["key"])

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
