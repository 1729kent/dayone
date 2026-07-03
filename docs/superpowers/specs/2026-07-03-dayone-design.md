# DayOne — 毎日「入社初日」をやり直すAI新人エージェント 設計書

- 日付: 2026-07-03
- 対象: DevOps × AI Agent Hackathon 2026（Findy主催、Google Cloud Japan協賛）提出作品
- 提出締切: 2026-07-10（金）23:59
- ステータス: ユーザー承認済み設計

## 1. コンセプト

README やセットアップ手順は書いた瞬間から腐り始め、気づくのは数ヶ月後に入った新人が半日溶かした時である。DayOne は毎朝「AI の新入社員（ルーキー）」がクリーンなサンドボックスで対象リポジトリにゼロからオンボーディングし、ドキュメント通りに環境構築を実行して、嘘になった手順を検知 → 正しい手順を自力で探索 → ドキュメント修正 PR と摩擦レポートを提出する。ドキュメントを「読む対象」から「毎日テストされる実行可能な成果物」に変える、Docs-as-Code の文字通りの実装。

### 審査基準への対応
| 審査軸 | DayOne の回答 |
|---|---|
| ① エージェントの必然性・自律性 | チャット UI 不要。スケジュール起動で計画→実行→診断→修復→検証→報告を全自律実行 |
| ② 課題ストーリー | 課題=ドキュメント腐敗、ユーザー=オンボーディングに苦しむ開発チーム、価値=新人の半日を守る |
| ③ ユーザビリティ | ダッシュボードで実行がライブで見え、成果は普段の GitHub フロー（PR）に返る |
| ④ 実用性・体験価値 | 「新人が毎日入社する」メタファー。腐敗スコア・time-to-first-success の定量効果 |
| ⑤ 実装力・実運用配慮 | 最小権限サンドボックス、HITL、CI/CD、エージェント回帰テスト、コスト設計 |

## 2. ゴール / 非ゴール

### ゴール
- 7/9 までに Cloud Run 上で審査員が実際に触って動く公開デモを完成させる
- セットアップ系ドキュメント（README / CONTRIBUTING / docs/setup 等）の検証に対応
- 腐敗検知 → 自己修復探索 → ドキュメント修正 PR の全自律ループを 3 種の腐敗パターンで確実に成功させる
- 独自定量指標: ドキュメント腐敗スコア（0-100）、time-to-first-success（TTFS）

### 非ゴール（スコープ外）
- API リファレンス等、セットアップ以外のドキュメント検証
- アプリコード自体の修正 PR（修正はドキュメントのみ。コード起因と判断した場合は Issue 起票に留める）
- プライベートレジストリ・認証付き依存の解決
- ユーザーアカウント / マルチテナント（公開デモはレート制限付きトリガーで対応）
- 任意の巨大リポジトリ対応（デモは軽量リポジトリ 2 個。設計は汎用に保つ）

## 3. アーキテクチャ

```
Cloud Scheduler（毎朝 07:00 JST の定期入社）
        │ HTTP (OIDC)
        ▼
┌─ dayone-app（Cloud Run サービス・公開 URL）───────┐
│ FastAPI + 軽量フロント（SSE ライブトレース）        │
│ - ダッシュボード: 実行履歴・腐敗スコア推移・         │──▶ Firestore
│   摩擦レポート・ライブトレース                      │   (runs / steps /
│ - POST /runs: ルーキー入社トリガー（レート制限付き）  │    frictions / metrics)
│ - Cloud Run Jobs API で dayone-rookie を起動        │
└──────────────┬─────────────────────┘
               │ Jobs API (run execution)
               ▼
┌─ dayone-rookie（Cloud Run Jobs・使い捨てサンドボックス）─┐
│ ADK Python 2.x エージェント一式（コンテナ内で完結）      │
│ ① Planner: ドキュメント → ステップ計画(構造化 JSON)     │──▶ Vertex AI
│ ② Executor: 1 ステップずつシェル実行・出力観察          │   Gemini 3.5 Flash
│ ③ Diagnostician: 失敗を3分類 → リポジトリ探索 →         │   (要約系は
│    修正候補発見 → 再実行で検証                          │    3.1 Flash-lite)
│ ④ Reporter: 腐敗スコア算出・摩擦レポート・               │
│    ドキュメント修正 PR 生成                             │──▶ GitHub API
│ 進捗イベントを Firestore へ逐次書き込み                  │   (fine-grained PAT)
└─────────────────────────────────────┘
```

