import os
import json
import asyncio
import numpy as np
import hashlib
from typing import List, Dict, Any
from app.core.config import settings
from app.tools.database import get_database_schema
from app.tools.navigation import load_sitemap

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
            print(f"🧠 [RAG DEBUG] Reports Ingested (T={time.time() - start_time:.2f}s)")
            
            # self._ingest_templates() # Assuming reports covers this or redundant calls removed?
            # Wait, original code had duplicate calls. I'll clean that up.
            
            self.initialized = True
            print(f"🧠 [RAG DEBUG] READY! Total Init Time: {time.time() - start_time:.2f}s")
            
        except Exception as e:
            print(f"❌ [RAG CRASH] Initialization Failed at {time.time() - start_time:.2f}s: {e}")

    def _setup_embeddings(self):
        """Selects the embedding provider based on config."""
        try:
            if settings.AI_PROVIDER == "GEMINI" and settings.GOOGLE_API_KEY:
                self.embedding_model = GoogleGenerativeAIEmbeddings(
                    model="models/text-embedding-004",
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
        """Wrapper to get embedding from the configured provider."""
        if not self.embedding_model:
            return None # Fallback to keyword search
        try:
            # Check for cache
            if text in self.embeddings_cache:
                return self.embeddings_cache[text]
            
            # Call API
            emb = await self.embedding_model.aembed_query(text)
            
            # Cache (Limit size for MVP)
            if len(self.embeddings_cache) < 1000:
                self.embeddings_cache[text] = emb
                
            return emb
        except Exception as e:
            print(f"⚠️ Embedding Error: {e}")
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
                self.schema_docs = [{"content": s, "type": "schema"} for s in schema]
            else:
                # If it's a big string, split by table headers or newlines
                 self.schema_docs = [{"content": line, "type": "schema"} for line in schema.split("\n\n") if line.strip()]
            print(f"📦 RAG: Ingested {len(self.schema_docs)} schema items.")
        except Exception as e:
            print(f"❌ RAG: Schema ingestion failed: {e}")

    def _ingest_navigation(self):
        """Ingests Sitemap."""
        try:
            routes = load_sitemap()
            self.nav_docs = []
            for r in routes:
                content = f"Page: {r.get('label')} | Path: {r.get('path')} | Keywords: {', '.join(r.get('keywords', []))}"
                self.nav_docs.append({"content": content, "type": "navigation", "metadata": r})
            print(f"📦 RAG: Ingested {len(self.nav_docs)} navigation items.")
        except Exception as e:
            print(f"❌ RAG: Navigation ingestion failed: {e}")

    def _ingest_business_rules(self):
        """Ingests Business Rules."""
        try:
            if os.path.exists(RULES_PATH):
                with open(RULES_PATH, "r") as f:
                    content = f.read()
                # Split by rules
                rules = [r.strip() for r in content.split("\n") if r.strip() and not r.startswith("#") and not r.startswith("[")]
                self.rules_docs = [{"content": r, "type": "rule"} for r in rules]
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
                    self.report_docs.append({"content": content, "type": "report", "metadata": r})
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
                    self.template_docs.append({"content": content, "type": "template", "metadata": details})
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

    async def retrieve_context(self, query: str) -> str:
        """
        Master retrieval function.
        Returns a formatted string of ALL relevant context.
        """
        if not self.initialized:
            await self.initialize()

        print(f"🔍 RAG Retrieval for: '{query}'")
        
        query_embedding = await self._get_embedding(query)
        
        # Combine all docs
        # Partition docs: Vector Search for Schema/Reports/Rules (Small), Keyword for Nav (Large)
        vector_docs = self.schema_docs + self.rules_docs + self.report_docs + self.template_docs
        
        scored_docs = []
        
        # 1. Vector Search (Small < 50 items)
        if query_embedding:
            for doc in vector_docs:
                doc_embedding = await self._get_embedding(doc["content"])
                score = self._cosine_similarity(query_embedding, doc_embedding)
                if score > 0.4:
                    scored_docs.append((score, doc))
        
        # 2. Keyword Search for Navigation (Large ~2000 items)
        # Avoid embedding all 2000 items. Use fast string matching.
        query_parts = query.lower().split()
        for doc in self.nav_docs:
            content_lower = doc["content"].lower()
            score = 0
            for part in query_parts:
                if part in content_lower:
                    score += 1
            # Boost exact substring matches
            if query.lower() in content_lower:
                score += 2
                
            if score > 0:
                # Normalize score to be comparable to cosine (0-1 range approx)
                # Max score is likely len(query_parts) + 2. Flatten it.
                norm_score = min(score * 0.2, 0.9)
                scored_docs.append((norm_score, doc))

        # Sort and Top-K
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:8] # Take top 8 chunks
        
        if not top_docs:
            return "No relevant context found in RAG knowledge base."

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
        if groups["report"]:
            context_str += "\n\n[REPORTS]\n" + "\n".join(f"- {r}" for r in groups["report"])
            
        return context_str

rag_engine = RagEngine.get_instance()
