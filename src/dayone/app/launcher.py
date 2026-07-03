from typing import Protocol


class JobLauncher(Protocol):
    def launch(self, run_id: str, repo_url: str) -> None: ...


class CloudRunJobLauncher:
    def __init__(self, project_id: str, region: str, job_name: str):
        from google.cloud import run_v2

        self.client = run_v2.JobsClient()
        self.name = f"projects/{project_id}/locations/{region}/jobs/{job_name}"

    def launch(self, run_id: str, repo_url: str) -> None:
        from google.cloud import run_v2

        override = run_v2.RunJobRequest.Overrides.ContainerOverride(env=[
            {"name": "DAYONE_RUN_ID", "value": run_id},
            {"name": "DAYONE_REPO_URL", "value": repo_url},
        ])
        req = run_v2.RunJobRequest(
            name=self.name,
            overrides=run_v2.RunJobRequest.Overrides(container_overrides=[override]))
        self.client.run_job(request=req)  # LRO は待たない（Job は非同期に走る）
