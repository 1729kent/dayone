import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    environ: dict = field(default_factory=lambda: dict(os.environ))

    def _get(self, key: str, default: str = "") -> str:
        return self.environ.get(f"DAYONE_{key}", default)

    @property
    def project_id(self) -> str:
        return self._get("PROJECT_ID")

    @property
    def region(self) -> str:
        return self._get("REGION", "asia-northeast1")

    @property
    def genai_location(self) -> str:
        return self._get("GENAI_LOCATION", "global")

    @property
    def model(self) -> str:
        return self._get("MODEL", "gemini-3.5-flash")

    @property
    def model_lite(self) -> str:
        return self._get("MODEL_LITE", "gemini-3.1-flash-lite")

    @property
    def github_token(self) -> str:
        return self._get("GITHUB_TOKEN")

    @property
    def job_name(self) -> str:
        return self._get("JOB_NAME", "dayone-rookie")

    @property
    def sched_token(self) -> str:
        return self._get("SCHED_TOKEN")

    @property
    def extra_allowed_repos(self) -> str:
        return self._get("EXTRA_ALLOWED_REPOS")

    @property
    def create_pr(self) -> bool:
        return self._get("CREATE_PR", "1") not in ("0", "false", "")


settings = Settings()
