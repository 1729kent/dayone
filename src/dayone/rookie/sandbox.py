import os
import signal
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
        limit = timeout_s or self.timeout_s
        # start_new_session でプロセスグループを分離し、タイムアウト時は killpg で
        # 孫・バックグラウンドプロセスまで確実に殺す（shell のみ kill だと残存する）
        proc = subprocess.Popen(command, shell=True, cwd=self.cwd, env=scrub_env(dict(os.environ)),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=limit)
            return ExecResult(exit_code=proc.returncode, stdout=stdout[-20000:], stderr=stderr[-20000:],
                              duration_s=time.monotonic() - t0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                stdout, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout = ""
            return ExecResult(exit_code=124, stdout=(stdout or "")[-20000:],
                              stderr=f"timed out after {limit}s (ネットワーク断とは限らない。"
                                     "大きな依存のインストール等で単に時間切れの可能性が高い)",
                              duration_s=time.monotonic() - t0, timed_out=True)
