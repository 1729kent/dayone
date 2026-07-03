import os
import subprocess
import time
from pathlib import Path

from dayone.common.models import ExecResult

ALLOWED = {"PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "USER", "SHELL",
           "NODE_ENV", "PYTHONUNBUFFERED", "npm_config_cache", "UV_CACHE_DIR"}
DENY_SUBSTR = ("TOKEN", "KEY", "SECRET", "CREDENTIAL", "PASSWORD")


def scrub_env(base: dict[str, str]) -> dict[str, str]:
    out = {}
    for k, v in base.items():
        if k not in ALLOWED:
            continue
        if any(s in k.upper() for s in DENY_SUBSTR):
            continue
        out[k] = v
    return out


class Sandbox:
    def __init__(self, cwd: Path, timeout_s: int = 300):
        self.cwd = cwd
        self.timeout_s = timeout_s

    def run(self, command: str, timeout_s: int | None = None) -> ExecResult:
        t0 = time.monotonic()
        try:
            p = subprocess.run(command, shell=True, cwd=self.cwd, env=scrub_env(dict(os.environ)),
                               capture_output=True, text=True, timeout=timeout_s or self.timeout_s)
            return ExecResult(exit_code=p.returncode, stdout=p.stdout[-20000:], stderr=p.stderr[-20000:],
                              duration_s=time.monotonic() - t0)
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else ""
            limit = timeout_s or self.timeout_s
            return ExecResult(exit_code=124, stdout=(out or "")[-20000:],
                              stderr=f"timed out after {limit}s (ネットワーク断とは限らない。"
                                     "大きな依存のインストール等で単に時間切れの可能性が高い)",
                              duration_s=time.monotonic() - t0, timed_out=True)
