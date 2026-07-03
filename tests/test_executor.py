from pathlib import Path

from dayone.common.models import ExecResult, Fix, Step, StepPlan
from dayone.rookie.executor import Budget, Executor
from dayone.rookie.judge import OutputJudge


def ok():
    return ExecResult(exit_code=0, stdout="", stderr="", duration_s=0.1)


def ng():
    return ExecResult(exit_code=1, stdout="", stderr="boom", duration_s=0.1)


class ScriptedSandbox:
    """コマンド→結果列の台本。列が尽きたら最後の結果を返し続ける"""

    def __init__(self, script: dict[str, list[ExecResult]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []

    def run(self, command, timeout_s=None):
        self.calls.append(command)
        seq = self.script.get(command, [ng()])
        return seq.pop(0) if len(seq) > 1 else seq[0]


class NoFix:
    def diagnose(self, step, attempts, repo_dir):
        return None


class FixWith:
    def __init__(self, cmd):
        self.cmd = cmd

    def diagnose(self, step, attempts, repo_dir):
        return Fix(category="doc_outdated", working_command=self.cmd,
                   explanation="renamed", doc_patch_hint="setup->bootstrap")


def plan(*cmds):
    return StepPlan(doc_path="README.md", steps=[
        Step(id=i + 1, intent=f"s{i}", command=c, expects="ok") for i, c in enumerate(cmds)])


def run_exec(sandbox, diag, p, budget=None):
    events = []
    ex = Executor(sandbox, OutputJudge(), diag, emit=lambda t, pl: events.append(t), budget=budget)
    return ex.run(p, Path(".")), events


def test_all_ok():
    outcomes, _ = run_exec(ScriptedSandbox({"a": [ok()], "b": [ok()]}), NoFix(), plan("a", "b"))
    assert [o.status for o in outcomes] == ["ok", "ok"]


def test_fix_verified_marks_fixed():
    sb = ScriptedSandbox({"npm run setup": [ng()], "npm run bootstrap": [ok()]})
    outcomes, _ = run_exec(sb, FixWith("npm run bootstrap"), plan("npm run setup"))
    assert outcomes[0].status == "fixed"
    assert outcomes[0].fix.working_command == "npm run bootstrap"
    assert len(outcomes[0].attempts) == 2


def test_two_consecutive_failures_skip_rest():
    sb = ScriptedSandbox({"a": [ng()], "b": [ng()], "c": [ok()]})
    outcomes, _ = run_exec(sb, NoFix(), plan("a", "b", "c"))
    assert [o.status for o in outcomes] == ["failed", "failed", "skipped"]


def test_loop_detection_aborts():
    sb = ScriptedSandbox({"x": [ng(), ng(), ng(), ng()]})
    outcomes, _ = run_exec(sb, FixWith("x"), plan("x", "y"))  # 修復案も同じ x → ループ
    assert outcomes[-1].status == "skipped"
    assert sb.calls.count("x") <= 3


def test_action_budget():
    sb = ScriptedSandbox({f"c{i}": [ok()] for i in range(10)})
    outcomes, _ = run_exec(sb, NoFix(), plan(*[f"c{i}" for i in range(10)]),
                           budget=Budget(max_actions=5))
    assert sum(1 for o in outcomes if o.status == "ok") == 5
    assert all(o.status == "skipped" for o in outcomes[5:])


def test_judge_suspicious_triggers_diagnose():
    sus = ExecResult(exit_code=0, stdout="", stderr="Error: ENOENT missing file", duration_s=0.1)
    sb = ScriptedSandbox({"a": [sus], "a2": [ok()]})
    outcomes, _ = run_exec(sb, FixWith("a2"), plan("a"))
    assert outcomes[0].status == "fixed" and outcomes[0].suspicious is True
