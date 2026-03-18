from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings
from app.models.ai_settings import AISettings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str, system_prompt: str = "You are a helpful assistant.", history: List[Dict[str, str]] = []) -> str:
        pass

class GeminiProvider(BaseLLMProvider):
    def __init__(self, model: str, temperature: float):
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temperature
        )
    async def generate_response(self, prompt: str, system_prompt: str, history: List[Dict[str, str]] = []) -> str:
        messages = [SystemMessage(content=system_prompt)]
        for h in history:
            role = h.get("role")
            content = h.get("content")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=content))
        
        messages.append(HumanMessage(content=prompt))
        res = await self.llm.ainvoke(messages)
        return res.content

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model: str, temperature: float):
        self.llm = ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature
        )
    async def generate_response(self, prompt: str, system_prompt: str, history: List[Dict[str, str]] = []) -> str:
        messages = [SystemMessage(content=system_prompt)]
        for h in history:
            role = h.get("role")
            content = h.get("content")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=content))
        
        messages.append(HumanMessage(content=prompt))
        res = await self.llm.ainvoke(messages)
        return res.content

class OllamaProvider(BaseLLMProvider):
    def __init__(self, model: str, temperature: float):
        # Default Ollama URL in Docker
        self.llm = ChatOllama(
            model=model,
            base_url="http://host.docker.internal:11434",
            temperature=temperature
        )
    async def generate_response(self, prompt: str, system_prompt: str, history: List[Dict[str, str]] = []) -> str:
        messages = [SystemMessage(content=system_prompt)]
        for h in history:
            role = h.get("role")
            content = h.get("content")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=content))
        
        messages.append(HumanMessage(content=prompt))
        res = await self.llm.ainvoke(messages)
        return res.content

async def get_llm_provider(client_id: int, session: AsyncSession) -> BaseLLMProvider:
    """
    Factory function to get the configured LLM provider for a client.
    """
    stmt = select(AISettings).where(AISettings.client_id == client_id)
    res = await session.execute(stmt)
    config = res.scalars().first()
    
    if not config:
        print("🤖 [LLM Factory] No config found, using default Gemini")
        return GeminiProvider(model="gemini-2.0-flash-lite", temperature=0.7)
        
    p = config.provider.lower()
    m = config.model
    t = config.temperature
    
    print(f"🤖 [LLM Factory] Initializing Provider: {p} | Model: {m} | Temp: {t}")

    if p == "openai":
        return OpenAIProvider(m, t)
    elif p == "ollama":
        # Resilience: if user typed 'llama3' but Ollama needs 'llama3:latest'
        full_model_name = m if ":" in m else f"{m}:latest"
        return OllamaProvider(full_model_name, t)
    elif p == "gemini":
        return GeminiProvider(m, t)
    else:
        return GeminiProvider("gemini-2.0-flash-lite", 0.7)
