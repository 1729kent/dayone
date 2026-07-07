#!/usr/bin/env bash
# 実在OSS群でDayOneを実行し、検知精度の実データを集める。
# 自己完結型(外部DB/creds不要)の軽量リポジトリを厳選。結果はFirestore→ダッシュボードにも残る。
set -euo pipefail
REGION=asia-northeast1; PROJECT=dayone-hack-2026
TS=$(date +%m%d%H%M)

# owner/repo|ラベル（クイックスタートが install→import/run で完結する純ライブラリ/軽量FW）
REPOS=(
  "sindresorhus/slugify|node-slugify"
  "tj/commander.js|node-commander"
  "chalk/chalk|node-chalk"
  "expressjs/express|node-express"
  "pallets/click|py-click"
  "psf/requests|py-requests"
  "python-attrs/attrs|py-attrs"
  "pallets/flask|py-flask"
)

for entry in "${REPOS[@]}"; do
  full="${entry%%|*}"; label="${entry##*|}"
  rid="val-${label}-${TS}"
  echo "=== $full → run $rid ==="
  gcloud run jobs execute dayone-rookie --region "$REGION" --project "$PROJECT" \
    --update-env-vars "DAYONE_RUN_ID=$rid,DAYONE_REPO_URL=https://github.com/$full,DAYONE_CREATE_PR=0" \
    --wait 2>&1 | tail -1
done
echo "ALL DONE ($TS)"
