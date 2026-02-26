# 🎓 The "Fresher's Guide" to Amoeba AI
*Welcome to the team! This document is your map to the Amoeba AI project. Read this before touching any code.*

---

## 1. 🌍 What IS this project?
**Amoeba AI** is not just a chatbot. It is an **Autonomous Agent Widget**.

Normally, businesses have to build complex "Admin Panels" or "Dashboards" for their software. Amoeba replaces those dashboards with a **Smart Chat Window** that floats on their website.

### The "Magic" Trick:
1.  **The Widget**: A small chat bubble sits on the client's website (ERP, CRM, etc.).
2.  **The Brain**: The user types "Show me sales for yesterday".
3.  **The Action**: Our AI **connects directly to the client's database**, runs the SQL, generates an Excel file, and gives it to the user.

**It doesn't just talk. It DOES things.** (Database writes, navigating the UI, generating reports).

---

## 2. 🏗️ The Architecture (How it works)

Imagine three islands connected by bridges:

1.  **🏝️ Island A: The Client Website**
    *   This is the user's existing app (Vue, React, PHP, whatever).
    *   They add **1 line of code** (`<script src="widget-loader.js">`).
    *   This script creates an `<iframe>` that loads our Frontend.

2.  **🏝️ Island B: Our Frontend (The Widget)**
    *   **Tech**: React 19, Vite, TailwindCSS.
    *   **Role**: Handles the chat UI, WebSockets, and displaying messages.
    *   **Location**: `frontend/`

3.  **🏝️ Island C: Our Backend (The Brain)**
    *   **Tech**: Python (FastAPI), LangChain, SQLModel, Postgres.
    *   **Role**: Logic, AI reasoning, File Generation.
    *   **Location**: `backend/`

4.  **🏝️ Island D: The Client's Database**
    *   **Crucial**: We do NOT store their business data. We connect to *their* database remotely using a Connection String stored in our config.

---

## 3. 🛠️ Tech Stack Cheat Sheet

| Layer | Technology | Why we use it |
| :--- | :--- | :--- |
| **Backend** | **FastAPI** (Python) | High-performance Async API. |
| **AI Logic** | **LangChain** | Manages the "ReAct" loop (Reasoning + Acting). |
| **Database** | **Postgres + pgvector** | Stores our users, chat history, and "Memory" (RAG). |
| **Frontend** | **React 19 + Vite** | Super fast UI. |
| **Styling** | **TailwindCSS** | Utility-first CSS. |
| **Realtime** | **WebSockets** | For streaming AI tokens (talking while thinking). |

---

## 4. 📂 Project Tour (Where things live)

### 🖥️ Frontend (`/frontend`)
*   **`public/widget-loader.js`**: **Start here.** This is the script clients paste on their site. It creates the iframe.
*   **`src/App.tsx`**: The main container.
*   **`src/components/ChatWidget.tsx`**: The massive component that runs the chat UI.

### 🧠 Backend (`/backend/app`)
*   **`main.py`**: The entry point. Starts the server and defines routes.
*   **`routers/chat.py`**: **The Heart.** Handles the WebSocket connection.
    *   It decides: *"Is this a simple request (FastPath) or complex (LLM)?"*
*   **`services/llm_service.py`**: **The Brain.** Setup for GPT-4/Gemini and the "System Prompt".
*   **`services/fastpath_service.py`**: **The Reflexes.** Regex logic to handle "Navigate to X" instantly without paying for AI.
*   **`tools/`**: **The Hands.**
    *   `inspect_db.py`: Reads table schemas.
    *   `reporting.py`: Generates PDF/Excel.
    *   `navigation.py`: Smart sitemap lookup.

---

## 5. 🔑 Key Concepts You MUST Understand

### A. The "ReAct" Loop (Reason + Act)
Normal chatbots just talk. Amoeba follows a loop:
1.  **THINK**: "The user wants a sales report."
2.  **PLAN**: "I need to check the `orders` table first."
3.  **ACT**: Call `tool_inspect_database()`.
4.  **OBSERVE**: "Table `orders` has columns `id`, `amount`, `date`."
5.  **ACT**: Call `tool_generate_excel("SELECT * FROM orders...")`.
6.  **RESPOND**: "Here is your file."

See `backend/app/services/llm_service.py` -> `get_response()` function.

### B. "Context Switching" (Multi-Tenant)
How do we know WHICH database to query?
1.  Client sends `API_KEY` in the WebSocket connection.
2.  Backend looks up `ClientConfig` table.
3.  Backend sets `current_db_url` context variable.
4.  All tools (SQL, etc.) automatically use that specific client's DB.

### C. The "Safety Net" & "FastPath"
*   **FastPath**: If a user says "Navigate to Sales", we don't need GPT-4. We use Regex in `fastpath_service.py` to do it instantly (0s latency).
*   **Safety Net**: Sometimes the AI generates a link but forgets to show it. The `chat.py` router "catches" any tool outputs (like file paths) and forces them to appear in the chat.

---

## 6. 🚀 specific Guides for Freshers

### "How do I add a new Tool?" (e.g., Send Email)
1.  Create a function in `backend/app/tools/email_tool.py`.
2.  Add the `@tool` decorator wrapper in `backend/app/services/llm_service.py`.
3.  Add it to the `MY_TOOLS` list in `llm_service.py`.
4.  Update the System Prompt to tell the AI when to use it.

### "How do I fix a bug in the Chat UI?"
1.  Go to `frontend/src/components/ChatWidget.tsx`.
2.  Use `npm run dev` to see changes.

### "How do I setup the project?"
1.  Install Docker Desktop.
2.  Run `docker-compose up --build`.
3.  Access Frontend at `http://localhost:5173`.
4.  Access Backend API docs at `http://localhost:8000/docs`.

---

## 7. ⚠️ Golden Rules
1.  **Never hardcode Client DBs**: Always use the `current_db_url` context.
2.  **Don't write huge files**: Use Stream responses if possible.
3.  **Safety First**: The AI should never DELETE data without confirmation (We have a check for this in `llm_service.py`).

*Good luck! If stuck, check `debug_output.txt` in the backend folder.*
