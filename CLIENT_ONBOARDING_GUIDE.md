# Amoeba AI: Client Onboarding Guide (v2 Schema RAG Architecture)

With the new AI-driven Schema RAG Engine, onboarding a new client is completely automated through codebase scanning and vector embeddings. You no longer need to manually map tables, configure relationships, or create data labels in the Wizard.

Follow these 4 steps to onboard a new client to Amoeba AI.

---

## Step 1: Create Client & Connect Database (Admin Panel)

*The AI cannot guess database credentials, so this must be done manually.*

1. Log in to the **Amoeba Admin Panel**.
2. Navigate to **Clients** and create a new client (e.g., "New Look").
3. Copy the client's unique **Widget API Key**.
4. Navigate to the **Wizard** for the newly created client.
5. In Step 1 of the Wizard, fill in the **Database Connection** details:
   - **Database Type**: MySQL (or PostgreSQL depending on the client)
   - **Host, Port, Username, Password, Database Name** (Must be accessible by the Amoeba VPS)
6. Click **"Connect ERP Database"**.
7. Once the connection is successful, click **"Skip Wizard"** at the bottom right. The AI will handle the rest!

---

## Step 2: Extract & Sync Database Schemas

*This step teaches Amoeba's Vector Brain exactly what tables, columns, and row counts exist in the client's database.*

Run the **Schema Extractor** script from the Amoeba backend:

```bash
docker exec amoeba-ai-backend-1 python scripts/schema_extractor.py <DB_HOST> <DB_PORT> <DB_USER> <DB_PASS> <DB_NAME> <API_KEY>
```

**Example:**
```bash
docker exec amoeba-ai-backend-1 python scripts/schema_extractor.py srv1556.hstgr.io 3306 u161593822_newlook MySuperSecretPassword u161593822_newlook am_live_123456...
```

*Expected Output:* `✅ Success! Amoeba responded: {"status":"success","tables_learned":145}`

---

## Step 3: Map Business Logic & Terminology (Universal Connector)

*The AI knows the tables exist, but it doesn't know that humans call `enquiry_header` a "Quotation". We scan the client's codebase to automatically build these Semantic Mappings.*

Run the **Universal Connector** on the machine hosting the client's source code:

```bash
docker exec amoeba-ai-backend-1 python scripts/universal_connector.py "/path/to/client/codebase" "<API_KEY>"
```

*(Note: The Universal Connector analyzes `.php`, `.py`, and `.ts` files to find SQL queries and variables, mapping them directly to the database tables discovered in Step 2).*

*Expected Output:* `✅ Semantic Sync Success! Amoeba responded: {"status":"success","mappings_learned":...}`

---

## Step 4: Install the Chat Widget

*The AI is now fully trained on the client's database structure and custom terminology. It's ready to go live.*

Add the following snippet just before the closing `</body>` tag (e.g., in `footer.php` or `index.html`) in the client's web application:

```html
<script 
  src="https://amoeba.space/widget-loader.js" 
  data-api-key="YOUR_CLIENT_API_KEY">
</script>
```

---

### Troubleshooting

- **AI says "Table not found" or hallucinates table names:** 
  You probably missed Step 2 (Schema Extraction). The AI is guessing table names instead of using the real schema.
- **AI queries the wrong table (e.g. `quotation_header` instead of `enquiry_header`):** 
  You probably missed Step 3 (Universal Connector). The AI doesn't know the client's specific terminology. 
- **Error: `Could not parse SQLAlchemy URL`:** 
  The database connection details in Step 1 are empty, malformed, or have the wrong Database Type selected.
