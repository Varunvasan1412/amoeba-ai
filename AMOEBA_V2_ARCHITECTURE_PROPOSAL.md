# Amoeba AI V2: Enterprise Architecture & Scaling Plan

This document outlines the architectural shift for Amoeba AI, transitioning from a "Raw SQL Guesser" to a deterministic, enterprise-ready AI Orchestrator. It covers all major edge cases, technical solutions, and exact developer workflows for client onboarding.

---

## 1. Case: Navigation Hallucination (404 Errors)
**The Problem Statement:**
The AI currently guesses URLs based on natural language (e.g., guessing `/settings` when the client uses `/user/prefs`), leading to 404 errors.

**The Solution (Strict RAG & Constrained Decoding):**
The AI is no longer allowed to generate URLs freely. It must select from a pre-verified list of scraped routes using a Vector Database.

**How it works (The Mechanics):**
1. User types "Take me to settings".
2. Amoeba embeds the query and runs a mathematical Vector Search against the 30,000 verified routes in `pgvector`.
3. The database returns the top 3 actual routes. The AI is forced to pick one of those 3 verified routes. 

**What Needs to be Built (Internal):**
- Vectorize the output of `universal_connector.py` and store it in `pgvector`.
- Update the Chat Router to query the vector database before responding to navigation prompts.

**What the Client Developer Does:**
- **Zero extra work.** They continue to run `universal_connector.py` exactly as they do today.

---

## 2. Case: The Modern ERP (Built with Laravel, Express, APIs)
**The Problem Statement:**
Modern ERPs have thousands of tables. Forcing a developer to manually map table joins in the Amoeba Dashboard is unscalable and highly inaccurate.

**The Solution (OpenAPI Auto-Tooling):**
If the client has existing APIs, Amoeba skips the database entirely. It automatically generates AI Tools directly from their API documentation.

**How it works (The Mechanics):**
Amoeba reads the client's standard `.json` API spec file. OpenAI's function-calling engine instantly maps every API endpoint into an executable "Tool" the AI can use to fetch or push data.

**What Needs to be Built (Internal):**
- An upload UI in the Admin Panel for `.json` Swagger/OpenAPI files.
- Integration with LangChain or OpenAI's native OpenAPI parser to convert the JSON into Tools.

**What the Client Developer Does:**
1. Run a 1-line command in their framework (e.g., `php artisan l5-swagger:generate`) to export their API documentation as a JSON file.
2. Upload the JSON file to Amoeba. (Time taken: 5 minutes. Zero AI code written).

---

## 3. Case: The High-Security Enterprise (Model Context Protocol)
**The Problem Statement:**
Large enterprises (banks, healthcare) will refuse to upload API specs or give raw database access due to security compliance.

**The Solution (MCP SDK / Custom Tools):**
Amoeba connects to a highly secure Model Context Protocol (MCP) server hosted on the client's own infrastructure.

**How it works (The Mechanics):**
The client defines specific, constrained functions (Tools) on their own server. Amoeba simply sends an HTTP/SSE request asking the server to execute a specific tool (e.g., `get_user(123)`). The client's server executes the logic safely behind their firewall and returns the data.

**What Needs to be Built (Internal):**
- Support for connecting to external MCP endpoints.

**What the Client Developer Does:**
1. Download a tiny Python/Node SDK.
2. Write 5 to 10 wrapper functions for their top business operations, decorating them with `@mcp.tool()`.
3. Start their server. (Time taken: 2 hours. Total control retained by the client).

---

## 4. Case: The Legacy Monolith (CodeIgniter, No APIs)
**The Problem Statement:**
The client has a 15-year-old database with zero APIs and terrible naming conventions. The AI guesses the table joins incorrectly, and manual dashboard mapping is too painful.

**The Solution (Schema RAG via Vanna.ai):**
Amoeba connects to the raw database, automatically reads the structural blueprint (DDL), and learns the table joins from past human queries.

**How it works (The Mechanics):**
1. **The Blueprint:** Amoeba runs `SHOW CREATE TABLE` to memorize column types and foreign keys.
2. **The Rosetta Stone:** Amoeba reads 20-30 historical SQL queries provided by the client, dissecting how the client manually joined tables in the past. 
3. When asked a new question, Amoeba uses Vector Search to find the most relevant past query, copies the complex join logic, and writes a perfect new SQL query.

**What Needs to be Built (Internal):**
- Replace current Text-to-SQL logic with `Vanna.ai` or `LlamaIndex` SQL Engine.
- Create an upload field for a "SQL Cheat Sheet" (.txt) in the admin panel.

**What the Client Developer Does:**
1. Provide Read-Only database credentials.
2. Copy-paste 20 to 30 SQL queries they currently use for their daily reporting into a text file, and upload it. (Time taken: 15 minutes. Zero manual UI mapping).

---

## 5. Case: Complex Analytics & Data Formatting
**The Problem Statement:**
Users ask for complex math: *"Group all employees into 10-year age buckets and format it as a grid."* Forcing the AI to write a 50-line SQL query with `CASE WHEN` statements usually fails.

**The Solution (Two-Step Code Interpreter):**
Amoeba pulls simple raw data using SQL, and formats it using a Python sandbox.

**How it works (The Mechanics):**
1. Amoeba writes simple SQL: `SELECT name, age FROM employees`.
2. Amoeba spins up an invisible Python Sandbox, writes a `pandas` script to calculate the 10-year buckets, and returns the finished table.

**What Needs to be Built (Internal):**
- A secure Python execution environment (Code Interpreter) in the backend.

**What the Client Developer Does:**
- **Zero work.** This is handled entirely by Amoeba's internal architecture.

---

## 6. Case: The Dangerous "WRITE" Action (e.g., Giving a Raise)
**The Problem Statement:**
Users ask the AI to modify the database (*"Give these 5 people a 10% raise"*). If the AI hallucinates an `UPDATE` query on a legacy database, it could corrupt the entire system.

**The Solution (Human-in-the-Loop Safeguard):**
Text-to-SQL is strictly sandboxed. Any destructive action is paused until human approval.

**How it works (The Mechanics):**
If Amoeba detects an `UPDATE`, `INSERT`, or `DELETE` intent, it drafts the SQL query but sets its status to `pending_approval`. A UI modal pops up showing the exact database impact, requiring the manager to click "Approve" before the query executes.

**What Needs to be Built (Internal):**
- Query execution blocker for non-SELECT statements.
- An "Execution Approval Modal" in the React frontend.

**What the Client Developer Does:**
- **Zero work.** They enjoy the peace of mind knowing the AI cannot accidentally destroy their database.

---
*End of Blueprint.*
