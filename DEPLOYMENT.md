# Deployment & Architecture Guide

## 1. Hosting (Hostinger vs. VPS)
**Can you host this on Hostinger?**
-   **Shared Hosting**: **NO**. You cannot run Docker, Python (FastAPI), or persistent WebSockets on standard shared hosting.
-   **VPS (Virtual Private Server)**: **YES**. Hostinger offers VPS plans (Ubuntu). You can install Docker there and run this project exactly as you do on your local machine (`docker-compose up -d`).

## 2. Embedding (The "Script Iframe")
**Can you just use the script iframe line?**
-   **YES**. That is exactly how we built it.
-   **How**: You give your client a snippet:
    ```html
    <script src="https://your-saas-domain.com/widget-loader.js" data-api-key="CLIENT_API_KEY"></script>
    ```
-   **Result**: The widget loads from *your* server but floats on *their* website.

## 3. Data Isolation (Crucial)
**"It should directly integrate and work with client's db only"**
-   **Current Status**: **YES**, checking `management.py`, the system is designed to switch databases dynamically.
-   **How it works**:
    1.  Client Website sends `CLIENT_API_KEY` to your Backend.
    2.  Your Backend looks up that key in *your* `client_configs` table.
    3.  It finds the `db_connection_url` associated with that client (e.g., `postgresql://client_user:pass@client-db-host/client_db`).
    4.  It switches the "Phone Line". All subsequent SQL queries (Blogs, Reports, Sales) run against **THEIR DB URL**, not yours.

## 4. Where is the Content Stored?
**"If the user prompted to append a blog... where the content will be stored?"**
-   **Answer**: It is stored in the **Client's Database**.
-   **Mechanism**:
    -   `tool_create_blog` calls `create_async_engine(current_db_url.get())`.
    -   If `current_db_url` points to the Client's DB, the `INSERT INTO blogs` runs there.
-   **Requirement**: The Client's Database MUST have a table named `blogs` (schema matching your tool).
    -   *Future Plan*: You will need a way to "map" your tool to their specific table structure (e.g., if they call it `wp_posts` instead of `blogs`).

## 5. Security Note
-   Since you are connecting to external databases, your SaaS backend needs to be on a "allowlist" for your clients' firewalls.
