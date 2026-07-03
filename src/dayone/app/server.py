import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from dayone.common.config import Settings
from dayone.common.models import Run
from dayone.common.store import Store

DEFAULT_REPO = "https://github.com/1729kent/dayone-demo-node"
DEMO_REPOS = [DEFAULT_REPO, "https://github.com/1729kent/dayone-demo-py"]
COOLDOWN_SECONDS = 300
STATIC_DIR = Path(__file__).parent / "static"


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

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/runs")
    def list_runs():
        return [r.model_dump() for r in store.list_runs()]

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
        if not store.try_acquire_cooldown(COOLDOWN_SECONDS, now=time.time()):
            raise HTTPException(429, detail="cooldown: 5分に1回まで実行できます")
        repo_url = (body or {}).get("repo_url") or DEFAULT_REPO
        return {"run_id": start_run(repo_url, "manual")}

    @app.post("/internal/scheduled")
    def scheduled(token: str = ""):
        if not s.sched_token or token != s.sched_token:
            raise HTTPException(403)
        return {"run_ids": [start_run(u, "scheduled") for u in DEMO_REPOS]}

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
