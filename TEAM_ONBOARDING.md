# Team Onboarding: Local Project Sharing Guide

## Goal
This guide explains how to invite your team members to work on the **Frontend/UI** of Amoeba AI by sharing the project files locally (without GitHub).

---

## 🚀 1. Prerequisites (For Team Members)
Before receiving the files, your team members need to install:

1.  **Node.js (v18 or higher)**: [Download Here](https://nodejs.org/)
    *   Verify: `node -v` and `npm -v` in terminal.
2.  **Docker Desktop (Optional but Recommended)**: [Download Here](https://www.docker.com/products/docker-desktop/)
    *   If they only work on UI, they *can* run the frontend without Docker, but they won't have a working backend unless you expose your machine's IP.
    *   **Best Practice:** Have them install Docker so they run the full stack.
3.  **VS Code**: Recommended editor.

---

## 📦 2. How to Pack the Project (For You)
To share the project effectively, you must **ZIP** the folder but **EXCLUDE** heavy/generated files.

### Steps to Pack:
1.  **Stop Docker:** Run `docker-compose down`.
2.  **Delete/Exclude these folders** before zipping:
    *   `node_modules/` (inside `frontend/`) - **Critical to remove (very heavy)**
    *   `venv/` (inside `backend/`)
    *   `__pycache__/` (everywhere)
    *   `.git/` (hidden folder)
    *   `postgres_data/` (if it exists in root)
    *   `dist/` (inside `frontend/`)
3.  **Zip the `amoeba-ai` folder**.
4.  **Share** via Google Drive, USB, or LAN.

---

## 🛠️ 3. How to Set Up (For Team Members)

### Step 1: Unzip & Open
1.  Unzip to a folder (e.g., `D:\Projects\amoeba-ai`).
2.  Open VS Code -> File -> Open Folder -> Select `amoeba-ai`.

### Step 2: Backend Setup (Docker)
Since the backend uses a database and Python, running it via Docker is easiest.

1.  Open Terminal in VS Code.
2.  Run:
    ```bash
    docker-compose up --build
    ```
3.  Wait for `Uvicorn running on http://0.0.0.0:8000`.
4.  Success: Backend is live at `http://localhost:8000`.

### Step 3: Frontend Setup (UI Development)
Team members should run the **Frontend** locally for hot-reloading.

1.  Open a **new** terminal (keep Docker running in the first one).
2.  Go to frontend folder:
    ```bash
    cd frontend
    ```
3.  Install dependencies (Required since you deleted `node_modules`):
    ```bash
    npm install
    ```
4.  Start the UI:
    ```bash
    npm run dev
    ```
5.  Open `http://localhost:5173`. Updates will reflect instantly.

---

## 📋 4. How to Assign Tasks (Without GitHub)
Since you are not using GitHub issues/projects yet, use a simple text file to track work.

1.  Create a file named `TASKS.md` in the root folder.
2.  List tasks with names:

    ```markdown
    # Frontend Tasks

    ## To Do
    - [ ] Design Login Page (Assigned to: Alex)
    - [ ] Fix Chat Bubble overlap (Assigned to: Sam)

    ## In Progress
    - [ ] Update Sidebar Colors (Assigned to: You)

    ## Done
    - [x] Initial Chat Widget
    ```

3.  **Syncing Work:**
    *   When a member finishes a task, they should zip **ONLY** the `frontend/src` folder (or specific files) and send it back to you.
    *   You then overwrite the files in your main project.
    *   *Warning: This is risky for complex work. Git is highly recommended for the future.*

---

## 🎨 Frontend Workflow
Your team will work in `frontend/src`.

| Action | Command (inside `frontend/`) |
| :--- | :--- |
| **Start UI** | `npm run dev` |
| **Install Package** | `npm install <package-name>` (e.g., `npm install framer-motion`) |

---

## ❓ Troubleshooting
**Q: "Backend connection failed"**
*   A: Ensure `docker-compose up` is running.

**Q: "npm command not found"**
*   A: Install Node.js.

**Q: "Conflict / Port in use"**
*   A: Stop other apps using port 8000 or 5173.
