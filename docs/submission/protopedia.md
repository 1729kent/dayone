# ProtoPedia 登録用文面（コピペ用）

✅ **登録完了済み（2026-07-03）**: https://protopedia.net/prototype/8711
✅ 動画: https://www.youtube.com/watch?v=jgMJn3lnd2s
残り: Google Form での最終応募（7/10 23:59 まで、再提出可）。

---

## 作品タイトル（必須）

```
DayOne — 毎日が、入社初日。AIルーキーがドキュメントの腐敗を検知して直す
```

## 作品ステータス（必須）

`完成品` を選択（動作するデプロイ済みURLあり）

## 概要（必須）

```
READMEやセットアップ手順は書いた瞬間から腐り始め、気づくのは新人が半日を溶かした時。
DayOneは「AIの新入社員」が毎朝あなたのリポジトリにゼロからオンボーディングし、
ドキュメント通りに実行→嘘になった手順を検知→自力で正しい手順を探索→修正PRを提出する
自律エージェントです。ドキュメントを「毎日テストされる実行可能な成果物」に変えます。

▶ 動作デモ: https://dayone-app-d2fceukfiq-an.a.run.app
▶ GitHub: https://github.com/1729kent/dayone
```

## 動画（必須）

YouTube に90秒デモをアップして URL を貼る（video-plan.md 参照）

## システム構成（必須）

アーキテクチャ図: `docs/submission/assets/architecture.png` をアップロード

技術補足テキスト:

```
・Cloud Run: FastAPIダッシュボード「業務日誌」（SSEでエージェントの思考をライブ中継）
・Cloud Run Jobs: 1回の入社=1つの使い捨てサンドボックス。最小権限SA・環境変数スクラブ・
　実行予算とタイムアウトで封じ込め（本番資格情報ゼロ）
・Vertex AI Gemini (gemini-3.5-flash / 3.1-flash-lite): 計画立案・失敗診断・修復探索・報告生成
・Firestore: 実行イベントストリームと腐敗スコア履歴
・Cloud Scheduler: 毎朝07:00の完全自律実行（チャットUI不要）
・GitHub Actions + Workload Identity Federation: push→テスト→ビルド→自動デプロイ（キーレス）、
　さらに毎朝のE2E回帰で「エージェント自身の品質」を継続検証
```

## 開発素材（必須）

```
Google Cloud Run / Cloud Run Jobs / Vertex AI (Gemini API) / Cloud Firestore /
Cloud Scheduler / Secret Manager / Artifact Registry / GitHub Actions /
Python 3.12 / FastAPI / uv / Docker / Playwright / Claude Code（AI駆動開発）
```

## タグ（必須）

```
findy_hackathon, AIエージェント, Gemini, CloudRun, DevOps, ドキュメント, 自己修復
```

※ `findy_hackathon` は必須タグ

## ストーリー（必須・3項目）

### ① 解決したい課題とその背景

```
READMEやセットアップ手順は、書いた瞬間から腐り始めます。スクリプトの改名、環境変数の変更、
暗黙の前提——変更のたびにドキュメントは現実からズレていき、それに気づくのは数ヶ月後に
入った新人が半日を溶かした時です。コードにはCIがあり壊れれば即座に検知されるのに、
ドキュメントには「実行して検証する仕組み」が存在しない。既存のドキュメントツールも
生成・検索止まりで、「書かれた手順が今日も本当に動くか」は誰も保証してくれません。
オンボーディングの失敗はチームの生産性と新人の心理的安全性を同時に削る、
DevOpsの死角でした。
```

### ② 想定する利用ユーザー

```
・オンボーディングのたびに「READMEが古い」問題を踏む開発チーム
・コントリビュータの初回体験がプロジェクトの生命線であるOSSメンテナ
・ドキュメント整備に人手を割けない小規模チーム／スタートアップ
使い方は「リポジトリURLを渡すだけ」。あとは毎朝勝手に検証が回り、
成果は普段のGitHubフロー（PR）に返ってくるので、新しいツールの学習コストがありません。
```

### ③ プロダクトの特徴

```
【エージェントの必然性】チャットUIすらありません。Cloud Schedulerが毎朝「AIルーキー」を
出社させ、読解（README→実行計画）→実務（1ステップずつ実行）→診断（失敗を3分類）→
自己修復（リポジトリを探索し動く手順を発見、再実行で検証）→日報（腐敗スコア・修正PR）
まで全て自律判断で回します。人間の仕事はPRのマージ判断だけ（Human-in-the-Loop）。

【独自の定量指標】ドキュメント腐敗スコア(0-100)と Time to First Success（環境構築成功までの
実測秒数）を毎日計測し、ダッシュボードで推移を可視化。実測でTTFS 28秒
（腐敗診断・自己修復込み）を達成。

【実運用への配慮】任意コマンドを実行するため封じ込めを最優先に設計：使い捨てサンドボックス、
最小権限SA（本番資格情報ゼロ）、環境変数スクラブ、実行予算・タイムアウト・ループ検知、
重複PR防止。CI/CD（WIFキーレス）に加え、毎朝のE2E回帰が「エージェント自身の品質」を
継続検証します——「つくる・まわす・とどける」を作品自体が毎日体現しています。
```

## 画像（任意・最大5枚）

1. `assets/dashboard.png` — 業務日誌ダッシュボード（ライブトレース）
2. `assets/architecture.png` — システム構成図
3. `assets/pr-diff.png` — 自動生成された修正PRのdiff
4. （動画撮影時に追加: 入社ボタンを押した直後のライブ画面）

## 関連URL（任意）

```
https://dayone-app-d2fceukfiq-an.a.run.app （動作デモ）
https://github.com/1729kent/dayone （本体リポジトリ）
https://github.com/1729kent/dayone-demo-node （デモ用リポジトリ・腐敗注入済み）
https://github.com/1729kent/dayone-demo-py （デモ用リポジトリ・前提記載漏れ）
```

---

## 提出チェックリスト（公式ルール準拠）

- [ ] ProtoPedia アカウント作成
- [ ] 上記フィールドをすべて入力（タグ `findy_hackathon` 忘れずに）
- [ ] デモ動画を YouTube に「限定公開」以上でアップし URL 記入
- [ ] アーキテクチャ図アップロード
- [ ] **Google Form（作品提出フォーム）から最終応募** ← これで正式エントリー完了
  - GitHub リポジトリURL: https://github.com/1729kent/dayone
  - デプロイURL: https://dayone-app-d2fceukfiq-an.a.run.app
  - ProtoPedia URL: （登録後に記入）
- [ ] Findy Conference 申込フォームからのエントリーが完了しているか再確認（7/10締切・本名漢字）
