from pathlib import Path
from typing import Callable

from dayone.common.models import Attempt, Fix, Step
from dayone.rookie.prompts import DIAGNOSE_SYSTEM
from dayone.rookie.sandbox import Sandbox

TEXT_MAX_BYTES = 1_000_000


class RepoTools:
    """診断用の探索ツール。すべて repo_dir 内に制限する"""

    def __init__(self, repo_dir: Path, sandbox: Sandbox, probe_budget: int = 5):
        self.repo_dir = repo_dir.resolve()
        self.sandbox = sandbox
        self.probe_budget = probe_budget

    def _resolve(self, path: str) -> Path | None:
        p = (self.repo_dir / path).resolve()
        if not str(p).startswith(str(self.repo_dir)):
            return None
        return p

    def list_dir(self, path: str = ".") -> str:
        p = self._resolve(path)
        if p is None or not p.is_dir():
            return "outside repository or not a directory"
        entries = sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir()
                         if x.name != ".git")
        return "\n".join(entries[:100]) or "(empty)"

    def read_file(self, path: str, max_chars: int = 8000) -> str:
        p = self._resolve(path)
        if p is None:
            return "outside repository"
        if not p.is_file():
            return "not a file"
        try:
            return p.read_text(errors="replace")[:max_chars]
        except OSError as e:
            return f"read error: {e}"

    def search(self, pattern: str) -> str:
        hits = []
        for p in sorted(self.repo_dir.rglob("*")):
            if not p.is_file() or ".git" in p.parts or p.stat().st_size > TEXT_MAX_BYTES:
                continue
            try:
                text = p.read_text(errors="strict")
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pattern in line:
                    rel = p.relative_to(self.repo_dir)
                    hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                    if len(hits) >= 20:
                        return "\n".join(hits)
        return "\n".join(hits) or "(no match)"

    def run_probe(self, command: str) -> str:
        if self.probe_budget <= 0:
            return "probe budget exceeded"
        self.probe_budget -= 1
        r = self.sandbox.run(command)
        return f"exit_code={r.exit_code}\nstdout: {r.stdout[-2000:]}\nstderr: {r.stderr[-2000:]}"


def _tool_declarations():
    from google.genai import types

    def decl(name, desc, props, required):
        return types.FunctionDeclaration(
            name=name, description=desc,
            parameters=types.Schema(type="OBJECT",
                                    properties={k: types.Schema(type="STRING", description=v)
                                                for k, v in props.items()},
                                    required=required))

    return [
        decl("list_dir", "リポジトリ内のディレクトリの内容を一覧する", {"path": "相対パス（省略時ルート）"}, []),
        decl("read_file", "リポジトリ内のファイルを読む", {"path": "相対パス"}, ["path"]),
        decl("search", "全ファイルからパターンを部分一致検索する", {"pattern": "検索文字列"}, ["pattern"]),
        decl("run_probe", "サンドボックスでコマンドを実行して結果を確認する（高価・最大数回）",
             {"command": "シェルコマンド"}, ["command"]),
    ]


class GeminiDiagnostician:
    def __init__(self, llm, sandbox_factory: Callable[[Path], Sandbox] | None = None):
        self.llm = llm
        self.sandbox_factory = sandbox_factory or (lambda d: Sandbox(cwd=d))

    def diagnose(self, step: Step, attempts: list[Attempt], repo_dir: Path) -> Fix | None:
        tools_impl = RepoTools(repo_dir, self.sandbox_factory(repo_dir))
        dispatch = {"list_dir": lambda a: tools_impl.list_dir(a.get("path", ".")),
                    "read_file": lambda a: tools_impl.read_file(a.get("path", "")),
                    "search": lambda a: tools_impl.search(a.get("pattern", "")),
                    "run_probe": lambda a: tools_impl.run_probe(a.get("command", ""))}

        def on_call(name: str, args: dict) -> str:
            fn = dispatch.get(name)
            return fn(args) if fn else f"unknown tool: {name}"

        attempts_text = "\n".join(
            f"- `{a.command}` → exit {a.result.exit_code}\n  stderr: {a.result.stderr[-2000:]}"
            for a in attempts)
        user = (f"失敗したステップ:\n- 目的: {step.intent}\n- コマンド: `{step.command}`\n"
                f"- 期待: {step.expects}\n\n実行履歴:\n{attempts_text}\n\n"
                "リポジトリを探索して原因を診断し、Fix JSON を出力せよ。")
        try:
            declarations = _tool_declarations()
        except Exception:  # google.genai 不在のテスト環境ではツール宣言なしで続行
            declarations = []
        try:
            text = self.llm.chat_with_tools(DIAGNOSE_SYSTEM, user, declarations, on_call)
            return self._parse_fix(text)
        except Exception:
            return None

    def _parse_fix(self, text: str) -> Fix | None:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return Fix.model_validate_json(text[start:end + 1])
            except Exception:
                pass
        try:
            return self.llm.gen_json(
                f"次のテキストから Fix スキーマの JSON を抽出して返せ:\n{text[:4000]}", Fix)
        except Exception:
            return None
