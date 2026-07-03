from dayone.common.config import Settings
from dayone.common.models import Run, RunReport, Step, StepPlan
from dayone.common.store import MemoryStore
from dayone.rookie import main as rookie_main


def make_run():
    return Run(id="r1", repo_url="u", trigger="manual", status="queued", started_at=0.0)


def test_run_pipeline_happy(tmp_path, monkeypatch):
    store = MemoryStore()
    store.create_run(make_run())
    plan = StepPlan(doc_path="README.md",
                    steps=[Step(id=1, intent="i", command="true", expects="e")])

    class FakePlanner:
        def plan(self, d):
            return plan

    class FakeDiag:
        def diagnose(self, *a):
            return None

    class FakeReporter:
        def report(self, *a, **k):
            return RunReport(frictions=[], decay_score=0, ttfs_seconds=1.0, pr_url=None, summary="ok")

    def fake_clone(url, dst):
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "README.md").write_text("x")

    monkeypatch.setattr(rookie_main, "clone_repo", fake_clone)
    monkeypatch.setattr(rookie_main, "build_planner", lambda s: FakePlanner())
    monkeypatch.setattr(rookie_main, "build_diagnostician", lambda s: FakeDiag())
    monkeypatch.setattr(rookie_main, "build_reporter", lambda s, emit: FakeReporter())
    run = rookie_main.run_pipeline("u", "r1", store, tmp_path, Settings(environ={}))
    assert run.status == "completed"
    assert store.get_run("r1").decay_score == 0
    types = [e.type for e in store.get_events("r1")]
    assert "plan" in types and "report" in types


def test_run_pipeline_failure_marks_failed(tmp_path, monkeypatch):
    store = MemoryStore()
    store.create_run(make_run())

    def broken_clone(url, dst):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(rookie_main, "clone_repo", broken_clone)
    run = rookie_main.run_pipeline("u", "r1", store, tmp_path, Settings(environ={}))
    assert run.status == "failed"
    assert any(e.type == "error" for e in store.get_events("r1"))
    assert store.get_run("r1").finished_at is not None
