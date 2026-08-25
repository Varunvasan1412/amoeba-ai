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
        self.schema_cache = {} # Dict[int, List[Dict]]
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
        
        # 2. Ingest Global Data (Rules, Reports)
        try:
            # We skip global schema ingestion here. It happens per-client in retrieve_context.
            
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
        # Note: Schema docs are embedded on-the-fly when first ingested per-client
        docs = self.rules_docs + self.report_docs + self.template_docs
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

    async def _ingest_schema(self, client_id: int):
        """Ingests Database Schema for a specific client, splitting by table."""
        try:
            schema_raw = await get_database_schema()
            if isinstance(schema_raw, str) and "Error" in schema_raw:
                print(f"❌ RAG: Schema discovery returned error for Client {client_id}: {schema_raw}")
                return

            client_docs = []
            
            # 1. Handle Dictionary (Best practice)
            if isinstance(schema_raw, dict):
                print(f"📦 RAG: Processing {len(schema_raw)} tables from dict for Client {client_id}...")
                for table_name, columns in schema_raw.items():
                    content = f"Table: {table_name} | Columns: {', '.join(columns)}"
                    client_docs.append({"content": content, "type": "schema", "embedding": None})
            
            # 2. Handle String Output (For backward compatibility)
            elif isinstance(schema_raw, str):
                print(f"📦 RAG: Processing string schema for Client {client_id} (Length: {len(schema_raw)})...")
                if schema_raw.strip().startswith("{"):
                    try:
                        import ast
                        schema_dict = ast.literal_eval(schema_raw)
                        for table_name, columns in schema_dict.items():
                            content = f"Table: {table_name} | Columns: {', '.join(columns)}"
                            client_docs.append({"content": content, "type": "schema", "embedding": None})
                    except Exception as e:
                        print(f"⚠️ RAG: AST Eval failed for Client {client_id}: {e}")
                        client_docs = [{"content": line.strip(), "type": "schema", "embedding": None} for line in schema_raw.split("\n\n") if line.strip()]
                else:
                    client_docs = [{"content": line.strip(), "type": "schema", "embedding": None} for line in schema_raw.split("\n\n") if line.strip()]
            
            self.schema_cache[client_id] = client_docs
            print(f"✅ RAG: Successfully ingested {len(client_docs)} table documents for Client {client_id}.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ RAG: UNEXPECTED Schema ingestion crash for Client {client_id}: {e}")

    def _ingest_navigation(self):
        """Sitemap ingestion is now handled per-session/tenant during retrieval."""
        self.nav_docs = []
        print(f"📦 RAG: Navigation ingestion skipped (Global sitemap deprecated).", flush=True)

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
                print(f"❌ RAG: Template ingestion failed (Inline): {e}", flush=True)


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

        print(f"🔍 RAG Retrieval for: '{query}' [Client: {client_id}, Fast: {fast_mode}]", flush=True)
        
        # 0. Ensure Client Schema is Ingested
        if client_id and client_id not in self.schema_cache:
            print(f"🔄 RAG: Initial schema ingestion for Client {client_id}...")
            await self._ingest_schema(client_id)
            
        current_schema_docs = self.schema_cache.get(client_id, []) if client_id else []
        print(f"📊 RAG: Active Schema Docs for Client {client_id}: {len(current_schema_docs)}")

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
                print(f"📦 RAG: Loaded {len(current_nav_docs)} navigation items for Client {client_id}", flush=True)
            except Exception as e:
                await session.rollback()
                print(f"⚠️ RAG: Failed to load tenant navigation: {e}")
        
        # Combine all docs for vector search
        vector_docs = current_schema_docs + self.rules_docs + self.report_docs + self.template_docs
        
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
        
        # 3. Keyword Search
        # We always do keyword search if no vector results OR if fast_mode=True
        if not scored_docs or fast_mode:
            # Combine all searchable docs
            nav_source = current_nav_docs if current_nav_docs else self.nav_docs
            all_source_docs = nav_source + vector_docs
            
            query_parts = [p for p in query.lower().split() if len(p) > 2]
            for doc in all_source_docs:
                content = doc.get("content", "")
                if not content:
                    continue
                content_lower = content.lower()
                score = 0
                
                # Bonus for exact phrase/title match
                metadata = doc.get("metadata", {}) or {}
                label = metadata.get("label", "").lower() if isinstance(metadata, dict) else ""
                
                # For schema docs, check table_name in content
                if doc.get("type") == "schema" and "Table: " in content:
                    table_name = content.split("|")[0].replace("Table: ", "").strip().lower()
                    if query.lower() in table_name or table_name in query.lower():
                        score += 15 # High priority for direct table matches
                
                if label and (query.lower() in label or label in query.lower()):
                    score += 10
                
                if query.lower() in content_lower:
                    score += 5
                    
                for part in query_parts:
                    if part in content_lower:
                        score += 1
                    
                if score > 0:
                    norm_score = min(score * 0.1, 0.95)
                    # Deduplicate if already added via vector search
                    if not any(d[1].get("content") == content for d in scored_docs):
                        scored_docs.append((norm_score, doc))

        # Sort and Top-K
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:5] # Increased from 3 to 5 for better coverage
        
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