### 設計判断
- **エージェントは Job コンテナ内で完結**（オーケストレータからのリモートシェル操作はしない）。1 回の入社 = 1 Job 実行。堅牢でデバッグしやすく、失敗の爆発半径がコンテナ 1 個に閉じる。
- **ライブ感の実現**: rookie が Firestore に進捗イベントを逐次書き込み、dayone-app が SSE でダッシュボードへ中継する。ポーリング間隔 1 秒。
- **公開デモの保護**: POST /runs はグローバルで 5 分に 1 回のクールダウン（Firestore のロックドキュメントで実装）。超過時は直近の実行履歴の閲覧へ誘導。

## 4. コンポーネント設計

### 4.1 dayone-rookie（エージェント本体）
ADK Python の SequentialAgent をルートに、以下のサブエージェント／ツールで構成する。

- **Planner**: 対象リポジトリを clone し、README 等のセットアップ文書を Gemini で「実行可能ステッププラン」に変換。各ステップは `{id, intent, command, expects, source_doc_line}` の構造化 JSON。
- **Executor**: ステップを順に実行するループ。シェル実行ツール（timeout 120s/step、環境変数スクラブ済み）で実行し、exit code と stdout/stderr を観察。成功判定は exit code + Gemini による出力解釈の二段構え。
- **Diagnostician**: 失敗時に起動。失敗を 3 分類する — (a) ドキュメントが古い（改名・移動・手順欠落）、(b) 前提の記載漏れ（必要ツール・環境変数）、(c) 本物のバグ。リポジトリ探索ツール（ls / cat / grep / package.json・pyproject.toml 解析）で正しい手順の仮説を立て、**再実行で検証してから**確定する。修復上限: 1 ステップにつき 3 仮説まで。
- **Reporter**: 実行結果から摩擦ポイント一覧・腐敗スコア・TTFS を算出。「ドキュメントの記載 vs 実際に動いた手順」の差分からドキュメント修正 diff を生成し、GitHub に PR を作成（(c) 分類は Issue 起票のみ）。

**暴走封じ込め**: 総ステップ予算 30、修復試行込みのアクション上限 60、Job 全体タイムアウト 10 分、同一コマンド 3 回で ループ検知打ち切り。打ち切り時も部分レポートを必ず出す。

### 4.2 dayone-app（ダッシュボード + API）
- FastAPI。エンドポイント: `GET /`（ダッシュボード）、`GET /runs/{id}`（実行詳細・ライブトレース）、`POST /runs`（トリガー、クールダウン付き）、`GET /api/runs/{id}/events`（SSE）、`POST /internal/scheduled`（Scheduler 用、OIDC 検証）。
- フロントは素の HTML/CSS/JS（ビルドレス）。画面: 実行一覧 + 腐敗スコア推移グラフ、実行詳細（ステップのタイムライン、思考ログの吹き出し、摩擦レポート、PR リンク）、「今日のルーキーを入社させる」ボタン。

### 4.3 データモデル（Firestore）
- `runs/{runId}`: {repo, trigger(manual|scheduled), status, started_at, finished_at, decay_score, ttfs_seconds, pr_url, summary}
- `runs/{runId}/events/{seq}`: {ts, type(plan|exec|diagnose|fix|report|think), payload} — ライブトレースの実体
- `frictions/{id}`: {run_id, step_id, category(a|b|c), doc_line, found_fix, severity}
- `repos/{repoId}`: {url, decay_history[], last_success_ttfs}

### 4.4 デモリポジトリ（2 個・公開）
1. **dayone-demo-node**: Express の小さな Web アプリ。腐敗注入: `npm run setup` → `npm run bootstrap` への改名、`.env.example` のキー名変更。
2. **dayone-demo-py**: FastAPI の小さなアプリ（uv 管理）。腐敗注入: 手順欠落（DB マイグレーション記載漏れ）、必要ツールの記載漏れ。

腐敗は `inject-rot.sh` / `heal.sh` スクリプトで注入・修復でき、デモを何度でもリセット可能にする。依存は軽量に保ち、rookie のベースイメージに node/uv を焼き込んで 1 実行 3 分以内に収める。

