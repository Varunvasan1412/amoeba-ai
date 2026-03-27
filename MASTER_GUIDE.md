# The Complete Guide to Amoeba AI 🦠🤖
*For Team Members & Freshers*

## 1. What is this Project?
**Amoeba AI** is a "SaaS AI Widget".
*   **SaaS**: Software as a Service (We host it, clients rent it).
*   **Widget**: A small chat window that floats on *any* website (ERP, CRM, Blog).
*   **AI Agent**: It isn't just a chatbot; it can *do things* (Write to DB, Make Reports, Navigate).

## 2. The Architecture (How it connects)
Imagine three islands:
1.  **Island A (The Client's Website)**: Where the user lives. They have the `widget-loader.js` script.
2.  **Island B (Our SaaS Backend)**: Where the Brain (AI) lives.
3.  **Island C (The Client's Database)**: Where the Data lives.

**The Magic Trick**:
Our AI (Island B) sits in the middle. The User (Island A) talks to it, and based on the "API Key", the AI reaches out to Island C to get/save data.

## 3. Key Concepts Explained (The "Why" & "How")

### A. The "Widget Loader" (The Doorway) 🚪
*   **What**: A tiny JavaScript file (`widget-loader.js`) that creates an `<iframe>`.
*   **Why**: Clients don't want to install huge libraries. They just want one line of code.
*   **How**:
    ```html
    <script src=".../widget-loader.js" data-api-key="SECRET_KEY"></script>
    ```
    This script builds the chat window on their page.

### B. The API Key (The ID Card) 🆔
*   **What**: A secret string (e.g., `sk_12345`).
*   **Why**: We have many clients. When a message comes in, we need to know: *"Which database is this for?"*
*   **How**:
    1.  Widget sends `sk_12345`.
    2.  Our Backend checks `ClientConfig` table.
    3.  It finds: `Client A` uses `postgres://client-a-db...`.
    4.  It **switches functionality** to talk to that specific DB.

### C. The "ReAct" Agent (The Brain) 🧠
*   **What**: "Reasoning + Acting". The AI doesn't just talk; it thinks in steps.
*   **Why**: A normal LLM (ChatGPT) can't see your database. This Agent can.
*   **How**: It runs in a loop:
    1.  *User*: "Add a blog."
    2.  *AI Thought*: "I need to use a tool."
    3.  *AI Action*: Calls `tool_inspect_database()`.
    4.  *Observation*: "Table is called `wp_posts`."
    5.  *AI Action*: Calls `tool_execute_sql_write(...)`.
    6.  *Result*: "Done!"

### D. The "Safety Net" (The Bodyguard) 🛡️
*   **What**: Special code in `chat.py`.
*   **Why**: Sometimes the AI makes mistakes (e.g., returning a broken link or forgetting to show an image).
*   **How**:
    -   It watches every tool output.
    -   If the tool says "Here is the PDF link: http://...", the Safety Net GRABS that link and forces it onto the screen.

## 4. The "Dynamic Intelligence" Upgrade 🚀
This is the newest, most advanced part.
*   **Old Way**: We assumed every client had a table named `blogs`. (Bad, because clients are different).
*   **New Way (Phase 7)**:
    -   **Inspection**: The AI uses `tool_inspect_database` to "look" at the client's tables.
    -   **Schema Discovery**: It learns *"Ah, this client calls their table `articles`, not `blogs`."*
    -   **Execution**: It writes SQL specifically for *that* structure.

## 5. Summary Check
| Feature | Purpose |
| :--- | :--- |
| **Widget Loader** | Puts the chat on the client's site. |
| **API Key** | Tells us *which* client DB to connect to. |
| **Agent Tools** | The "Hands" (PDF, Excel, SQL, Unsplash). |
| **Dynamic Schema** | The "Eyes" (Allows AI to learn table structure). |
