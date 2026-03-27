"""
Multi-Source Retrieval Router for Amoeba AI.
Routes queries to selected knowledge sources and merges results.
Used by Assistant mode only.
"""
import os
import asyncio
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.audit_service import log_audit


async def search_erp(query: str, client_id: int, session: AsyncSession) -> List[str]:
    """Search ERP data via existing RAG engine (schema, navigation, rules, reports)."""
    try:
        from app.services.rag_service import rag_engine
        context = await rag_engine.retrieve_context(query, client_id=client_id, session=session, fast_mode=True)
        if context and context != "No relevant context found.":
            return [context]
        return []
    except Exception as e:
        await session.rollback()
        print(f"⚠️ [RETRIEVAL] ERP search error: {e}")
        return []


async def search_documents(query: str, client_id: int, session: AsyncSession, file_hint: Optional[str] = None) -> List[dict]:
    """
    Search uploaded documents using vector similarity. 
    Returns a list of dicts: {'text': str, 'filename': str, 'page': int, 'score': float}
    """
    import time
    from sqlmodel import select
    from app.services.rag_service import rag_engine
    from app.models.document import DocumentChunk, Document
    
    start_time = time.time()
    try:
        # 1. Get query embedding
        await rag_engine.initialize()
        query_embedding = await rag_engine._get_embedding(query)
        if not query_embedding:
            return []
            
        # 2. Vector search (top 5 chunks for the current client)
        # Join with Document table to get the filename for better RAG context
        statement = (
            select(DocumentChunk, Document.filename, DocumentChunk.embedding_vector.l2_distance(query_embedding).label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.client_id == client_id,
                DocumentChunk.embedding_vector.isnot(None)
            )
        )

        if file_hint:
            statement = statement.where(Document.filename == file_hint)
            print(f"🎯 [RETRIEVAL] Targeted search to file: {file_hint}")

        statement = statement.order_by("distance").limit(5)
        
        results = await session.execute(statement)
        rows = results.all() 
        
        time_ms = int((time.time() - start_time) * 1000)
        docs_used = len(set(r[0].document_id for r in rows))
        
        print(f"\nDOCUMENT SEARCH:\nquery: {query[:50]}\ndocuments_used: {docs_used}\nchunks_returned: {len(rows)}\nlatency_ms: {time_ms}\n")
        
        output = []
        for chunk, filename, distance in rows:
            # Convert l2_distance to a 0-100 score for UI
            # distance of 0.0 is perfect (100%), 1.0+ is poor.
            score = max(0, min(100, int((1.0 - (distance or 0.5)) * 100)))
            output.append({
                "text": chunk.chunk_text,
                "filename": filename,
                "page": chunk.page_number,
                "score": score
            })

        return output
        
    except Exception as e:
        await session.rollback()
        print(f"⚠️ [RETRIEVAL] Document search error: {e}")
        return []


async def search_web(query: str) -> List[str]:
    """Web search stub — ready for DuckDuckGo/SerpAPI integration."""
    # TODO: Integrate with a web search API (DuckDuckGo, SerpAPI, Tavily, etc.)
    return ["Web search is not configured yet. Please contact your administrator to enable this feature."]


async def route_sources(
    query: str,
    sources: Dict[str, bool],
    client_id: int,
    session: AsyncSession,
    file_hint: Optional[str] = None
) -> Dict[str, List[Any]]:
    """
    Routes a query to the selected knowledge sources and returns merged results.
    
    Args:
        query: The user's search query
        sources: Dict of source toggles, e.g. {"erp": True, "documents": True, "web": False}
        client_id: The client ID for tenant isolation
        session: Database session
    
    Returns:
        Dict with source names as keys and lists of context strings as values
    """
    results: Dict[str, List[str]] = {"erp": [], "documents": [], "web": []}
    tasks = []

    if sources.get("erp", True):
        tasks.append(("erp", search_erp(query, client_id, session)))
    
    if sources.get("documents", True):
        tasks.append(("documents", search_documents(query, client_id, session, file_hint=file_hint)))
    
    if sources.get("web"):
        print("\nWEB SEARCH DISABLED — skipping\n")
        # results["web"] = await search_web(query)))

    # Run all source searches concurrently
    if tasks:
        import time
        start_time_all = time.perf_counter()
        
        gathered = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        
        total_latency_ms = int((time.perf_counter() - start_time_all) * 1000)
        
        for i, (source_name, _) in enumerate(tasks):
            result = gathered[i]
            if isinstance(result, Exception):
                print(f"⚠️ [RETRIEVAL] {source_name} failed: {result}")
                results[source_name] = []
            else:
                results[source_name] = result

        # 🚀 Step 5 & 6: Latency Monitoring & Slow Query Detection
        total_results = sum(len(v) for v in results.values())
        print(f"\nDOCUMENT RETRIEVAL LATENCY:\nquery: {query[:50]}\nlatency_ms: {total_latency_ms}\nchunks_returned: {total_results}\n")
        
        if total_latency_ms > 2000:
            print(f"⚠️ SLOW DOCUMENT QUERY:\nquery: {query[:50]}\nlatency_ms: {total_latency_ms}\nclient_id: {client_id}\n")

    # Audit log
    log_audit(client_id, "RETRIEVAL_SOURCES", {
        "query": query[:100],
        "sources": sources,
        "results_count": {k: len(v) for k, v in results.items()}
    })

    total = sum(len(v) for v in results.values())
    print(f"🔍 [RETRIEVAL] Query: '{query[:50]}' | Sources: {sources} | Results: {total}")

    return results


def format_retrieval_context(results: Dict[str, List[Any]]) -> str:
    """Formats the multi-source results into a structured context string for the LLM."""
    sections = []

    if results.get("erp"):
        erp_texts = [r if isinstance(r, str) else str(r) for r in results["erp"]]
        sections.append("[ERP DATA]\n" + "\n".join(erp_texts))
    
    if results.get("documents"):
        doc_texts = []
        for res in results["documents"]:
            if isinstance(res, dict):
                src_label = f"Source: {res['filename']}"
                if res.get('page'):
                    src_label += f" | Page {res['page']}"
                doc_texts.append(f"[{src_label}]\n{res['text']}")
            else:
                doc_texts.append(str(res))
        sections.append("[DOCUMENTS]\n" + "\n\n".join(doc_texts))
    
    if results.get("web"):
        sections.append("[WEB]\n" + "\n".join(results["web"]))

    if not sections:
        return "No relevant context found from selected sources."

    return "\n\n".join(sections)
