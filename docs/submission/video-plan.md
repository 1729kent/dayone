# デモ動画プラン（90秒・YouTube用）

## 絵コンテ

| 秒 | シーン | 見せるもの | テロップ案 |
|---|---|---|---|
| 0-8 | 課題提起 | 腐ったREADME（`npm run setup`）と実際の`package.json`（bootstrapしかない） | 「READMEは、書いた瞬間から腐り始める」 |
| 8-15 | タイトル | ダッシュボードのヒーロー画面 | 「DayOne — 毎日が、入社初日。」 |
| 15-22 | トリガー | 「🌅 今日のルーキーを入社させる」クリック | 「AIの新入社員が、毎朝あなたのリポジトリに入社する」 |
| 22-55 | 自律ループ（山場） | 業務日誌ライブ: 計画→npm install→setup失敗→🔍調査→🔧bootstrap発見→✅ | 「読解 → 実務 → 診断 → 自己修復。すべて自律判断」 |
| 55-70 | 成果 | 腐敗スコア15・TTFS 26秒・摩擦テーブル → 修正PRのdiff画面 | 「嘘になった手順は、根拠つきの修正PRに」「マージ判断は人間（HITL）」 |
| 70-82 | まわす | GitHub Actions緑・Cloud Scheduler・スコア推移グラフ | 「毎朝の回帰がエージェント自身の品質を検証し続ける」 |
| 82-90 | 締め | ロゴ＋URL | 「ドキュメントを、毎日テストされる成果物へ。DayOne」 |

## 撮影手順（半自動）

1. **準備**（毎テイク前）
   ```bash
   # デモリポジトリを腐敗状態に戻す（PRマージ済みの場合）
   cd /Users/kent/Uto/hackthon-demos/dayone-demo-node && ./inject-rot.sh && git commit -am "rot" && git push
   # オープン中のDayOne製PRを閉じる（重複防止機能でPR作成がスキップされるため）
   gh pr list --repo 1729kent/dayone-demo-node
   # 前回トリガーから5分待つ（クールダウン）
   ```
2. **本編素材の自動収録**（22-70秒のシーンが1本のwebmになる）
   ```bash
   uv run python scripts/record_demo.py docs/submission/assets/raw-demo
   ```
3. **静止画素材**: `docs/submission/assets/` の dashboard.png / architecture.png / pr-diff.png
4. **編集**: iMovie / CapCut で絵コンテ通りにカット＋テロップ。長い待ち（exec中）は2倍速に
5. **書き出し**: 1080p、90秒以内 → YouTube に「限定公開」でアップ → URLをProtoPediaへ

## ナレーション不要（テロップのみで成立する構成）。BGMはYouTubeオーディオライブラリのlo-fi推奨
