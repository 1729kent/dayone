"""ダッシュボードや任意HTMLのスクリーンショットを撮る。

使い方:
  uv run python scripts/screenshot.py <url_or_file> <out.png> [width] [height] [wait_ms]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    target, out = sys.argv[1], sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 900
    wait_ms = int(sys.argv[5]) if len(sys.argv) > 5 else 2500
    if not target.startswith("http"):
        target = "file://" + str(Path(target).resolve())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
        page.goto(target, wait_until="networkidle")
        page.wait_for_timeout(wait_ms)
        page.screenshot(path=out, full_page=False)
        browser.close()
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
