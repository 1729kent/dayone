"""毎日の E2E 回帰: デモリポジトリでルーキーを走らせ、腐敗検知まで到達することを検証する。

使い方: APP_URL=https://... uv run python scripts/e2e_check.py
"""
import os
import sys
import time

import httpx

APP_URL = os.environ["APP_URL"].rstrip("/")
TIMEOUT_S = 12 * 60


def main() -> None:
    r = httpx.post(f"{APP_URL}/runs", json={}, timeout=30)
    if r.status_code == 429:
        sys.exit("cooldown active; retry later")
    r.raise_for_status()
    run_id = r.json()["run_id"]
    print(f"run started: {run_id}")

    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        time.sleep(30)
        run = httpx.get(f"{APP_URL}/api/runs/{run_id}", timeout=30).json()
        print(f"status={run['status']} decay={run['decay_score']}")
        if run["status"] == "completed":
            assert run["decay_score"] and run["decay_score"] > 0, \
                f"expected decay detection, got {run['decay_score']}"
            print("E2E OK: rot detected")
            return
        if run["status"] == "failed":
            sys.exit("E2E FAILED: run failed")
    sys.exit("E2E FAILED: timeout")


if __name__ == "__main__":
    main()
