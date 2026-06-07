import os
import base64
import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")

FILE_PATH = "output.png"
TARGET_PATH = "output.png"
BRANCH = "main"


def upload_image():
    if not GITHUB_TOKEN:
        raise ValueError("Missing GITHUB_TOKEN")

    if not GITHUB_REPOSITORY:
        raise ValueError("Missing GITHUB_REPOSITORY")

    if not os.path.exists(FILE_PATH):
        raise FileNotFoundError("output.png not found")

    with open(FILE_PATH, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    api_url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{TARGET_PATH}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    sha = None
    existing = requests.get(
        api_url,
        headers=headers,
        params={"ref": BRANCH},
        timeout=60,
    )

    if existing.status_code == 200:
        sha = existing.json().get("sha")

    payload = {
        "message": "Update output image",
        "content": content,
        "branch": BRANCH,
    }

    if sha:
        payload["sha"] = sha

    response = requests.put(
        api_url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    result = response.json()
    print("GitHub upload response:", result)

    if response.status_code not in [200, 201]:
        raise RuntimeError(f"Failed to upload output.png: {result}")

    print("output.png uploaded successfully")


if __name__ == "__main__":
    upload_image()
