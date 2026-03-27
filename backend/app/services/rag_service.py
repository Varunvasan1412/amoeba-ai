import os
import json
import asyncio
import numpy as np
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.tools.database import get_database_schema
# load_sitemap removed in favor of load_client_sitemap (DB-based)

# Import Embedding Providers
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

# Path Setup
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RULES_PATH = os.path.join(DATA_DIR, "business_rules.txt")
REPORTS_PATH = os.path.join(DATA_DIR, "report_definitions.json")
TEMPLATES_PATH = os.path.join(DATA_DIR, "report_execution_templates.json")

class RagEngine:
    _instance = None
    
    def __init__(self):
        self.schema_docs = []
        self.nav_docs = []
        self.rules_docs = []
        self.report_docs = []
        self.template_docs = []
        self.embeddings_cache = {} # Simple in-memory cache for MVP
        self.embedding_model = None
        self.initialized = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RagEngine()
        return cls._instance

    async def initialize(self):
        """Loads all data sources and initializes embedding model."""
        if self.initialized:
            return

        import time
        start_time = time.time()
        print(f"🧠 [RAG DEBUG] Initializing... (T=0s)")
        
        # 1. Setup Embedding Model
        self._setup_embeddings()
        print(f"🧠 [RAG DEBUG] Embeddings Setup (T={time.time() - start_time:.2f}s)")
        
        # 2. Ingest Data
        try:
            await self._ingest_schema()
            print(f"🧠 [RAG DEBUG] Schema Ingested (T={time.time() - start_time:.2f}s)")
            
            self._ingest_navigation()
            print(f"🧠 [RAG DEBUG] Navigation Ingested (T={time.time() - start_time:.2f}s)")
            
            self._ingest_business_rules()
            print(f"🧠 [RAG DEBUG] Rules Ingested (T={time.time() - start_time:.2f}s)")
            
            self._ingest_reports()
            
            # 3. Generate Embeddings for all static knowledge in parallel
            await self._generate_embeddings()
            
            self.initialized = True
            print(f"🧠 [RAG DEBUG] READY! Total Init Time: {time.time() - start_time:.2f}s")
            
        except Exception as e:
            print(f"❌ [RAG CRASH] Initialization Failed at {time.time() - start_time:.2f}s: {e}")

    async def _generate_embeddings(self):
        """Generates embeddings for all ingested documents in parallel."""
        docs = self.schema_docs + self.rules_docs + self.report_docs + self.template_docs
        to_embed = [d for d in docs if d.get("embedding") is None]
        
        if not to_embed or not self.embedding_model:
            return

        print(f"📦 RAG: Generating embeddings for {len(to_embed)} items...")
        
        # Process in batches of 10 to avoid rate limits/overload
        batch_size = 10
        for i in range(0, len(to_embed), batch_size):
            batch = to_embed[i:i + batch_size]
            tasks = [self._get_embedding(d["content"]) for d in batch]
            results = await asyncio.gather(*tasks)
            for j, emb in enumerate(results):
                batch[j]["embedding"] = emb
        
        print(f"✅ RAG: Pre-computed all embeddings.")

    def _setup_embeddings(self):
        """Selects the embedding provider based on config."""
        try:
            if settings.AI_PROVIDER == "GEMINI" and settings.GOOGLE_API_KEY:
                self.embedding_model = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-001",
                    google_api_key=settings.GOOGLE_API_KEY
                )
            elif (settings.AI_PROVIDER == "GPT4" or settings.OPENAI_API_KEY):
                self.embedding_model = OpenAIEmbeddings(
                    model="text-embedding-3-small", 
                    api_key=settings.OPENAI_API_KEY
                )
            else:
                print("⚠️ RAG Engine: No valid embedding credentials. Using KEYWORD fallback.")
                self.embedding_model = None
        except Exception as e:
            print(f"❌ RAG Engine Embedding Setup Failed: {e}")
            self.embedding_model = None

    async def _get_embedding(self, text: str) -> List[float]:
        """Wrapper to get embedding from the configured provider with retry logic."""
        if not self.embedding_model:
            return None
            
        # Check for cache
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Call API
                emb = await self.embedding_model.aembed_query(text)
                
                # Cache (Limit size for MVP)
                if len(self.embeddings_cache) < 1000:
                    self.embeddings_cache[text] = emb
                    
                return emb
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"⚠️ [RAG] Rate limit hit. Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                
                print(f"⚠️ Embedding Error: {e}")
                return None
        return None

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Computes cosine similarity between two vectors."""
        if not v1 or not v2: return 0.0
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    async def _ingest_schema(self):
        """Ingests Database Schema."""
        try:
            schema = await get_database_schema()
            # Schema is usually a list of "Table: X, Columns: ..." strings or similar.
            # If it's a list:
            if isinstance(schema, list):
                self.schema_docs = [{"content": s, "type": "schema", "embedding": None} for s in schema]
            else:
                # If it's a big string, split by table headers or newlines
                 self.schema_docs = [{"content": line, "type": "schema", "embedding": None} for line in schema.split("\n\n") if line.strip()]
            print(f"📦 RAG: Ingested {len(self.schema_docs)} schema items.")
        except Exception as e:
            print(f"❌ RAG: Schema ingestion failed: {e}")

    def _ingest_navigation(self):
        """Sitemap ingestion is now handled per-session/tenant during retrieval."""
        self.nav_docs = []
        print("📦 RAG: Navigation ingestion skipped (Global sitemap deprecated).")

    def _ingest_business_rules(self):
        """Ingests Business Rules."""
        try:
            if os.path.exists(RULES_PATH):
                with open(RULES_PATH, "r") as f:
                    content = f.read()
                # Split by rules
                rules = [r.strip() for r in content.split("\n") if r.strip() and not r.startswith("#") and not r.startswith("[")]
                self.rules_docs = [{"content": r, "type": "rule", "embedding": None} for r in rules]
                print(f"📦 RAG: Ingested {len(self.rules_docs)} business rules.")
            else:
                print("⚠️ RAG: No business_rules.txt found.")
        except Exception as e:
             print(f"❌ RAG: Rules ingestion failed: {e}")

    def _ingest_reports(self):
        """Ingests Report Definitions."""
        try:
            if os.path.exists(REPORTS_PATH):
                with open(REPORTS_PATH, "r") as f:
                    reports = json.load(f)
                self.report_docs = []
                for r in reports:
                    content = f"Report: {r.get('name')} | Desc: {r.get('description')} | Tables: {r.get('supported_tables')}"
                    self.report_docs.append({"content": content, "type": "report", "metadata": r, "embedding": None})
                print(f"📦 RAG: Ingested {len(self.report_docs)} report definitions.")
            else:
                 print("⚠️ RAG: No report_definitions.json found.")
        except Exception as e:
             print(f"❌ RAG: Report ingestion failed: {e}")

        if os.path.exists(TEMPLATES_PATH):
            try:
                with open(TEMPLATES_PATH, "r") as f:
                    templates = json.load(f)
                self.template_docs = []
                # templates is a dict: "Report Name": { ... }
                for name, details in templates.items():
                    content = f"Template: {name} | Base Table: {details.get('base_table')} | Where: {details.get('base_where')} | Aggregations: {details.get('allowed_aggregations')}"
                    self.template_docs.append({"content": content, "type": "template", "metadata": details, "embedding": None})
                print(f"📦 RAG: Ingested {len(self.template_docs)} report templates.")
            except Exception as e:
                print(f"❌ RAG: Template ingestion failed (Inline): {e}")


    def _get_config_hash(self, path: str) -> str:
        """Returns a short hash of the file content for versioning."""
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return hashlib.md5(f.read()).hexdigest()[:6]
        except:
            pass
        return "unknown"

    async def retrieve_context(self, query: str, client_id: Optional[int] = None, session: Optional[AsyncSession] = None, fast_mode: bool = False) -> str:
        """
        Master retrieval function.
        Returns a formatted string of ALL relevant context.
        """
        if not self.initialized:
            await self.initialize()

        print(f"🔍 RAG Retrieval for: '{query}' [Client: {client_id}, Fast: {fast_mode}]")
        
        query_embedding = None
        if not fast_mode:
            query_embedding = await self._get_embedding(query)
        
        # 1. Fetch Tenant-Specific Navigation from DB
        current_nav_docs = []
        # ... (rest of the navigation fetching logic remains same)
        if client_id and session:
            try:
                from app.models.navigation import NavigationItem
                from app.tools.navigation import _infer_parents_from_path
                from sqlmodel import select
                
                stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)
                res = await session.execute(stmt)
                items = res.scalars().all()
                
                for item in items:
                    parents = _infer_parents_from_path(item.path)
                    parents_str = " -> ".join(parents)
                    content = f"Page: {item.label} | Path: {item.path} | Module: {item.module} | Navigation: {parents_str} -> {item.label}"
                    current_nav_docs.append({
                        "content": content, 
                        "type": "navigation", 
                        "metadata": {"label": item.label, "path": item.path}
                    })
                print(f"📦 RAG: Loaded {len(current_nav_docs)} navigation items for Client {client_id}")
            except Exception as e:
                await session.rollback()
                print(f"⚠️ RAG: Failed to load tenant navigation: {e}")
        
        # Combine all docs for vector search (Small < 100 items usually)
        vector_docs = self.schema_docs + self.rules_docs + self.report_docs + self.template_docs
        
        scored_docs = []
        
        # 2. Vector Search
        if query_embedding:
            for doc in vector_docs:
                doc_embedding = doc.get("embedding")
                if not doc_embedding:
                    doc_embedding = await self._get_embedding(doc["content"])
                
                score = self._cosine_similarity(query_embedding, doc_embedding)
                if score > 0.35:
                    scored_docs.append((score, doc))
        
        # 3. Keyword Search for Navigation (Large)
        # Use current_nav_docs (tenant-specific) or fallback to self.nav_docs (global)
        nav_source = current_nav_docs if current_nav_docs else self.nav_docs
        
        query_parts = [p for p in query.lower().split() if len(p) > 2]
        for doc in nav_source:
            content_lower = doc["content"].lower()
            score = 0
            
            label = doc.get("metadata", {}).get("label", "").lower()
            if query.lower() in label or label in query.lower():
                score += 10
            
            if query.lower() in content_lower:
                score += 5
                
            for part in query_parts:
                if part in content_lower:
                    score += 1
                
            if score > 0:
                norm_score = min(score * 0.1, 0.95)
                scored_docs.append((norm_score, doc))

        # Sort and Top-K
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:3] # REDUCED from 8 to 3 for speed
        
        if not top_docs:
            if fast_mode:
                # Fallback to general rules if no keyword match in fast mode
                top_docs = [(0.5, doc) for doc in self.rules_docs[:2]]
            else:
                return "No relevant context found."

        # Format Output
        v_rules = self._get_config_hash(RULES_PATH)
        v_reports = self._get_config_hash(REPORTS_PATH)
        v_templates = self._get_config_hash(TEMPLATES_PATH)
        
        context_str = f"### RETRIEVED CONTEXT [Config Versions: Rules={v_rules}, Reports={v_reports}, Templates={v_templates}] ###\n"
        
        # Group by type for readability
        groups = {"schema": [], "navigation": [], "rule": [], "report": [], "template": []}
        for score, doc in top_docs:
            groups[doc["type"]].append(doc["content"])
            
        if groups["rule"]:
            context_str += "\n[BUSINESS RULES]\n" + "\n".join(f"- {r}" for r in groups["rule"])
        if groups["schema"]:
            context_str += "\n\n[DATABASE SCHEMA]\n" + "\n".join(f"- {s}" for s in groups["schema"])
        if groups["template"]:
            context_str += "\n\n[REPORT TEMPLATES (STRICT)]\n" + "\n".join(f"- {t}" for t in groups["template"])
        if groups["report"]:
            context_str += "\n\n[REPORTS]\n" + "\n".join(f"- {r}" for r in groups["report"])
        if groups["navigation"]:
            context_str += "\n\n[NAVIGATION]\n" + "\n".join(f"- {n}" for n in groups["navigation"])
            
        return context_str

rag_engine = RagEngine.get_instance()
