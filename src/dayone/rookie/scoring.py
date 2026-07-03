from dayone.common.models import Friction, StepOutcome

SEVERITY_POINTS = {"low": 5, "medium": 15, "high": 30}


def frictions_from(outcomes: list[StepOutcome]) -> list[Friction]:
    frictions = []
    for o in outcomes:
        if o.status == "fixed":
            severity = "low" if o.suspicious else "medium"
            frictions.append(Friction(
                step_id=o.step.id, category=o.fix.category, severity=severity,
                doc_line=o.step.source_doc_line, explanation=o.fix.explanation, found_fix=True))
        elif o.status == "failed":
            category = o.fix.category if o.fix else "code_bug"
            explanation = o.fix.explanation if o.fix else "原因を特定できず"
            frictions.append(Friction(
                step_id=o.step.id, category=category, severity="high",
                doc_line=o.step.source_doc_line, explanation=explanation, found_fix=False))
    return frictions


def decay_score(frictions: list[Friction]) -> int:
    return min(100, sum(SEVERITY_POINTS[f.severity] for f in frictions))


def ttfs(outcomes: list[StepOutcome], started_at: float, finished_at: float) -> float | None:
    if outcomes and all(o.status in ("ok", "fixed") for o in outcomes):
        return finished_at - started_at
    return None
