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



def _call_llm(agent: Agent, req: AgentChatRequest) -> str:
    """通过 CMS 代理调用大模型。"""
    import requests
    from src.auth import get_auth_headers, update_local_quota

    cms_url = get_config("cms_base_url")
    api_key = get_config("api_key")
    if not api_key:
        raise HTTPException(502, "未注册 CMS 用户，无法调用大模型")

    model = _llm_model()
    messages = [{"role": "system", "content": req.prompt or agent.prompt}]
    messages.extend(req.messages)

    try:
        headers = {"Content-Type": "application/json", **get_auth_headers()}
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": req.max_tokens,
        }
        resp = requests.post(
            f"{cms_url}/api/proxy/llm",
            json=body, headers=headers, timeout=120,
        )
        if resp.status_code == 402:
            raise HTTPException(402, "CMS 额度不足，请充值")
        if resp.status_code >= 400:
            logger.error("CMS LLM 代理错误 (HTTP %s): %s", resp.status_code, resp.text[:200])
            raise HTTPException(502, f"大模型调用失败: {resp.text[:200]}")

        data = resp.json()
        llm_response = data.get("data", {})
        text = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        remaining = llm_response.get("x_quota_remaining")
        if remaining is not None:
            update_local_quota(remaining)
        return text or ""
    except requests.RequestException as e:
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
