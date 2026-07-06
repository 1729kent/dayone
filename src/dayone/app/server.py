import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from dayone.common.config import Settings
from dayone.common.models import Run
from dayone.common.store import Store

DEFAULT_REPO = "https://github.com/1729kent/dayone-demo-node"
DEMO_REPOS = [DEFAULT_REPO, "https://github.com/1729kent/dayone-demo-py"]
COOLDOWN_SECONDS = 300
STATIC_DIR = Path(__file__).parent / "static"
REPO_URL_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+/?$")
STUCK_SECONDS = 1800  # queued/running のままこれを超えた run はウォッチドッグが failed に落とす

# 公開デモで実行できるリポジトリの許可リスト。
# サンドボックスは環境変数スクラブ等で封じ込めているが、任意リポジトリの README コマンド実行は
# メタデータサーバー経由のトークン取得・課金DoS 等の攻撃面が残るため、信頼境界を許可リストで引く。
ALLOWED_REPOS = {
    "1729kent/dayone", "1729kent/dayone-demo-node", "1729kent/dayone-demo-py",
    "1729kent/dayone-e2e-target",
    # 軽量・著名な OSS のキュレーション（審査員のお試し用）
    "chalk/chalk", "fastapi/fastapi", "pallets/click", "encode/httpx",
    "tj/commander.js", "sindresorhus/slugify", "expressjs/express",
}


def repo_full(url: str) -> str:
    return "/".join(url.rstrip("/").removesuffix(".git").split("/")[-2:]).lower()


def create_app(store: Store | None = None, launcher=None, settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    if store is None:
        from dayone.common.store import FirestoreStore

        store = FirestoreStore(s.project_id)
    if launcher is None:
        from dayone.app.launcher import CloudRunJobLauncher

        launcher = CloudRunJobLauncher(s.project_id, s.region, s.job_name)

    app = FastAPI(title="DayOne")

    def start_run(repo_url: str, trigger: str) -> str:
        run_id = uuid.uuid4().hex[:12]
        store.create_run(Run(id=run_id, repo_url=repo_url, trigger=trigger,
                             status="queued", started_at=time.time()))
        launcher.launch(run_id, repo_url)
        return run_id

    @app.get("/health")  # /healthz は Cloud Run GFE の予約パスで404になるため使わない
    def healthz():
        return {"ok": True}

    def reconciled_runs() -> list[Run]:
        """滞留した run をウォッチドッグで failed に落としてから返す"""
        runs = store.list_runs()
        now = time.time()
        for i, r in enumerate(runs):
            if r.status in ("queued", "running") and now - r.started_at > STUCK_SECONDS:
                store.update_run(r.id, status="failed", finished_at=now,
                                 summary="実行が滞留したためウォッチドッグが自動クローズしました。")
                runs[i] = store.get_run(r.id) or r
        return runs

    @app.get("/")
    def index():
        # 初期データを埋め込み、審査員が開いた瞬間に実績が見える状態にする（CSR待ちの空画面を排除）
        html = (STATIC_DIR / "index.html").read_text()
        initial = json.dumps([r.model_dump() for r in reconciled_runs()], ensure_ascii=False)
        html = html.replace("/*__INITIAL_RUNS__*/", f"window.__INITIAL_RUNS__ = {initial};")
        return HTMLResponse(html)

    @app.get("/api/runs")
    def list_runs():
        return [r.model_dump() for r in reconciled_runs()]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(404)
        return run.model_dump()

    @app.get("/api/runs/{run_id}/events")
    def get_events(run_id: str, after: int = -1):
        return [e.model_dump() for e in store.get_events(run_id, after_seq=after)]

    @app.post("/runs")
    async def trigger(request: Request):
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        repo_url = ((body or {}).get("repo_url") or DEFAULT_REPO).strip()
        if not REPO_URL_RE.match(repo_url):
            raise HTTPException(400, detail="公開GitHubリポジトリのURL（https://github.com/owner/repo）を指定してください")
        allowed = ALLOWED_REPOS | set(filter(None, s.extra_allowed_repos.lower().split(",")))
        if repo_full(repo_url) not in allowed:
            raise HTTPException(
                403,
                detail="公開デモでは安全のため許可リストのリポジトリのみ実行できます"
                       "（例: chalk/chalk, fastapi/fastapi, pallets/click, encode/httpx）。"
                       "理由はREADMEのセキュリティ設計を参照してください")
        if not store.try_acquire_cooldown(COOLDOWN_SECONDS, now=time.time()):
            raise HTTPException(429, detail="cooldown: 5分に1回まで実行できます")
        return {"run_id": start_run(repo_url, "manual")}

    def check_bearer(authorization: str) -> None:
        if not s.sched_token or authorization != f"Bearer {s.sched_token}":
            raise HTTPException(403)

    @app.post("/internal/scheduled")
    def scheduled(authorization: str = Header("")):
        check_bearer(authorization)
        return {"run_ids": [start_run(u, "scheduled") for u in DEMO_REPOS]}

    @app.post("/internal/e2e")
    async def e2e_trigger(request: Request, authorization: str = Header("")):
        """CI 用の回帰トリガー。公開クールダウンと競合しない専用経路（Bearer 認証）"""
        check_bearer(authorization)
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        repo_url = (body or {}).get("repo_url") or DEFAULT_REPO
        return {"run_id": start_run(repo_url, "manual")}

    @app.get("/api/runs/{run_id}/stream")
    async def stream(run_id: str):
        async def gen():
            last = -1
            for _ in range(600):
                for e in store.get_events(run_id, after_seq=last):
                    last = e.seq
                    yield f"data: {json.dumps(e.model_dump(), ensure_ascii=False)}\n\n"
                run = store.get_run(run_id)
                if run and run.status in ("completed", "failed"):
                    yield f"event: done\ndata: {json.dumps(run.model_dump(), ensure_ascii=False)}\n\n"
                    return
                await asyncio.sleep(1)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    return app


def main():
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
