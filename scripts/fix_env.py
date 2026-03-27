
import os
env_content = """AI_PROVIDER=GEMINI
GOOGLE_API_KEY=AIzaSyCScgsuV_xwNUMCZ1NeKTKpSzVyAW3uoKw
# AI_PROVIDER=GPT4
# OPENAI_API_KEY=
# AI_PROVIDER=DEEPSEEK
# DEEPSEEK_API_KEY=
# AI_PROVIDER=OLLAMA
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/amoeba
"""

path = "backend/.env"
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(env_content)

print(f"✅ Cleaned {path} with UTF-8 and LF line endings.")
