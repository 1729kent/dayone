import base64

API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str, http=None):
        if http is None:
            import httpx

            http = httpx.Client(headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }, timeout=30)
        self.http = http

    def find_open_dayone_pr(self, repo_full: str) -> str | None:
        """既にオープンな DayOne 製 PR があればその URL を返す（重複 PR の防止）"""
        r = self.http.get(f"{API}/repos/{repo_full}/pulls", params={"state": "open", "per_page": 50})
        r.raise_for_status()
        for pr in r.json():
            if (pr.get("head") or {}).get("ref", "").startswith("dayone/"):
                return pr["html_url"]
        return None

    def create_doc_pr(self, repo_full: str, base: str, file_path: str,
                      new_content: str, title: str, body: str, branch: str) -> str:
        r = self.http.get(f"{API}/repos/{repo_full}/git/ref/heads/{base}")
        r.raise_for_status()
        base_sha = r.json()["object"]["sha"]

        r = self.http.post(f"{API}/repos/{repo_full}/git/refs",
                           json={"ref": f"refs/heads/{branch}", "sha": base_sha})
        r.raise_for_status()

        r = self.http.get(f"{API}/repos/{repo_full}/contents/{file_path}", params={"ref": base})
        r.raise_for_status()
        file_sha = r.json()["sha"]

        r = self.http.put(f"{API}/repos/{repo_full}/contents/{file_path}", json={
            "message": title,
            "content": base64.b64encode(new_content.encode()).decode(),
            "sha": file_sha,
            "branch": branch,
        })
        r.raise_for_status()

        r = self.http.post(f"{API}/repos/{repo_full}/pulls",
                           json={"title": title, "body": body, "head": branch, "base": base})
        r.raise_for_status()
        return r.json()["html_url"]
