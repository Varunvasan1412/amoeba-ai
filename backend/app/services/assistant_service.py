from sqlalchemy.ext.asyncio import AsyncSession
from app.services.rag_service import rag_engine
from app.services.greeting_service import detect_greeting
from app.services.audit_service import log_audit
from app.models.semantic_metadata import SemanticMetadata
from sqlmodel import select
from typing import Tuple, List, Dict, Any
from app.services.llm_service import get_brain
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import re
import asyncio
import traceback

async def get_assistant_response(user_input: str, client_id: int, session: AsyncSession, history: list = [], memory_summary: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    """
    ULTRA-FAST Assistant Mode: Bypasses embeddings and uses minimal context.
    """
    # 1. Greeting Check
    greeting_reply = detect_greeting(user_input)
    if greeting_reply:
        return greeting_reply, []

    # 2. Fast RAG (Keyword only, top 3)
    print(f"🔍 [Assistant DEBUG] Starting RAG Retrieval...", flush=True)
    rag_start = asyncio.get_event_loop().time()
    context = await rag_engine.retrieve_context(user_input, client_id=client_id, session=session, fast_mode=True)
    print(f"✅ [Assistant DEBUG] RAG Finished in {asyncio.get_event_loop().time() - rag_start:.2f}s", flush=True)
    
    # 3. Minimal Semantic Context (Skipped for Assistant Mode to maximize speed)
    semantic_context = ""

    # 4. Prompt
    system_prompt = f"ERP Assistant. Brief answer based on context:\n{context[:1000]}\nNav: [NAVIGATE: /path]"

    messages = [SystemMessage(content=system_prompt)]
    # Keep last 4 messages (e.g., 2 exchanges) for context
    for msg in history[-4:]:
        msg_role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "user")
        msg_content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
        if msg_role == "user":
            messages.append(HumanMessage(content=msg_content))
        else:
            messages.append(AIMessage(content=msg_content))
    messages.append(HumanMessage(content=user_input))

    # 5. Get Brain
    print(f"🔍 [Assistant DEBUG] Getting AI Brain...", flush=True)
    brain_start = asyncio.get_event_loop().time()
    res_brain = await get_brain(client_id, session)
    print(f"✅ [Assistant DEBUG] Brain Found in {asyncio.get_event_loop().time() - brain_start:.2f}s", flush=True)
    
    provider = res_brain[1] if res_brain else "UNKNOWN"
    llm = res_brain[2] if res_brain else None  # Use RAW LLM for Assistant mode (no tools needed)
    
    if not llm:
        return "System Error: AI Brain failed to initialize.", []

    try:
        start_time = asyncio.get_event_loop().time()
        print(f"🚀 [Assistant] Fast-Invoke ({provider}) with {len(messages)} messages...", flush=True)
        pending_actions = []
        
        # Increased timeout to 120s for slow local models
        ai_msg = await asyncio.wait_for(llm.ainvoke(messages), timeout=120.0)
        
        duration = asyncio.get_event_loop().time() - start_time
        print(f"✅ [Assistant] Response received in {duration:.2f}s", flush=True)
        content = ai_msg.content
        
        if not content or content.strip() == "":
            print("⚠️ [Assistant] Received EMPTY content from LLM.")
            return "The AI model returned an empty response. This can happen if the model is still loading or under heavy load. Please try again.", []

        if "[NAVIGATE:" in content:
            nav_match = re.search(r"\[NAVIGATE:\s*(.*?)\]", content)
            if nav_match:
                path = nav_match.group(1).strip()
                pending_actions.append({"type": "NAVIGATE", "payload": path})
                content = content.replace(nav_match.group(0), "").strip()

        return content, pending_actions

    except asyncio.TimeoutError:
        print("💥 Assistant Timeout: The model took too long to respond (>120s).")
        return "I encountered a timeout error. The local AI model (Ollama) is taking too long to respond. This usually happens when the model is still loading or your system is busy. Please try again in 30 seconds.", []
    except Exception as e:
        err_type = e.__class__.__name__
        err_msg = str(e)
        print(f"💥 Assistant Error [{err_type}]: {err_msg}")
        traceback.print_exc()
        
        final_error = f"{err_type}: {err_msg}" if err_msg else err_type
        return f"I encountered an error while processing your request: {final_error}. Please try again.", []
