"""デモ動画の素材をPlaywrightで自動収録する。

使い方: uv run python scripts/record_demo.py docs/submission/assets/raw-demo
出力: raw-demo/ 配下に .webm（1280x800）

前提:
- デモリポジトリが腐敗状態（inject-rot.sh 適用済み・push済み）
- DayOne 製のオープンPRがないこと（重複防止でPR作成がスキップされるため）
- 直近5分以内にトリガーしていないこと（クールダウン）
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "https://dayone-app-d2fceukfiq-an.a.run.app"


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "raw-demo")
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(out_dir),
            record_video_size={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        # シーン1: ダッシュボードを開く（3秒）
        page.goto(APP, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # シーン2: ルーキー入社ボタンを押す
        page.click("#hireBtn")
        page.wait_for_timeout(1500)

        # シーン3: 業務日誌がライブで流れる（完了まで最大120秒監視）
        deadline = time.time() + 120
        while time.time() < deadline:
            chip = page.text_content("#stChip") or ""
            if "完了" in chip or "失敗" in chip:
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(4000)

        # シーン4: 摩擦レポートにスクロール（4秒）
        page.evaluate("document.querySelector('#frictionBox')?.scrollIntoView({behavior:'smooth'})")
        page.wait_for_timeout(4000)

        # シーン5: 修正PRページへ（あれば・6秒）
        pr = page.get_attribute("#prLink", "href")
        if pr:
            page.goto(pr, wait_until="networkidle")
            page.wait_for_timeout(4000)
            page.goto(pr + "/files", wait_until="networkidle")
            page.wait_for_timeout(4000)

        ctx.close()
        browser.close()
    print(f"video saved under: {out_dir}/")


if __name__ == "__main__":
    main()
