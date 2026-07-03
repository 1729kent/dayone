import pytest

from dayone.common.llm import FakeLLM
from dayone.common.models import Step, StepPlan
from dayone.rookie.planner import Planner, find_setup_doc


def repo(tmp_path, files: dict[str, str]):
    for name, body in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return tmp_path


def test_find_doc_priority(tmp_path):
    d = repo(tmp_path, {"CONTRIBUTING.md": "c", "README.md": "r"})
    assert find_setup_doc(d).name == "README.md"


def test_find_doc_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_setup_doc(tmp_path)


def test_plan_normalizes_ids(tmp_path):
    d = repo(tmp_path, {"README.md": "# setup\nnpm install\nnpm run setup"})
    fake_plan = StepPlan(doc_path="README.md", steps=[
        Step(id=7, intent="install deps", command="npm install", expects="node_modules created"),
        Step(id=9, intent="run setup", command="npm run setup", expects="setup done"),
    ])
    p = Planner(FakeLLM(json_responses=[fake_plan])).plan(d)
    assert [s.id for s in p.steps] == [1, 2]
    assert p.doc_path == "README.md"
