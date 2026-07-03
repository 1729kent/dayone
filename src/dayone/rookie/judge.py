from dayone.common.models import ExecResult, Step

KEYWORDS = ("error", "fatal", "traceback", "enoent", "not found")


class OutputJudge:
    """exit 0 でも出力が失敗を示唆していないかの二段判定。llm 省略時はキーワードのみ"""

    def __init__(self, llm=None):
        self.llm = llm

    def suspicious(self, step: Step, result: ExecResult) -> bool:
        text = (result.stdout + "\n" + result.stderr).lower()
        hit = any(k in text for k in KEYWORDS)
        if not hit:
            return False
        if self.llm is None:
            return True
        verdict = self.llm.gen_text(
            f"コマンド `{step.command}`（目的: {step.intent}）の出力:\n"
            f"---\n{(result.stdout + result.stderr)[-2000:]}\n---\n"
            "このコマンドは目的を達成できたか? yes/no のみで答えて")
        return verdict.strip().lower().startswith("no")
