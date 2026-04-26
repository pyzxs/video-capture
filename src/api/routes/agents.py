from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import (
    AgentChatRequest, AgentChatResponse, AgentCreate, AgentOut,
    AgentUpdate,
)
from src.config import get_config
from src.logger import get_logger
from src.db.models import Agent

logger = get_logger("api.agents")

router = APIRouter(prefix="/agents", tags=["智能体管理"])


# ── Agent CRUD ──

@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.query(Agent).order_by(Agent.id).all()


@router.post("", response_model=AgentOut)
def create_agent(data: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(**data.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.put("/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: int, data: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise HTTPException(404, "智能体不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(agent, k, v)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise HTTPException(404, "智能体不存在")
    db.delete(agent)
    db.commit()
    return {"ok": True}


# ── Chat / Test ──

def _llm_model():
    """返回带 provider 前缀的完整模型名。"""
    model = get_config("llm_model")
    provider = get_config("llm_provider")
    if provider and "/" not in model:
        return f"{provider}/{model}"
    return model


def _get_llm_config():
    """从系统配置读取大模型信息。"""
    return {
        "model": _llm_model(),
        "api_key": get_config("llm_api_key"),
        "api_base": get_config("llm_base_url"),
    }


def _call_llm(agent: Agent, req: AgentChatRequest) -> str:
    """调用系统配置的大模型。"""
    from litellm import completion

    cfg = _get_llm_config()
    messages = [{"role": "system", "content": req.prompt or agent.prompt}]
    messages.extend(req.messages)

    try:
        response = completion(
            model=cfg["model"],
            messages=messages,
            api_key=cfg["api_key"] or None,
            api_base=cfg["api_base"] or None,
            max_tokens=req.max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        raise HTTPException(502, f"大模型调用失败: {e}")


@router.post("/by-key/{key}/chat", response_model=AgentChatResponse)
def chat_with_agent_by_key(key: str, req: AgentChatRequest, db: Session = Depends(get_db)):
    """按 key 调用智能体"""
    agent = db.query(Agent).filter(Agent.key == key).first()
    if not agent:
        raise HTTPException(404, f"智能体 '{key}' 不存在")
    return AgentChatResponse(content=_call_llm(agent, req))


@router.post("/by-name/{name}/chat", response_model=AgentChatResponse)
def chat_with_agent_by_name(name: str, req: AgentChatRequest, db: Session = Depends(get_db)):
    """按名称调用智能体（旧版兼容）"""
    agent = db.query(Agent).filter(Agent.name == name).first()
    if not agent:
        raise HTTPException(404, f"智能体 '{name}' 不存在")
    return AgentChatResponse(content=_call_llm(agent, req))


@router.post("/{agent_id}/chat", response_model=AgentChatResponse)
def chat_with_agent(agent_id: int, req: AgentChatRequest, db: Session = Depends(get_db)):
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise HTTPException(404, "智能体不存在")
    return AgentChatResponse(content=_call_llm(agent, req))
