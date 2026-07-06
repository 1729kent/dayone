from fastapi.testclient import TestClient

from dayone.common.config import Settings
from dayone.common.store import MemoryStore
from dayone.app.server import create_app


class FakeLauncher:
    def __init__(self):
        self.launched = []

    def launch(self, run_id, repo_url):
        self.launched.append((run_id, repo_url))


def mk():
    store, launcher = MemoryStore(), FakeLauncher()
    app = create_app(store=store, launcher=launcher,
                     settings=Settings(environ={"DAYONE_SCHED_TOKEN": "tok"}))
    return TestClient(app), store, launcher


def test_trigger_creates_run_and_launches():
    c, store, launcher = mk()
    r = c.post("/runs", json={})
    assert r.status_code == 200
    rid = r.json()["run_id"]
    assert store.get_run(rid).status == "queued"
    assert launcher.launched and launcher.launched[0][0] == rid


def test_cooldown_429():
    c, *_ = mk()
    assert c.post("/runs", json={}).status_code == 200
    assert c.post("/runs", json={}).status_code == 429


def test_events_after():
    c, store, _ = mk()
    rid = c.post("/runs", json={}).json()["run_id"]
    store.append_event(rid, "plan", {})
    store.append_event(rid, "exec", {})
    evs = c.get(f"/api/runs/{rid}/events?after=0").json()
    assert len(evs) == 1 and evs[0]["type"] == "exec"


def test_get_run_and_list():
    c, store, _ = mk()
    rid = c.post("/runs", json={}).json()["run_id"]
    assert c.get(f"/api/runs/{rid}").json()["id"] == rid
    assert c.get("/api/runs").json()[0]["id"] == rid
    assert c.get("/api/runs/nope").status_code == 404


def test_scheduled_requires_bearer_header():
    c, _, launcher = mk()
    assert c.post("/internal/scheduled").status_code == 403
    assert c.post("/internal/scheduled", headers={"Authorization": "Bearer bad"}).status_code == 403
    assert c.post("/internal/scheduled?token=tok").status_code == 403  # query は受け付けない
    assert c.post("/internal/scheduled", headers={"Authorization": "Bearer tok"}).status_code == 200
    assert len(launcher.launched) == 2


def test_repo_allowlist():
    c, *_ = mk()
    r = c.post("/runs", json={"repo_url": "https://github.com/evil/evil-repo"})
    assert r.status_code == 403
    assert c.post("/runs", json={"repo_url": "https://github.com/chalk/chalk"}).status_code == 200


def test_e2e_endpoint_bypasses_cooldown():
    c, _, launcher = mk()
    assert c.post("/runs", json={}).status_code == 200  # クールダウン消費
    assert c.post("/internal/e2e", json={}).status_code == 403  # 認証なしは拒否
    r = c.post("/internal/e2e", json={"repo_url": "https://github.com/1729kent/dayone-e2e-target"},
               headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200  # クールダウン中でも CI 経路は通る
    assert launcher.launched[-1][1].endswith("e2e-target")


def test_index_serves_html():
    c, *_ = mk()
    r = c.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_index_embeds_initial_runs():
    c, store, _ = mk()
    rid = c.post("/runs", json={}).json()["run_id"]
    html = c.get("/").text
    assert "window.__INITIAL_RUNS__" in html and rid in html


def test_trigger_rejects_bad_repo_url():
    c, *_ = mk()
    assert c.post("/runs", json={"repo_url": "https://evil.example.com/x"}).status_code == 400
    assert c.post("/runs", json={"repo_url": "git@github.com:a/b.git"}).status_code == 400
    assert c.post("/runs", json={"repo_url": "https://github.com/chalk/chalk"}).status_code == 200


def test_watchdog_fails_stuck_runs():
    import time as _time

    from dayone.common.models import Run

    c, store, _ = mk()
    store.create_run(Run(id="stuck1", repo_url="u", trigger="manual", status="running",
                         started_at=_time.time() - 3600))
    runs = c.get("/api/runs").json()
    stuck = next(r for r in runs if r["id"] == "stuck1")
    assert stuck["status"] == "failed"
