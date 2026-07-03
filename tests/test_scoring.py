from dayone.common.models import Attempt, ExecResult, Fix, Friction, Step, StepOutcome
from dayone.rookie.scoring import decay_score, frictions_from, ttfs


def step(i):
    return Step(id=i, intent="x", command=f"c{i}", expects="e")


def att(code):
    return [Attempt(command="c", result=ExecResult(exit_code=code, stdout="", stderr="", duration_s=1))]


FIX = Fix(category="doc_outdated", working_command="c2", explanation="", doc_patch_hint="h")


def test_frictions_mapping():
    outcomes = [
        StepOutcome(step=step(1), status="ok", attempts=att(0)),
        StepOutcome(step=step(2), status="fixed", attempts=att(1), fix=FIX),
        StepOutcome(step=step(3), status="failed", attempts=att(1)),
        StepOutcome(step=step(4), status="skipped"),
    ]
    fr = frictions_from(outcomes)
    assert [(f.step_id, f.severity, f.found_fix) for f in fr] == [(2, "medium", True), (3, "high", False)]
    assert fr[1].category == "code_bug"


def test_frictions_suspicious_low():
    outcomes = [StepOutcome(step=step(1), status="fixed", attempts=att(0), fix=FIX, suspicious=True)]
    assert frictions_from(outcomes)[0].severity == "low"


def test_decay_score_caps():
    fr = [Friction(step_id=i, category="doc_outdated", severity="high", doc_line=None,
                   explanation="", found_fix=False) for i in range(5)]
    assert decay_score(fr) == 100
    assert decay_score([]) == 0


def test_ttfs():
    ok_all = [StepOutcome(step=step(1), status="ok"),
              StepOutcome(step=step(2), status="fixed", fix=FIX)]
    assert ttfs(ok_all, 100.0, 250.0) == 150.0
    with_fail = ok_all + [StepOutcome(step=step(3), status="failed")]
    assert ttfs(with_fail, 100.0, 250.0) is None
