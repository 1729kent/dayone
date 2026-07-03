from pathlib import Path

from dayone.common.models import StepPlan
from dayone.rookie.prompts import PLANNER_SYSTEM, PLANNER_USER

DOC_CANDIDATES = ["README.md", "CONTRIBUTING.md", "docs/setup.md", "docs/SETUP.md", "SETUP.md"]


def find_setup_doc(repo_dir: Path) -> Path:
    for c in DOC_CANDIDATES:
        p = repo_dir / c
        if p.is_file():
            return p
    raise FileNotFoundError(f"no setup doc in {repo_dir}")


class Planner:
    def __init__(self, llm):
        self.llm = llm

    def plan(self, repo_dir: Path) -> StepPlan:
        doc = find_setup_doc(repo_dir)
        lines = doc.read_text(errors="replace").splitlines()
        numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))[:15000]
        rel = str(doc.relative_to(repo_dir))
        plan = self.llm.gen_json(
            PLANNER_USER.format(doc_path=rel, doc_body=numbered),
            StepPlan, system=PLANNER_SYSTEM)
        steps = [s.model_copy(update={"id": i + 1}) for i, s in enumerate(plan.steps)]
        return StepPlan(doc_path=rel, steps=steps)
