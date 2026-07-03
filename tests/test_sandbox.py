from pathlib import Path

from dayone.rookie.sandbox import Sandbox, scrub_env


def test_scrub_removes_secrets():
    env = {"PATH": "/bin", "HOME": "/h", "GITHUB_TOKEN": "x", "DAYONE_GITHUB_TOKEN": "x",
           "GOOGLE_APPLICATION_CREDENTIALS": "x", "MY_API_KEY": "x", "AWS_SECRET_TOKEN": "x",
           "LANG": "C", "NODE_ENV": "dev"}
    out = scrub_env(env)
    assert set(out) == {"PATH", "HOME", "LANG", "NODE_ENV"}


def test_run_captures_output(tmp_path: Path):
    r = Sandbox(cwd=tmp_path).run("echo hello && echo bad >&2 && exit 3")
    assert r.exit_code == 3 and "hello" in r.stdout and "bad" in r.stderr


def test_run_timeout(tmp_path: Path):
    r = Sandbox(cwd=tmp_path).run("sleep 5", timeout_s=1)
    assert r.timed_out and r.exit_code != 0


def test_child_env_is_scrubbed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    r = Sandbox(cwd=tmp_path).run("printenv GITHUB_TOKEN || echo EMPTY")
    assert "secret" not in r.stdout and "EMPTY" in r.stdout
