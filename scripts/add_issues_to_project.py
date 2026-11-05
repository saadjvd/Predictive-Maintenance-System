"""
Add all issues and PRs to GitHub Project #1
"""
import subprocess
import time

PROJECT_NUM = "1"
OWNER = "saadjvd"
REPO = "Predictive-Maintenance-System"

# Issues 2 to 64, plus PR 1
urls = [f"https://github.com/{OWNER}/{REPO}/pull/1"] + [
    f"https://github.com/{OWNER}/{REPO}/issues/{i}" for i in range(2, 65)
]

print(f"Adding {len(urls)} items to Project #{PROJECT_NUM}...")

gh_path = r"C:\Program Files\GitHub CLI\gh.exe"

for idx, url in enumerate(urls, 1):
    cmd = [gh_path, "project", "item-add", PROJECT_NUM, "--owner", OWNER, "--url", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[{idx}/{len(urls)}] Added {url}")
    except subprocess.CalledProcessError as e:
        print(f"[{idx}/{len(urls)}] Failed {url}: {e.stderr.strip()}")
    time.sleep(0.4)

print("Done adding items to project.")

