import urllib.request, json, time

for i in range(25):
    try:
        req = urllib.request.Request('https://api.github.com/repos/Varunvasan1412/amoeba-ai/actions/runs?per_page=1', headers={'User-Agent':'M'})
        r = json.loads(urllib.request.urlopen(req).read().decode())
        w = r['workflow_runs'][0]
        sha = w.get('head_sha', '')[:7]
        num = w.get('run_number')
        status = w.get('status')
        conclusion = w.get('conclusion')
        print(f"Poll {i+1}: Run #{num} ({sha}) status={status} conclusion={conclusion}", flush=True)
        if sha == '42ec48a' and status == 'completed':
            print(f"Deployment finished with conclusion: {conclusion}", flush=True)
            break
    except Exception as e:
        print(f"Poll error: {e}", flush=True)
    time.sleep(8)