## 5. セキュリティ設計（審査⑤の見せ場）
- rookie の SA は最小権限: Vertex AI 呼び出し + 自分の Firestore コレクション書き込みのみ。**本番資格情報・他リソースへのアクセスはゼロ**
- 実行するシェルコマンドには**スクラブ済み環境変数**のみを渡す（GitHub PAT や API キーは子プロセスに露出しない）
- GitHub PAT は fine-grained・デモリポジトリ 2 個限定・contents/pull-requests 権限のみ。Secret Manager で管理
- PR マージは人間が行う HITL 設計（判断と実行は AI、意思決定は人間）

## 6. エラー処理
- Gemini 呼び出し: 指数バックオフ + リトライ 3 回。提出前に課金 Tier 1 へ引き上げ、審査中の 429 を排除
- ステップ実行: per-step timeout 120s、Job 全体 10 分
- どの段階で失敗しても「ここまでの摩擦レポート」を Firestore に書き、ダッシュボードに部分結果を表示（全損なし）
- Job 起動失敗・二重起動: クールダウンロック + runId の冪等キーで防止

## 7. テスト戦略
- 単体テスト: Planner の構造化出力パース、腐敗スコア算出、環境変数スクラブ、クールダウンロック
- E2E 回帰: 腐敗シナリオ 3 種 × デモリポジトリで「検知 → 修復 → PR 生成」まで到達することを検証するシナリオテスト。**GitHub Actions で毎日実行**（エージェント品質の継続検証＝「まわす」のアピール材料）
- デモ前リハーサル: 全シナリオを 7/9 に通しで実行し成功率を記録

## 8. CI/CD（テーマ「まわす」）
- GitHub Actions: push → lint/test → dayone-app と dayone-rookie のイメージビルド → Artifact Registry → Cloud Run / Jobs へ自動デプロイ
- 認証は Workload Identity Federation（キーレス）
- E2E 回帰のスケジュール実行ジョブ

## 9. 提出物計画
- GitHub 公開リポジトリ: モノレポ（app / rookie / demo-repos は別リポ 2 個 + 本体 1 個）、README にアーキ図・セキュリティ設計・定量効果
- デプロイ URL: dayone-app の公開 URL
- ProtoPedia: 動画（YouTube）、アーキテクチャ図（必須）、ストーリー 3 項目（課題と背景 / 想定ユーザー / 特徴）、タグ `findy_hackathon`
- 90 秒デモ動画の絵コンテ: ①腐った README のデモリポジトリを表示 → ②「今日のルーキーを入社させる」ボタン → ③ライブトレース（README 読解 → 12 ステップ計画 → `npm run setup` 失敗 → package.json 調査 → 改名スクリプト発見 → 成功）→ ④摩擦 3 件・腐敗スコア 62/100・修正 PR 表示 → ⑤マージ後再実行で全ステップ緑、TTFS 18 分 → 4 分のグラフで締め
- **7/9 に早期提出 → 7/10 に改善再提出**（再提出可ルールを活用）

## 10. リスクと対策
| リスク | 対策 |
|---|---|
| 実行エンジンの頑健化に工数超過 | デモリポジトリを軽量に固定し、シナリオ 3 種の成功に全振り。汎用性は「設計上の拡張性」として README で語る |
| デモが間延び（重いインストール） | ベースイメージにランタイム焼き込み、1 実行 3 分以内 |
| LLM 判断のブレでデモ失敗 | シナリオ固定 + E2E 回帰を毎日回す。動画は成功テイクを収録 |
| 審査中の 429 | 課金 Tier 1 + バックオフ |
| 「自作自演デモ」批判 | 腐敗注入スクリプトを公開し透明性を確保。実在 OSS リポジトリでの実行例を 1 本添える（時間があれば） |

## 11. スケジュール
| 日 | マイルストーン |
|---|---|
| 7/3(木)-4(金) | 骨格生成・GCP セットアップ・初回デプロイで URL 確保・サンドボックス Job 疎通 |
| 7/5(土) | Planner + Executor 完成 |
| 7/6(日) | Diagnostician（診断→自己修復ループ）完成 |
| 7/7(月) | Reporter（PR 生成・腐敗スコア）+ デモリポジトリ 2 個整備 |
| 7/8(火) | ダッシュボード UI・CI/CD 完成 |
| 7/9(水) | E2E リハーサル・動画・アーキ図・ProtoPedia 登録・早期提出 |
| 7/10(木) | バッファ + 改善再提出、Google Form 最終応募 |
