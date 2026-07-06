#!/usr/bin/env bash
# Google Cloud Text-to-Speech (REST) で日本語ナレーションを生成する。
# 使い方: bash scripts/gen_narration.sh <out_dir>
set -euo pipefail
OUT="${1:?out_dir required}"
mkdir -p "$OUT"
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
VOICE="ja-JP-Neural2-B"
RATE=1.06

synth() {
  local id="$1" text="$2"
  curl -s -X POST "https://texttospeech.googleapis.com/v1/text:synthesize" \
    -H "Authorization: Bearer $TOKEN" \
    -H "x-goog-user-project: $PROJECT" \
    -H "Content-Type: application/json" \
    -d "{\"input\":{\"text\":\"$text\"},\"voice\":{\"languageCode\":\"ja-JP\",\"name\":\"$VOICE\"},\"audioConfig\":{\"audioEncoding\":\"MP3\",\"speakingRate\":$RATE}}" \
    | python3 -c "import json,sys,base64; open('$OUT/$id.mp3','wb').write(base64.b64decode(json.load(sys.stdin)['audioContent']))"
  echo "$id.mp3 : $(printf '%s' "$text" | cut -c1-30)…"
}

synth s1 "READMEやセットアップ手順は、書いた瞬間から腐り始める。気づくのは、新人が半日を溶かした時です。"
synth s2 "DayOne。毎日が、入社初日。"
synth s3 "AIの新入社員が、毎朝あなたのリポジトリに入社します。指示は、ボタンひとつ。"
synth s4 "READMEを読んで計画を立て、手順どおりに実行。setupコマンドが失敗しても、自分でパッケージ設定を調べ、正しいbootstrapコマンドを見つけて、もう一度試します。"
synth s5 "見つけた摩擦は、腐敗スコアとして数値化。そして、根拠つきの修正プルリクエストを自動で作成します。マージするかどうかを決めるのは、人間です。"
synth s6 "人間がマージすると、翌朝のルーキーが回復を確認し、スコアはゼロに戻ります。chalkやFastAPIといった実在のオープンソースでも、誤検知はありませんでした。"
synth s7 "つくって、まわして、とどける。毎朝の自動実行とCIの回帰テストが、エージェント自身の品質も検証し続けます。"
synth s8 "ドキュメントを、毎日テストされる成果物へ。DayOne。"
echo "done: $OUT"
