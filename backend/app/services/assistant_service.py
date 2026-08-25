from sqlalchemy.ext.asyncio import AsyncSession
from app.services.retrieval_router import route_sources, format_retrieval_context
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

async def get_assistant_response(user_input: str, client_id: int, session: AsyncSession, history: list = [], memory_summary: str = "", sources: dict = None, model: str = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Assistant Mode with Multi-Source Retrieval.
    Routes queries to selected sources (ERP, Documents, Web) before calling the LLM.
    """
    if sources is None:
        sources = {"erp": True, "documents": True, "web": False}
    
    print(f"\nACTIVE SOURCES:\nerp={sources.get('erp')}\ndocuments={sources.get('documents')}\nweb={sources.get('web')}\n")

    # 1. Greeting Check
    greeting_reply = detect_greeting(user_input)
    if greeting_reply:
        return greeting_reply, []

    # 2. Multi-Source Retrieval
    # Strip [SYSTEM:] context for RAG query to avoid noise, but extract filename hint
    rag_query = user_input
    file_hint = None
    if "[SYSTEM: User uploaded file '" in user_input:
        match = re.search(r"\[SYSTEM: User uploaded file '(.*?)'", user_input)
        if match:
            file_hint = match.group(1)
            print(f"📎 Found attachment hint: {file_hint}")

    if "[SYSTEM:" in user_input and "]" in user_input:
        # Extract everything after the last ]
        parts = user_input.split("]", 1)
        if len(parts) > 1:
            rag_query = parts[1].strip()
    
    if not rag_query:
        rag_query = user_input

    print(f"🔍 [Assistant] Starting Multi-Source Retrieval (query='{rag_query}', sources={sources}, hint={file_hint})...", flush=True)
    rag_start = asyncio.get_event_loop().time()
    retrieval_results = await route_sources(rag_query, sources, client_id, session, file_hint=file_hint)
    context = format_retrieval_context(retrieval_results)
    print(f"✅ [Assistant] Retrieval finished in {asyncio.get_event_loop().time() - rag_start:.2f}s", flush=True)
    
    # 3. Minimal Semantic Context (Skipped for Assistant Mode to maximize speed)
    semantic_context = ""

    # 4. Prompt
    system_prompt = f"ERP Assistant. Brief answer based on context:\n{context[:1500]}\nNav: [NAVIGATE: /path]"

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
    print(f"🔍 [Assistant DEBUG] Getting AI Brain (Override: {model})...", flush=True)
    brain_start = asyncio.get_event_loop().time()
    res_brain = await get_brain(client_id, session, model_override=model)
    print(f"✅ [Assistant DEBUG] Brain Found in {asyncio.get_event_loop().time() - brain_start:.2f}s", flush=True)
    
    provider = res_brain[1] if res_brain else "UNKNOWN"
    llm = res_brain[2] if res_brain else None  # Use RAW LLM for Assistant mode (no tools needed)
    
    if not llm:
        return "System Error: AI Brain failed to initialize.", []

    try:
        start_time = asyncio.get_event_loop().time()
        print(f"🚀 [Assistant] Fast-Invoke ({provider}) with {len(messages)} messages...", flush=True)
        pending_actions = []
        
        # Increased timeout to 300s for slow local models during background builds
        ai_msg = await asyncio.wait_for(llm.ainvoke(messages), timeout=300.0)
        
        duration = asyncio.get_event_loop().time() - start_time
        print(f"✅ [Assistant] Response received in {duration:.2f}s", flush=True)
        content = ai_msg.content
        
        # --- NEW: TOKEN USAGE LOGGING ---
        if hasattr(ai_msg, "response_metadata") and "token_usage" in ai_msg.response_metadata:
            usage = ai_msg.response_metadata["token_usage"]
            total_tokens = usage.get("total_tokens", 0)
            if total_tokens > 0:
                print(f"💰 [ASSISTANT TOKEN USAGE] Total: {total_tokens}")
                content += f"\n\n*(💰 {total_tokens} tokens)*"
                try:
                    await session.execute(
                        __import__('sqlalchemy').text("UPDATE clientconfig SET total_tokens_used = COALESCE(total_tokens_used, 0) + :t WHERE id = :cid"),
                        {"t": total_tokens, "cid": client_id}
                    )
                    await session.commit()
                except Exception:
                    pass
        # --------------------------------
        
        if not content or content.strip() == "":
            print("⚠️ [Assistant] Received EMPTY content from LLM.")
            return "The AI model returned an empty response. This can happen if the model is still loading or under heavy load. Please try again.", []

        if "[NAVIGATE:" in content:
            nav_match = re.search(r"\[NAVIGATE:\s*(.*?)\]", content)
            if nav_match:
                path = nav_match.group(1).strip()
                pending_actions.append({"type": "NAVIGATE", "payload": path})
                content = content.replace(nav_match.group(0), "").strip()

        # 6. Structured Sources & Confidence
        doc_results = retrieval_results.get("documents", [])
        deduped_sources = {}
        total_score = 0
        
        for res in doc_results:
            fname = res["filename"]
            doc_id = res.get("document_id")
            total_score += res["score"]
            if fname not in deduped_sources:
                deduped_sources[fname] = {"filename": fname, "document_id": doc_id, "pages": []}
            if res.get("page") and res["page"] not in deduped_sources[fname]["pages"]:
                deduped_sources[fname]["pages"].append(res["page"])
        
        avg_confidence = int(total_score / len(doc_results)) if doc_results else 0
        
        # Sort pages for each source
        sources_payload = []
        for s in deduped_sources.values():
            s["pages"].sort()
            sources_payload.append(s)

        if sources_payload:
            pending_actions.append({
                "type": "SOURCES",
                "payload": {
                    "sources": sources_payload,
                    "confidence": avg_confidence
                }
            })

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
