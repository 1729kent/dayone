"""シードデータ入りのローカル開発サーバー。UI 確認・デモ動画撮影用。

使い方: uv run python scripts/dev_server.py [port]
"""
import sys
import time

import uvicorn

from dayone.app.server import create_app
from dayone.common.config import Settings
from dayone.common.models import Run
from dayone.common.store import MemoryStore


class NoopLauncher:
    def launch(self, run_id, repo_url):
        print(f"[dev] launch requested: {run_id} {repo_url}（dev サーバーでは何も起きません）")


def seed(store: MemoryStore) -> None:
    now = time.time()
    for i, (score, ttfs, status) in enumerate([(62, None, "completed"), (45, 380.0, "completed"),
                                               (15, 210.0, "completed"), (0, 184.0, "completed")]):
        rid = f"seed{i}"
        store.create_run(Run(id=rid, repo_url="https://github.com/1729kent/dayone-demo-node",
                             trigger="scheduled" if i % 2 else "manual", status=status,
                             started_at=now - (4 - i) * 86400,
                             finished_at=now - (4 - i) * 86400 + 300,
                             decay_score=score, ttfs_seconds=ttfs,
                             pr_url="https://github.com/1729kent/dayone-demo-node/pull/1" if score else None,
                             summary="README の setup 手順が改名済みスクリプトを指しており初回実行が失敗しました。"
                                     "正しい bootstrap 手順を特定し、修正PRを提出しています。" if score else
                                     "本日は摩擦ゼロ。ドキュメントは健全です。"))
    rid = "seed0"
    events = [
        ("phase", {"name": "clone", "repo_url": "https://github.com/1729kent/dayone-demo-node"}),
        ("phase", {"name": "plan"}),
        ("plan", {"doc_path": "README.md", "steps": [
            {"id": 1, "intent": "依存をインストール", "command": "npm install"},
            {"id": 2, "intent": "初期設定を実行", "command": "npm run setup"},
            {"id": 3, "intent": "動作確認", "command": "npm test"}]}),
        ("phase", {"name": "exec"}),
        ("exec", {"step_id": 1, "command": "npm install", "intent": "依存をインストール"}),
        ("exec", {"step_id": 2, "command": "npm run setup", "intent": "初期設定を実行"}),
        ("diagnose", {"step_id": 2, "stderr": "npm error Missing script: \"setup\"\nnpm error\nnpm error To see a list of scripts, run:\nnpm error   npm run"}),
        ("fix", {"step_id": 2, "working_command": "npm run bootstrap", "category": "doc_outdated"}),
        ("exec", {"step_id": 3, "command": "npm test", "intent": "動作確認"}),
        ("phase", {"name": "report"}),
        ("pr", {"url": "https://github.com/1729kent/dayone-demo-node/pull/1"}),
        ("report", {"decay_score": 62, "ttfs_seconds": None, "pr_url": "https://github.com/1729kent/dayone-demo-node/pull/1",
                    "summary": "README の setup 手順が改名済みスクリプトを指しており初回実行が失敗しました。",
                    "frictions": [
                        {"step_id": 2, "category": "doc_outdated", "severity": "medium", "doc_line": 12,
                         "explanation": "npm scripts の setup が bootstrap に改名されていた", "found_fix": True},
                        {"step_id": 4, "category": "missing_prereq", "severity": "high", "doc_line": None,
                         "explanation": ".env.example のキー名が実装と不一致", "found_fix": False}]}),
    ]
    for t, p in events:
        store.append_event(rid, t, p)


if __name__ == "__main__":
    store = MemoryStore()
    seed(store)
    app = create_app(store=store, launcher=NoopLauncher(), settings=Settings(environ={}))
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    uvicorn.run(app, host="127.0.0.1", port=port)
