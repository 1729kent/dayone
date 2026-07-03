from dayone.common.models import Run
from dayone.common.store import MemoryStore


def make_run(rid="r1", ts=100.0):
    return Run(id=rid, repo_url="https://github.com/x/y", trigger="manual",
               status="queued", started_at=ts)


def test_run_crud():
    s = MemoryStore()
    s.create_run(make_run())
    s.update_run("r1", status="running")
    assert s.get_run("r1").status == "running"
    assert s.get_run("nope") is None


def test_list_runs_desc():
    s = MemoryStore()
    s.create_run(make_run("a", 1.0))
    s.create_run(make_run("b", 2.0))
    assert [r.id for r in s.list_runs()] == ["b", "a"]


def test_events_seq_and_after():
    s = MemoryStore()
    s.create_run(make_run())
    assert s.append_event("r1", "plan", {"n": 1}) == 0
    assert s.append_event("r1", "exec", {"n": 2}) == 1
    evs = s.get_events("r1", after_seq=0)
    assert len(evs) == 1 and evs[0].type == "exec"


def test_cooldown():
    s = MemoryStore()
    assert s.try_acquire_cooldown(300, now=1000.0) is True
    assert s.try_acquire_cooldown(300, now=1100.0) is False
    assert s.try_acquire_cooldown(300, now=1301.0) is True
