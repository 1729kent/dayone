"""Google Cloud Text-to-Speech で日本語ナレーション音声を生成する。

各シーンのテキストを個別のMP3として出力。Cloud TTS（ハッカソンのスポンサー技術）を使用。
使い方: uv run --with google-cloud-texttospeech python scripts/gen_narration.py <out_dir>
"""
import sys
from pathlib import Path

from google.cloud import texttospeech

VOICE = "ja-JP-Neural2-B"  # 落ち着いた女性ナレーション
RATE = 1.06

# (id, テキスト) — シーン順。id はビルドスクリプトの scene 名と対応
LINES = [
    ("s1", "READMEやセットアップ手順は、書いた瞬間から腐り始める。気づくのは、新人が半日を溶かした時です。"),
    ("s2", "DayOne。毎日が、入社初日。"),
    ("s3", "AIの新入社員が、毎朝あなたのリポジトリに入社します。指示は、ボタンひとつ。"),
    ("s4", "READMEを読んで計画を立て、手順どおりに実行。setupコマンドが失敗しても、"
           "自分でパッケージ設定を調べ、正しいbootstrapコマンドを見つけて、もう一度試します。"),
    ("s5", "見つけた摩擦は、腐敗スコアとして数値化。そして、根拠つきの修正プルリクエストを自動で作成します。"
           "マージするかどうかを決めるのは、人間です。"),
    ("s6", "人間がマージすると、翌朝のルーキーが回復を確認し、スコアはゼロに戻ります。"
           "chalkやFastAPIといった実在のオープンソースでも、誤検知はありませんでした。"),
    ("s7", "つくって、まわして、とどける。毎朝の自動実行とCIの回帰テストが、エージェント自身の品質も検証し続けます。"),
    ("s8", "ドキュメントを、毎日テストされる成果物へ。DayOne。"),
]


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    client = texttospeech.TextToSpeechClient()
    voice = texttospeech.VoiceSelectionParams(language_code="ja-JP", name=VOICE)
    audio_cfg = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=RATE)
    for sid, text in LINES:
        resp = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text), voice=voice, audio_config=audio_cfg)
        (out / f"{sid}.mp3").write_bytes(resp.audio_content)
        print(f"{sid}.mp3  ({len(resp.audio_content)} bytes)  {text[:30]}…")


if __name__ == "__main__":
    main()
