from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import AgentChatRequest, AgentChatResponse, AgentCreate, AgentOut, AgentUpdate
from src.api.services.agent_service import (
    chat_with_agent,
    chat_with_agent_by_key,
    chat_with_agent_by_name,
    create_agent,
    delete_agent,
    list_agents,
    update_agent,
)

router = APIRouter(prefix="/agents", tags=["智能体管理"])


@router.get("", response_model=list[AgentOut])
def _list_agents(db: Session = Depends(get_db)):
    return list_agents(db)


@router.post("", response_model=AgentOut)
def _create_agent(data: AgentCreate, db: Session = Depends(get_db)):
    return create_agent(db, data)


@router.put("/{agent_id}", response_model=AgentOut)
def _update_agent(agent_id: int, data: AgentUpdate, db: Session = Depends(get_db)):
    return update_agent(db, agent_id, data)


@router.delete("/{agent_id}")
def _delete_agent(agent_id: int, db: Session = Depends(get_db)):
    return delete_agent(db, agent_id)


@router.post("/by-key/{key}/chat", response_model=AgentChatResponse)
def _chat_with_agent_by_key(key: str, req: AgentChatRequest, db: Session = Depends(get_db)):
    return chat_with_agent_by_key(db, key, req)


@router.post("/by-name/{name}/chat", response_model=AgentChatResponse)
def _chat_with_agent_by_name(name: str, req: AgentChatRequest, db: Session = Depends(get_db)):
    return chat_with_agent_by_name(db, name, req)


@router.post("/{agent_id}/chat", response_model=AgentChatResponse)
def _chat_with_agent(agent_id: int, req: AgentChatRequest, db: Session = Depends(get_db)):
    return chat_with_agent(db, agent_id, req)
