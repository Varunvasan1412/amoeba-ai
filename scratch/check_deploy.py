import urllib.request
import json
import time

url = "https://api.github.com/repos/Varunvasan1412/amoeba-ai/actions/runs"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

for _ in range(30):
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            runs = data.get("workflow_runs", [])
            if runs:
                latest = runs[0]
                status = latest["status"]
                conclusion = latest["conclusion"]
                commit_msg = latest["head_commit"]["message"].split("\n")[0]
                print(f"Run {latest['id']} ({status}/{conclusion}): {commit_msg}")
                if status == "completed":
                    print(f"Deployment completed with conclusion: {conclusion}")
                    break
    except Exception as e:
        print(f"Error fetching runs: {e}")
    time.sleep(5)
