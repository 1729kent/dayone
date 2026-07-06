import json

from dayone.common.models import Attempt, ExecResult, Step
from dayone.rookie.diagnostician import GeminiDiagnostician, RepoTools
from dayone.rookie.sandbox import Sandbox


def test_repotools_confined(tmp_path):
    (tmp_path / "a.txt").write_text("hello npm run bootstrap world")
    t = RepoTools(tmp_path, Sandbox(cwd=tmp_path))
    assert "a.txt" in t.list_dir(".")
    assert "bootstrap" in t.read_file("a.txt")
    assert "a.txt" in t.search("bootstrap")
    assert "outside" in t.read_file("../../etc/passwd")


def test_repotools_sibling_prefix_blocked(tmp_path):
    """/x/repo に対して /x/repo2 のような prefix が一致する sibling を repo 内と誤判定しないこと"""
    repo = tmp_path / "repo"
    repo.mkdir()
    sibling = tmp_path / "repo2"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("leak")
    t = RepoTools(repo, Sandbox(cwd=repo))
    assert "outside" in t.read_file("../repo2/secret.txt")
    assert "leak" not in t.read_file("../repo2/secret.txt")


def test_probe_budget(tmp_path):
    t = RepoTools(tmp_path, Sandbox(cwd=tmp_path), probe_budget=1)
    assert "exit_code=0" in t.run_probe("true")
    assert "budget" in t.run_probe("true")


class ToolUsingFakeLLM:
    """search を1回呼んでから Fix JSON を返す台本"""

    def chat_with_tools(self, system, user, tools, on_call):
        on_call("search", {"pattern": "bootstrap"})
        return json.dumps({"category": "doc_outdated", "working_command": "npm run bootstrap",
                           "explanation": "script renamed", "doc_patch_hint": "setup->bootstrap"})


def make_step():
    return Step(id=1, intent="setup", command="npm run setup", expects="done")


def make_attempts():
    return [Attempt(command="npm run setup",
                    result=ExecResult(exit_code=1, stdout="", stderr="missing script: setup",
                                      duration_s=0.1))]


def test_diagnose_returns_fix(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"bootstrap": "true"}}')
    d = GeminiDiagnostician(ToolUsingFakeLLM())
    fix = d.diagnose(make_step(), make_attempts(), tmp_path)
    assert fix.category == "doc_outdated" and fix.working_command == "npm run bootstrap"


class GarbageLLM:
    def chat_with_tools(self, system, user, tools, on_call):
        return "no json here"

    def gen_json(self, prompt, schema, system=None):
        raise RuntimeError("nope")


def test_diagnose_garbage_returns_none(tmp_path):
    d = GeminiDiagnostician(GarbageLLM())
    fix = d.diagnose(make_step(), make_attempts(), tmp_path)
    assert fix is None
