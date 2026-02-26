# Hostinger VPS Deployment Guide: Zero to Live 🚀

This guide assumes you are on Windows and want to host `amoeba-ai` on a Hostinger VPS (Ubuntu).

## Phase 1: Get the Server 🖥️
1.  **Buy VPS**: Go to Hostinger -> VPS -> Select "KVM 1" or higher (4GB RAM recommended for AI/Docker).
2.  **OS Selection**: Choose **Ubuntu 22.04 (64-bit)**.
3.  **Note Credentials**: You will get an IP Address (e.g., `123.45.67.89`) and a `root` password.

## Phase 2: Connect via SSH 🔌
1.  Open **Command Prompt** (Cmd) or PowerShell on Windows.
2.  Type:
    ```bash
    ssh root@<YOUR_VPS_IP>
    ```
3.  Type "yes" to trust the host.
4.  Enter the password (characters won't show while typing).

## Phase 3: Install Docker 🐳
(Run these commands inside the SSH terminal)
1.  Update the system:
    ```bash
    apt update && apt upgrade -y
    ```
2.  Install Docker (One-step script):
    ```bash
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    ```
3.  Verify:
    ```bash
    docker --version
    docker compose version
    ```

## Phase 4: Upload Your Code 📤
Since you are on Windows, the easiest way is **FileZilla** or **WinSCP**.

1.  **Download FileZilla Client**: [https://filezilla-project.org/](https://filezilla-project.org/).
2.  **Connect**:
    -   **Host**: `sftp://<YOUR_VPS_IP>`
    -   **User**: `root`
    -   **Pass**: Your VPS password.
3.  **Upload**:
    -   Create a folder `/root/amoeba-ai` on the server (Right panel).
    -   Drag and drop **ALL** files from your local `d:\AHATTRICKZ-PROJECT\amoeba-ai` (Left panel) to the server folder.
    -   **Exclude**: `node_modules`, `.git`, `.venv` (These are huge and unnecessary).

## Phase 5: Configuration ⚙️
1.  Back in your SSH terminal:
    ```bash
    cd /root/amoeba-ai
    ```
2.  Create `.env` file (if you didn't upload it):
    ```bash
    nano backend/.env
    ```
3.  Paste your secrets (API Keys, Database URL).
    -   *Tip*: If you want a database on the VPS too, add a Postgres service to `docker-compose.yml`. For now, use your external `DATABASE_URL`.
4.  Save: `Ctrl+O`, `Enter`, `Ctrl+X`.

## Phase 6: Go Live! 🟢
1.  Run the application:
    ```bash
    docker compose up -d --build
    ```
2.  **Check Logs**:
    ```bash
    docker compose logs -f backend
    ```
3.  **Visit in Browser**:
    `http://<YOUR_VPS_IP>:8000` (Backend API)
    `http://<YOUR_VPS_IP>:5173` (Frontend - *Note: Vite Dev Server is not for production*).

### IMPORTANT: Production Build ⚠️
You are currently running the **Dev Server** (`npm run dev`). For live deployment:
1.  Update `frontend/Dockerfile` to build the app (Nginx).
2.  OR simpler for now:
    -   Navigate to `http://<YOUR_VPS_IP>:5173/widget-loader.js`.
    -   Use that link in your client's script tag!

## Phase 7: Domain Name (Optional) 🌐
To use `https://api.yourdomain.com`:
1.  Go to your Domain Registrar (Namecheap/GoDaddy).
2.  Add an **A Record**: `@` points to `<YOUR_VPS_IP>`.
3.  On VPS, install **Caddy** (Simplest HTTPS):
    ```bash
    apt install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt update
    apt install caddy
    ```
4.  Edit Caddyfile:
    ```bash
    nano /etc/caddy/Caddyfile
    ```
    ```
    yourdomain.com {
        reverse_proxy localhost:8000
    }
    ```
5.  Restart Caddy:
    ```bash
    systemctl restart caddy
    ```
    Now your API is secure at `https://yourdomain.com`! 🔒
