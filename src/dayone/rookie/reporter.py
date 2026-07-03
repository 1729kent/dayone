from pathlib import Path
from typing import Callable

from dayone.common.models import RunReport, StepOutcome, StepPlan
from dayone.rookie.prompts import DOC_PATCH_SYSTEM, SUMMARY_SYSTEM
from dayone.rookie.scoring import decay_score, frictions_from, ttfs

EmitFn = Callable[[str, dict], None]

SEVERITY_JA = {"low": "低", "medium": "中", "high": "高"}
CATEGORY_JA = {"doc_outdated": "ドキュメント腐敗", "missing_prereq": "前提の記載漏れ", "code_bug": "コード起因"}


def repo_full_from_url(repo_url: str) -> str:
    return "/".join(repo_url.rstrip("/").removesuffix(".git").split("/")[-2:])


class Reporter:
    def __init__(self, llm, github, emit: EmitFn, create_pr: bool = True):
        self.llm = llm
        self.github = github
        self.emit = emit
        self.create_pr = create_pr

    def report(self, repo_url: str, repo_dir: Path, plan: StepPlan,
               outcomes: list[StepOutcome], started_at: float, finished_at: float) -> RunReport:
        frictions = frictions_from(outcomes)
        score = decay_score(frictions)
        ttfs_s = ttfs(outcomes, started_at, finished_at)
        pr_url = None

        fixable = [o for o in outcomes if o.status == "fixed" and o.fix and o.fix.working_command]
        if fixable and self.create_pr and self.github is not None:
            pr_url = self._try_doc_pr(repo_url, repo_dir, plan, fixable, finished_at)

        summary = self.llm.gen_text(
            "今日のオンボーディング結果:\n"
            f"- 腐敗スコア: {score}/100\n"
            f"- 摩擦: {[f.explanation for f in frictions]}\n"
            f"- 修正PR: {pr_url or 'なし'}",
            system=SUMMARY_SYSTEM)
        return RunReport(frictions=frictions, decay_score=score, ttfs_seconds=ttfs_s,
                         pr_url=pr_url, summary=summary)

    def _try_doc_pr(self, repo_url: str, repo_dir: Path, plan: StepPlan,
                    fixable: list[StepOutcome], finished_at: float) -> str | None:
        try:
            doc_file = repo_dir / plan.doc_path
            original = doc_file.read_text(errors="replace")
            mapping = "\n".join(
                f"- `{o.step.command}` → `{o.fix.working_command}`"
                f"（{CATEGORY_JA.get(o.fix.category, o.fix.category)}: {o.fix.doc_patch_hint}）"
                for o in fixable)
            new_content = self.llm.gen_text(
                f"元のドキュメント({plan.doc_path}):\n---\n{original[:15000]}\n---\n"
                f"実際に動いた手順への対応表:\n{mapping}\n---\n修正後の全文を出力せよ。",
                system=DOC_PATCH_SYSTEM)
            if not new_content.strip() or new_content.strip() == original.strip():
                return None
            if original.endswith("\n") and not new_content.endswith("\n"):
                new_content += "\n"
            body_lines = ["DayOne が本日のオンボーディングで検知した摩擦:", ""]
            body_lines += [f"- Step {o.step.id}: `{o.step.command}` → `{o.fix.working_command}`"
                           f"（{o.fix.explanation}）" for o in fixable]
            body_lines += ["", "🤖 このPRは AI 新人エージェント DayOne が自動生成しました。マージ判断は人間が行ってください。"]
            pr_url = self.github.create_doc_pr(
                repo_full=repo_full_from_url(repo_url), base="main", file_path=plan.doc_path,
                new_content=new_content, title="docs: DayOneが検知したセットアップ手順の腐敗を修正",
                body="\n".join(body_lines), branch=f"dayone/fix-{int(finished_at)}")
            self.emit("pr", {"url": pr_url})
            return pr_url
        except Exception as e:  # noqa: BLE001 - PR失敗はレポート全体を壊さない
            self.emit("error", {"where": "create_pr", "message": str(e)[:500]})
            return None
