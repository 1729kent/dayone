from dayone.common.config import Settings


def test_settings_defaults():
    s = Settings(environ={})
    assert s.region == "asia-northeast1"
    assert s.model == "gemini-3.5-flash"
    assert s.create_pr is True


def test_settings_env_override():
    s = Settings(environ={"DAYONE_PROJECT_ID": "p1", "DAYONE_CREATE_PR": "0"})
    assert s.project_id == "p1"
    assert s.create_pr is False
