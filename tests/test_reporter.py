from dayone.common.llm import FakeLLM
from dayone.common.models import Attempt, ExecResult, Fix, Step, StepOutcome, StepPlan
from dayone.rookie.github_client import GitHubClient
from dayone.rookie.reporter import Reporter


def test_create_doc_pr_calls_github_api():
    calls = []

    class FakeResp:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

        def raise_for_status(self):
            pass

    class FakeHTTP:
        def get(self, url, **kw):
            calls.append(("GET", url))
            return FakeResp({"object": {"sha": "abc"}, "sha": "filesha", "content": ""})

        def post(self, url, **kw):
            calls.append(("POST", url))
            return FakeResp({"html_url": "https://github.com/x/y/pull/1"})

        def put(self, url, **kw):
            calls.append(("PUT", url))
            return FakeResp({})

    gh = GitHubClient(token="t", http=FakeHTTP())
    url = gh.create_doc_pr("x/y", "main", "README.md", "new", "title", "body", "dayone/fix-1")
    assert url.endswith("/pull/1")
    assert ("POST", "https://api.github.com/repos/x/y/pulls") in calls


def make_fixed_outcomes(plan):
    return [StepOutcome(
        step=plan.steps[0], status="fixed",
        attempts=[Attempt(command="npm run setup",
                          result=ExecResult(exit_code=1, stdout="", stderr="", duration_s=1))],
        fix=Fix(category="doc_outdated", working_command="npm run bootstrap",
                explanation="renamed", doc_patch_hint="h"))]


def test_reporter_generates_pr_and_summary(tmp_path):
    (tmp_path / "README.md").write_text("npm run setup")
    plan = StepPlan(doc_path="README.md",
                    steps=[Step(id=1, intent="setup", command="npm run setup", expects="done")])

    class FakeGH:
        def create_doc_pr(self, *a, **kw):
            return "https://github.com/x/y/pull/9"

    llm = FakeLLM(text_responses=["npm run bootstrap", "サマリです。修正PRを出しました。"])
    rep = Reporter(llm, FakeGH(), emit=lambda t, p: None).report(
        "https://github.com/x/y", tmp_path, plan, make_fixed_outcomes(plan), 0.0, 60.0)
    assert rep.pr_url == "https://github.com/x/y/pull/9"
    assert rep.decay_score == 15 and rep.ttfs_seconds == 60.0 and rep.summary


def test_reporter_no_frictions_no_pr(tmp_path):
    (tmp_path / "README.md").write_text("x")
    plan = StepPlan(doc_path="README.md", steps=[Step(id=1, intent="i", command="c", expects="e")])
    outcomes = [StepOutcome(step=plan.steps[0], status="ok")]
    called = []

    class FakeGH:
        def create_doc_pr(self, *a, **kw):
            called.append(1)
            return "u"

    rep = Reporter(FakeLLM(text_responses=["s"]), FakeGH(), emit=lambda t, p: None).report(
        "https://github.com/x/y", tmp_path, plan, outcomes, 0.0, 30.0)
    assert rep.pr_url is None and not called and rep.decay_score == 0


def test_reporter_pr_failure_does_not_crash(tmp_path):
    (tmp_path / "README.md").write_text("npm run setup")
    plan = StepPlan(doc_path="README.md",
                    steps=[Step(id=1, intent="setup", command="npm run setup", expects="done")])

    class BrokenGH:
        def create_doc_pr(self, *a, **kw):
            raise RuntimeError("api down")

    errors = []
    llm = FakeLLM(text_responses=["npm run bootstrap", "サマリ。"])
    rep = Reporter(llm, BrokenGH(), emit=lambda t, p: errors.append(t)).report(
        "https://github.com/x/y", tmp_path, plan, make_fixed_outcomes(plan), 0.0, 60.0)
    assert rep.pr_url is None and "error" in errors
