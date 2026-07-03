from pathlib import Path

from dayone.common.models import StepPlan
from dayone.rookie.prompts import PLANNER_SYSTEM, PLANNER_USER

DOC_CANDIDATES = ["readme.md", "contributing.md", "docs/setup.md", "setup.md"]


def find_setup_doc(repo_dir: Path) -> Path:
    """候補名に大文字小文字を無視してマッチ（実OSSは readme.md / Readme.md 等が普通にある）"""
    for c in DOC_CANDIDATES:
        parent = repo_dir / Path(c).parent
        if not parent.is_dir():
            continue
        for p in sorted(parent.iterdir()):
            if p.is_file() and p.name.lower() == Path(c).name:
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
