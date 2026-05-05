"""Agent business logic: CRUD, LLM calling via CMS proxy."""
from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.api.schemas import AgentChatRequest, AgentChatResponse
from src.config import get_config
from src.db.models import Agent
from src.logger import get_logger

logger = get_logger("api.agents")


def _llm_model() -> str:
    model = get_config("llm_model")
    provider = get_config("llm_provider")
    if provider and "/" not in model:
        return f"{provider}/{model}"
    return model


def _call_llm(agent: Agent, req: AgentChatRequest) -> str:
    import requests
    from src.auth import get_auth_headers, update_local_quota

    cms_url = get_config("cms_base_url")
    api_key = get_config("api_key")
    if not api_key:
        raise fail_response(status_code=502, message="未注册 CMS 用户，无法调用大模型")

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
            raise fail_response(status_code=402, message="CMS 额度不足，请充值")
        if resp.status_code >= 400:
            logger.error("CMS LLM 代理错误 (HTTP %s): %s", resp.status_code, resp.text[:200])
            raise fail_response(status_code=502, message=f"大模型调用失败: {resp.text[:200]}")

        data = resp.json()
        llm_response = data.get("data", {})
        text = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        remaining = llm_response.get("x_quota_remaining")
        if remaining is not None:
            update_local_quota(remaining)
        return text or ""
    except requests.RequestException as e:
        logger.error("LLM 调用失败: %s", e)
        raise fail_response(status_code=502, message=f"大模型调用失败: {e}")


def list_agents(db: Session) -> list[Agent]:
    return db.query(Agent).order_by(Agent.id).all()


def create_agent(db: Session, data) -> Agent:
    agent = Agent(**data.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent(db: Session, agent_id: int, data) -> Agent:
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise fail_response(status_code=404, message="智能体不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(agent, k, v)
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent_id: int) -> dict:
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise fail_response(status_code=404, message="智能体不存在")
    db.delete(agent)
    db.commit()
    return {"ok": True}


def chat_with_agent(db: Session, agent_id: int, req: AgentChatRequest) -> AgentChatResponse:
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise fail_response(status_code=404, message="智能体不存在")
    return AgentChatResponse(content=_call_llm(agent, req))


def chat_with_agent_by_key(db: Session, key: str, req: AgentChatRequest) -> AgentChatResponse:
    agent = db.query(Agent).filter(Agent.key == key).first()
    if not agent:
        raise fail_response(status_code=404, message=f"智能体 '{key}' 不存在")
    return AgentChatResponse(content=_call_llm(agent, req))


def chat_with_agent_by_name(db: Session, name: str, req: AgentChatRequest) -> AgentChatResponse:
    agent = db.query(Agent).filter(Agent.name == name).first()
    if not agent:
        raise fail_response(status_code=404, message=f"智能体 '{name}' 不存在")
    return AgentChatResponse(content=_call_llm(agent, req))
