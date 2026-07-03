from dayone.common.models import ExecResult, Fix, Run, Step, StepOutcome, StepPlan


def test_step_plan_roundtrip():
    plan = StepPlan(doc_path="README.md", steps=[
        Step(id=1, intent="install", command="npm install", expects="deps installed"),
    ])
    again = StepPlan.model_validate_json(plan.model_dump_json())
    assert again.steps[0].command == "npm install"
    assert again.steps[0].source_doc_line is None


def test_outcome_defaults():
    o = StepOutcome(step=Step(id=1, intent="i", command="c", expects="e"), status="ok")
    assert o.attempts == [] and o.fix is None and o.suspicious is False


def test_fix_literal():
    f = Fix(category="doc_outdated", working_command=None, explanation="x", doc_patch_hint="h")
    assert f.category == "doc_outdated"


def test_run_defaults():
    r = Run(id="r", repo_url="u", trigger="manual", status="queued", started_at=1.0)
    assert r.finished_at is None and r.decay_score is None and r.summary == ""


def test_exec_result():
    e = ExecResult(exit_code=0, stdout="s", stderr="", duration_s=0.5)
    assert e.timed_out is False
