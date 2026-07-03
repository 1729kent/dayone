from typing import Literal

from pydantic import BaseModel, Field


class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False


class Step(BaseModel):
    id: int
    intent: str
    command: str
    expects: str
    source_doc_line: int | None = None


class StepPlan(BaseModel):
    doc_path: str
    steps: list[Step]


class Attempt(BaseModel):
    command: str
    result: ExecResult


class Fix(BaseModel):
    category: Literal["doc_outdated", "missing_prereq", "code_bug"]
    working_command: str | None
    explanation: str
    doc_patch_hint: str


class StepOutcome(BaseModel):
    step: Step
    status: Literal["ok", "fixed", "failed", "skipped"]
    attempts: list[Attempt] = Field(default_factory=list)
    fix: Fix | None = None
    suspicious: bool = False


class Friction(BaseModel):
    step_id: int
    category: str
    severity: Literal["low", "medium", "high"]
    doc_line: int | None
    explanation: str
    found_fix: bool


class RunReport(BaseModel):
    frictions: list[Friction]
    decay_score: int
    ttfs_seconds: float | None
    pr_url: str | None
    summary: str


class Run(BaseModel):
    id: str
    repo_url: str
    trigger: Literal["manual", "scheduled"]
    status: Literal["queued", "running", "completed", "failed"]
    started_at: float
    finished_at: float | None = None
    decay_score: int | None = None
    ttfs_seconds: float | None = None
    pr_url: str | None = None
    summary: str = ""


class Event(BaseModel):
    seq: int
    ts: float
    type: str
    payload: dict
