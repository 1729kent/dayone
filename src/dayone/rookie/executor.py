from pathlib import Path
from typing import Callable, Protocol

from dayone.common.models import Attempt, Fix, Step, StepOutcome, StepPlan

EmitFn = Callable[[str, dict], None]


class Diagnostician(Protocol):
    def diagnose(self, step: Step, attempts: list[Attempt], repo_dir: Path) -> Fix | None: ...


class Budget:
    def __init__(self, max_steps: int = 30, max_actions: int = 60):
        self.max_steps = max_steps
        self.actions = max_actions

    def spend_action(self) -> bool:
        if self.actions <= 0:
            return False
        self.actions -= 1
        return True


class Executor:
    def __init__(self, sandbox, judge, diagnostician, emit: EmitFn, budget: Budget | None = None):
        self.sandbox = sandbox
        self.judge = judge
        self.diag = diagnostician
        self.emit = emit
        self.budget = budget or Budget()

    def run(self, plan: StepPlan, repo_dir: Path) -> list[StepOutcome]:
        outcomes: list[StepOutcome] = []
        cmd_counts: dict[str, int] = {}
        consecutive_failures = 0
        aborted = False

        def execute(cmd: str):
            cmd_counts[cmd] = cmd_counts.get(cmd, 0) + 1
            return self.sandbox.run(cmd)

        for step in plan.steps[: self.budget.max_steps]:
            if aborted or consecutive_failures >= 2 or not self.budget.spend_action():
                outcomes.append(StepOutcome(step=step, status="skipped"))
                continue
            if cmd_counts.get(step.command, 0) >= 3:
                aborted = True
                outcomes.append(StepOutcome(step=step, status="skipped"))
                continue
            self.emit("exec", {"step_id": step.id, "command": step.command, "intent": step.intent})
            result = execute(step.command)
            attempts = [Attempt(command=step.command, result=result)]
            suspicious = result.exit_code == 0 and self.judge.suspicious(step, result)
            if result.exit_code == 0 and not suspicious:
                consecutive_failures = 0
                outcomes.append(StepOutcome(step=step, status="ok", attempts=attempts))
                continue
            self.emit("diagnose", {"step_id": step.id, "stderr": result.stderr[-500:]})
            fix = self.diag.diagnose(step, attempts, repo_dir)
            fixed = False
            if fix and fix.working_command and self.budget.spend_action():
                if cmd_counts.get(fix.working_command, 0) >= 2:
                    aborted = True  # 既に2回試したコマンドの再提案 = ループ
                else:
                    verify = execute(fix.working_command)
                    attempts.append(Attempt(command=fix.working_command, result=verify))
                    fixed = verify.exit_code == 0
            if aborted:
                outcomes.append(StepOutcome(step=step, status="skipped", attempts=attempts,
                                            fix=fix, suspicious=suspicious))
            elif fixed:
                consecutive_failures = 0
                self.emit("fix", {"step_id": step.id, "working_command": fix.working_command,
                                  "category": fix.category})
                outcomes.append(StepOutcome(step=step, status="fixed", attempts=attempts,
                                            fix=fix, suspicious=suspicious))
            else:
                consecutive_failures += 1
                outcomes.append(StepOutcome(step=step, status="failed", attempts=attempts,
                                            fix=fix, suspicious=suspicious))
        return outcomes
