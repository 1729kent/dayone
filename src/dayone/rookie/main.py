import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dayone.common.config import Settings
from dayone.common.llm import LLM
from dayone.common.models import Run
from dayone.common.store import Store
from dayone.rookie.diagnostician import GeminiDiagnostician
from dayone.rookie.executor import Budget, Executor
from dayone.rookie.github_client import GitHubClient
from dayone.rookie.judge import OutputJudge
from dayone.rookie.planner import Planner
from dayone.rookie.reporter import Reporter
from dayone.rookie.sandbox import Sandbox


def clone_repo(repo_url: str, dst: Path) -> None:
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(dst)],
                   check=True, capture_output=True, text=True, timeout=120)


def build_planner(s: Settings) -> Planner:
    return Planner(LLM(s.model))


def build_diagnostician(s: Settings) -> GeminiDiagnostician:
    return GeminiDiagnostician(LLM(s.model))


def build_reporter(s: Settings, emit) -> Reporter:
    github = GitHubClient(s.github_token) if s.github_token else None
    return Reporter(LLM(s.model), github, emit, create_pr=s.create_pr)


def run_pipeline(repo_url: str, run_id: str, store: Store, work_dir: Path, s: Settings) -> Run:
    started_at = time.time()

    def emit(type_: str, payload: dict) -> None:
        print(f"[{type_}] {payload}", flush=True)
        store.append_event(run_id, type_, payload)

    store.update_run(run_id, status="running", started_at=started_at)
    try:
        repo_dir = work_dir / "repo"
        emit("phase", {"name": "clone", "repo_url": repo_url})
        clone_repo(repo_url, repo_dir)

        emit("phase", {"name": "plan"})
        plan = build_planner(s).plan(repo_dir)
        emit("plan", {"doc_path": plan.doc_path,
                      "steps": [{"id": st.id, "intent": st.intent, "command": st.command}
                                for st in plan.steps]})

        emit("phase", {"name": "exec"})
        executor = Executor(Sandbox(cwd=repo_dir), OutputJudge(LLM(s.model_lite)),
                            build_diagnostician(s), emit, Budget())
        outcomes = executor.run(plan, repo_dir)

        emit("phase", {"name": "report"})
        finished_at = time.time()
        report = build_reporter(s, emit).report(repo_url, repo_dir, plan, outcomes,
                                                started_at, finished_at)
        emit("report", report.model_dump())
        store.update_run(run_id, status="completed", finished_at=finished_at,
                         decay_score=report.decay_score, ttfs_seconds=report.ttfs_seconds,
                         pr_url=report.pr_url, summary=report.summary)
    except Exception as e:  # noqa: BLE001 - どこで死んでも部分結果を残す
        emit("error", {"message": str(e)[:1000]})
        store.update_run(run_id, status="failed", finished_at=time.time())
    return store.get_run(run_id)


def main() -> None:
    s = Settings()
    run_id = s.environ.get("DAYONE_RUN_ID")
    repo_url = s.environ.get("DAYONE_REPO_URL")
    if not run_id or not repo_url:
        sys.exit("DAYONE_RUN_ID and DAYONE_REPO_URL are required")

    if s.environ.get("DAYONE_STORE") == "memory":
        from dayone.common.store import MemoryStore

        store = MemoryStore()
        store.create_run(Run(id=run_id, repo_url=repo_url, trigger="manual",
                             status="queued", started_at=time.time()))
    else:
        from dayone.common.store import FirestoreStore

        store = FirestoreStore(s.project_id)
        if store.get_run(run_id) is None:
            store.create_run(Run(id=run_id, repo_url=repo_url, trigger="manual",
                                 status="queued", started_at=time.time()))

    with tempfile.TemporaryDirectory(prefix="dayone-") as tmp:
        run = run_pipeline(repo_url, run_id, store, Path(tmp), s)
    print(f"run {run.id} finished: {run.status} decay={run.decay_score} pr={run.pr_url}")
