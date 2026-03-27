# Troubleshooting "AI Offline"

## Problem
The widget loaded on the Client ERP says "AI Offline". 

## Likely Causes
1.  **Backend Not Running:** The widget connects to `http://localhost:8000`. If Docker isn't running, it fails.
2.  **Mixed Content:** If Client ERP is `https://`, it blocks `http://localhost...`.
3.  **Vite vs Production:** The script tag points to port `5173` (Frontend Dev Server), which is fine for local testing but requires `npm run dev` to be active.

## Solution Steps

### 1. Ensure Services are Up
You must have **BOTH** terminals running:
1.  **Backend:** `docker-compose up` (Runs on port 8000)
    *   Test: Open `http://localhost:8000/` -> Should see `{"status": "Amoeba AI is active"}`.
2.  **Frontend:** `cd frontend && npm run dev` (Runs on port 5173)
    *   Test: Open `http://localhost:5173/widget-loader.js` -> Should see JavaScript code.

### 2. Check the Script Tag
The script tag validation:
```html
<script 
  src="http://localhost:5173/widget-loader.js" 
  data-api-key="YOUR_API_KEY"
></script>
```
*   **src**: Must match where your Frontend is running.
*   **data-api-key**: Must be a valid key from `client_config` table.

### 3. Verify API Key
If the Key is invalid, the backend rejects the connection (WebSocket closes), causing "Offline".
*   Check Key: `am_live_fME3...` looks correct format.
*   Verify in DB: Access `http://localhost:8000/api/clients` (if you have an endpoint) or check docker logs.

### 5. Connecting to Host Database from Docker
If your MySQL/Postgres is running on your **host machine** (Windows) and Amoeba is running in **Docker**, `localhost` will NOT work.

### The Problem
Inside a Docker container, `localhost` refers to the container itself. It cannot see your Windows MySQL.

### The Fix
Change the `host` in your API request from `localhost` to:
**`host.docker.internal`**

### Example Payload:
```json
{
    "db_type": "mysql",
    "host": "host.docker.internal",
    "port": 3306,
    "database": "thermosen",
    "username": "thermosentest",
    "password": "admin"
}
```

### 6. Database Permissions
If you get "Access Denied", ensure your MySQL user is allowed to connect from the Docker network.
1. Run this in MySQL:
   `CREATE USER 'thermosentest'@'%' IDENTIFIED BY 'admin';`
   `GRANT ALL PRIVILEGES ON thermosen.* TO 'thermosentest'@'%';`
   `FLUSH PRIVILEGES;`
2. The `@'%'` is critical—it allows the user to connect from the Docker virtual network instead of just `localhost`.
