r"""Deploy CineForge to a Hugging Face Space (CPU basic, free).

Usage:
    $env:HF_USERNAME="your-username"; $env:HF_TOKEN="hf_xxx"
    & backend\.venv\Scripts\python.exe spaces\upload_space.py

Steps: sync project -> temp staging -> create Space (sdk=docker) -> upload ->
poll build/runtime -> verify frontend + backend health.
"""
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = Path(tempfile.mkdtemp(prefix="cineforge-space-")).resolve()

EXCLUDE = [
    ".venv", "node_modules", ".next", "media", "__pycache__", ".pytest_cache",
    ".git", "docs", "deploy", "*.db", "*.pyc", "*.log",
]


def sync(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXCLUDE))
    print(f"  + {src.name} -> {dst}")


def main() -> int:
    user = os.environ.get("HF_USERNAME", "").strip()
    token = os.environ.get("HF_TOKEN", "").strip()
    if not user or not token:
        print("Set HF_USERNAME and HF_TOKEN (Settings > Access Tokens > New token, type: write).")
        return 1

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    repo_id = f"{user}/cineforge"

    print(f"==> [1/5] Syncing repo to staging ({STAGING})")
    for name in ("nginx.conf", "entrypoint.sh", "Dockerfile", "README.md", ".dockerignore"):
        shutil.copy2(ROOT / "spaces" / name, STAGING / name)
    sync(ROOT / "backend", STAGING / "backend")
    sync(ROOT / "frontend", STAGING / "frontend")

    print(f"==> [2/5] Ensuring Space {repo_id} exists (sdk=docker, cpu-basic)")
    try:
        api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker",
                        private=False, exist_ok=True)
        api.request_space_hardware(repo_id=repo_id, hardware="cpu-basic")
    except Exception as exc:  # noqa: BLE001
        print(f"  create_repo warning: {exc}")

    print("==> [3/5] Uploading files (this can take a few minutes for a first push)")
    api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=str(STAGING),
                      commit_message="deploy CineForge AI Studio")
    print("  uploaded.")

    base = f"https://{user}-cineforge.hf.space"
    print(f"==> [4/5] Waiting for build + app start (base: {base})")
    stage, deadline = "", time.time() + 900
    while time.time() < deadline:
        try:
            state = api.get_space_runtime(repo_id)
            stage = state.stage
            print(f"  [{time.strftime('%H:%M:%S')}] stage={stage} (runtime {state.runtime})")
            if stage in ("RUNNING", "APP_STARTED", "APP_RUNNING"):
                break
            if stage in ("ERROR", "STOPPED"):
                print(f"  build failed — logs: https://huggingface.co/spaces/{repo_id}/logs")
                return 1
        except Exception as exc:  # noqa: BLE001
            print(f"  runtime probe: {exc}")
        time.sleep(20)

    print(f"==> [5/5] Verifying endpoints on {base}")
    ok = 0
    for attempt in range(30):
        try:
            with urllib.request.urlopen(f"{base}/api/backend/healthz", timeout=15) as r:
                body = r.read().decode()
            print(f"  /api/backend/healthz -> HTTP {r.status} {body}")
            ok += 1
            break
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            print(f"  healthz try {attempt+1}: {exc}")
            time.sleep(10)
    try:
        with urllib.request.urlopen(base, timeout=15) as r:
            print(f"  / -> HTTP {r.status} (frontend up)")
        ok += 1
    except Exception as exc:  # noqa: BLE001
        print(f"  frontend probe failed: {exc}")

    print()
    print("============================================================")
    print(f" Studio   : {base}")
    print(f" Health   : {base}/api/backend/healthz")
    print(f" Logs     : https://huggingface.co/spaces/{repo_id}/logs")
    print(" Demo user: demo@cineforge.ai / cineforge123")
    print("============================================================")
    return 0 if ok == 2 else 2


if __name__ == "__main__":
    sys.exit(main())