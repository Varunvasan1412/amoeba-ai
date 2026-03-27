# Client Onboarding Guide (ACP v1)

## 1. Overview
Amoeba AI allows you to onboard new client ERP systems entirely through this interface. This tool manages the connection, security, and report definitions automatically.

**Who is this for?** System Administrators responsible for adding new clients (ERPs) to the Amoeba AI platform.

## 2. Step-by-Step Onboarding

### Step 1: Create Client
1. Enter the **Client Name** (e.g., "Northwind Traders").
2. Click **Create Client**.
3. **IMPORTANT:** Copy the **API Key** immediately. It is shown only once. You will need this to configure the chat widget.

### Step 2: Connect ERP Database
1. Select the **Database Type** (MySQL or PostgreSQL).
2. Enter the **Host** IP/Domain, **Port**, **Database Name**, **Username**, and **Password**.
3. Click **Connect & Verify**.
   - *Success:* The system has securely saved the connection.
   - *Failure:* Check your credentials or firewall settings.

### Step 3: Discover Tables
1. Click **Scan Database**.
2. Review the list of discovered tables and columns.
3. Use this list to decide which tables contain the data you want to report on.

### Step 4: Register Reports
1. Enter a **Report Name** (e.g., "Sales Report").
2. Select the **Base Table** from the dropdown (e.g., `orders`).
3. (Optional) Select a **Date Column** if the report should be filterable by date (e.g., `order_date`).
4. Click **Register Report**.
   - The system auto-generates the necessary SQL.
   - The report is immediately available to the AI.

### Step 5: Embed Chat Widget
Use the API Key from Step 1 to configure the widget on the client's site:
`ws://your-server/api/ws/chat?api_key=YOUR_API_KEY`

## 3. What Clients NEVER Need to Do
- **NO SQL:** You do not need to write `SELECT` statements.
- **NO Backend Access:** You do not need SSH access to the server.
- **NO Config Files:** You do not need to edit `amoeba.reports.json` or environment variables.

## 4. Common Errors & Fixes
- **"Invalid API Key"**: Ensure you copied the full key string without spaces. If lost, you must create a new client entry.
- **"Connection Failed"**: Verify the database host is reachable from the Amoeba AI server and that the username/password are correct.
- **"Table not found"**: Ensure the username provided has `SELECT` permissions on the target database.
