from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from datetime import datetime
import json
from app.models.chat import ChatMessage
from app.models.chat_memory import ChatMemory
from app.services.llm_provider_factory import get_llm_provider
from app.services.audit_service import log_audit

from app.core.database import async_session

async def trigger_compression_task(session_id: str, client_id: int):
    async with async_session() as db_session:
        # 1. Fetch messages
        result = await db_session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.client_id == client_id)
        .order_by(ChatMessage.timestamp)
    )
    messages = result.scalars().all()
    
    if len(messages) <= 20:
        return # No compression needed yet
        
    print(f"🗜️ Compressing memory for session {session_id} ({len(messages)} messages)")
    
    # 2. Get existing memory
    mem_result = await db_session.execute(
        select(ChatMemory)
        .where(ChatMemory.session_id == session_id)
        .where(ChatMemory.client_id == client_id)
    )
    memory = mem_result.scalars().first()
    
    is_new = False
    if not memory:
        memory = ChatMemory(session_id=session_id, client_id=client_id, summary="")
        is_new = True
        
    # We will summarize all but the last 8 messages
    messages_to_compress = messages[:-8]
    
    conversation_text = ""
    for msg in messages_to_compress:
        conversation_text += f"{msg.role}: {msg.content}\n"
        
    # 3. Use LLM to summarize
    try:
        provider = await get_llm_provider(client_id, db_session)
        system_prompt = "You are a memory compressor. Summarize the following conversation concisely, focusing on key facts, user preferences, and important entities discussed. Integrate it with the EXISTING SUMMARY if provided."
        
        prompt = f"EXISTING SUMMARY:\n{memory.summary}\n\nCONVERSATION TO COMPRESS:\n{conversation_text}"
        
        new_summary = await provider.generate_response(prompt, system_prompt)
        memory.summary = new_summary
        memory.updated_at = datetime.utcnow()
        
        if is_new:
            db_session.add(memory)
            
        await db_session.commit()
        
        log_audit(client_id, "CHAT_MESSAGE_COMPRESSED", {"session_id": session_id, "compressed_count": len(messages_to_compress)})
        print("✅ Memory compression successful.")
    except Exception as e:
        print(f"❌ Error compressing memory: {e}")
        # Important: If it was new and failed, it wasn't added yet, so session is clean.
        # If it was existing, we didn't change it or commit, so it's also clean.

