from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.chat_session import ChatSession
from app.models.chat import ChatMessage
from app.models.client_config import ClientConfig
from app.services.audit_service import log_audit
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat History"])

class CreateSessionRequest(BaseModel):
    title: str = "New Chat"

@router.get("/sessions")
async def get_chat_sessions(
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    sessions_res = await session.execute(
        select(ChatSession)
        .where(ChatSession.client_id == client.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return sessions_res.scalars().all()

@router.get("/messages/{session_id}", response_model=List[ChatMessage])
async def get_chat_messages(
    session_id: str,
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    messages_res = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.client_id == client.id)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp)
    )
    messages = messages_res.scalars().all()
    
    log_audit(client.id, "CHAT_HISTORY_LOADED", {"session_id": session_id, "count": len(messages)})
    return messages

@router.post("/session")
async def create_chat_session(
    request: CreateSessionRequest,
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    import uuid
    new_id = str(uuid.uuid4())
    new_sess = ChatSession(
        client_id=client.id,
        session_id=new_id,
        title=request.title
    )
    session.add(new_sess)
    await session.commit()
    
    log_audit(client.id, "CHAT_SESSION_CREATED", {"session_id": new_id})
    return {"session_id": new_id, "title": request.title}

@router.delete("/session/{session_id}")
async def delete_chat_session(
    session_id: str,
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 1. Verify session ownership
    sess_res = await session.execute(
        select(ChatSession)
        .where(ChatSession.session_id == session_id)
        .where(ChatSession.client_id == client.id)
    )
    chat_sess = sess_res.scalars().first()
    if not chat_sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Delete Messages
    from sqlalchemy import delete
    await session.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    
    # 3. Delete Memory
    from app.models.chat_memory import ChatMemory
    await session.execute(delete(ChatMemory).where(ChatMemory.session_id == session_id))
    
    # 4. Delete Session
    await session.delete(chat_sess)
    await session.commit()
    
    log_audit(client.id, "CHAT_SESSION_DELETED", {"session_id": session_id})
    return {"status": "success", "message": "Session deleted"}