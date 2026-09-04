# Amoeba AI: Client Onboarding & Integration Guide

This document outlines the exact steps required to onboard a new client, integrate the AI chat widget into their website, and teach the AI their custom navigation routes and database structure.

---

## Phase 1: Create the Client Account
Before touching any code, you must generate a unique identity for the client on your Amoeba AI platform.

1. Log into your **Amoeba Admin Panel**.
2. Navigate to the **Clients** section and click **Add New Client**.
3. Fill in their business details.
4. The system will generate a unique **API Key** for this client (e.g., `a68ed0d9-97ff-4b8a-a9a1-8ca5a6718645`). Save this key!

---

## Phase 2: Frontend Integration (The Widget)
You must inject the Amoeba AI Widget into the client's website. This requires zero downloads or zip files—it is entirely cloud-hosted.

**The Action:**
Copy the following script tag and paste it into the client's global layout file (e.g., `footer.php`, `index.html`, or the main React/Next.js layout), right before the closing `</body>` tag.

```html
<!-- Amoeba AI Cloud Widget -->
<script 
    src="https://amoeba.space/widget-loader.js" 
    data-api-key="YOUR_CLIENTS_API_KEY_HERE"
></script>
```

*Note: The script automatically detects the environment. It will connect to your live server over the internet without conflicting with any of the client's existing CSS or JavaScript.*

---

## Phase 3: Route Learning (Teaching Navigation)
For the AI to successfully navigate the client's dashboard (e.g., redirecting users to the "Settings" page), it needs a map of their website. This map is generated using the `universal_connector.py` tool.

### Scenario A: You have their Source Code (e.g., Local Projects)
If you built the client's project or have a copy of their source code on your laptop:

1. Open your terminal on your laptop.
2. Navigate to your Amoeba backend directory:
   ```bash
   cd D:\AHATTRICKZ-PROJECT\amoeba-ai\backend
   ```
3. Run the scanner script against their source code folder, using their specific API Key:
   ```bash
   python scripts\universal_connector.py "C:\Path\To\Their\Source\Code" "YOUR_CLIENTS_API_KEY_HERE"
   ```
4. **Done.** The script will instantly scan their files and upload the navigation map to your live Amoeba server. 

### Scenario B: You DO NOT have their Source Code (e.g., Third-Party Enterprise)
If the client's source code is strictly confidential and locked on their private servers, you have two options:

**Option 1: The Client IT Team runs it (Recommended)**
1. Email the `universal_connector.py` file to the client's IT department.
2. Provide them with their API key.
3. Ask their IT guy to place the file inside their main project folder, open their terminal, navigate to that folder, and run the script like this:
   ```bash
   python universal_connector.py "C:\Path\To\Their\Project" "YOUR_CLIENTS_API_KEY_HERE"
   ```
   *The script will safely map their routes and send the metadata to your Amoeba server.*

**Option 2: Manual Entry via Admin Panel**
If they refuse to run scripts, simply ask them for a spreadsheet of their top 10 URLs (e.g., `Dashboard -> /dashboard`, `Profile -> /users/profile`). You can manually add these routes to their profile in your Amoeba Admin Panel.

---

## Phase 4: Data Integration (Optional)
If the client wants the AI to answer specific questions about their live business data (e.g., "How many orders did we get today?"), you must connect Amoeba to their database.

1. Ask the client's IT team for a **Read-Only Database Connection String**. 
   *(Example: `mysql://amoeba_user:password123@104.23.55.12/client_db`)*
2. Log into your **Amoeba Admin Panel**.
3. Open the client's profile.
4. Scroll to the **Database Configuration** section and paste the connection string.
5. Save. 

**Done.** The widget on their live website is now fully capable of reading their database and generating real-time charts and reports!
