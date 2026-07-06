#!/usr/bin/env bash
# ナレーション音声に合わせて最終デモ動画を組み立てる。
# 使い方: bash scripts/build_final_video.sh <narration_dir> <out.mp4>
set -euo pipefail
A="/Users/kent/Uto/hackthon/docs/submission/assets"
NAR="${1:?narration_dir}"
OUT="${2:?out.mp4}"
RAW="$A/raw-final/page@76159e7962a3fe7ec7e766be2e9a87f4.webm"
B="$NAR/build"; rm -rf "$B"; mkdir -p "$B"
LEAD=0.3; TAIL=0.7

dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

# scene <name> <img|clip> <src> <clip_start> <clip_end> <narration.mp3>
scene() {
  local name="$1" typ="$2" src="$3" cs="$4" ce="$5" nar="$6"
  local nd td; nd=$(dur "$nar"); td=$(python3 -c "print(round($nd+$LEAD+$TAIL,3))")
  if [ "$typ" = img ]; then
    ffmpeg -y -loglevel error -loop 1 -i "$src" -t "$td" \
      -vf "scale=1280:800:force_original_aspect_ratio=decrease,pad=1280:800:(ow-iw)/2:(oh-ih)/2:0x0a0e18,fps=30" \
      -pix_fmt yuv420p "$B/v_$name.mp4"
  else
    local span factor; span=$(python3 -c "print($ce-$cs)"); factor=$(python3 -c "print(round($td/$span,4))")
    ffmpeg -y -loglevel error -ss "$cs" -to "$ce" -i "$src" \
      -vf "setpts=$factor*PTS,scale=1280:800,fps=30" -an -t "$td" -pix_fmt yuv420p "$B/v_$name.mp4"
  fi
  # 音声: LEAD秒の無音→ナレーション→末尾はtd秒までパディング
  ffmpeg -y -loglevel error -i "$nar" \
    -af "adelay=$(python3 -c "print(int($LEAD*1000))")|$(python3 -c "print(int($LEAD*1000))"),apad" \
    -t "$td" -ar 48000 -ac 2 "$B/a_$name.mp3"
  ffmpeg -y -loglevel error -i "$B/v_$name.mp4" -i "$B/a_$name.mp3" \
    -c:v copy -c:a aac -shortest "$B/$name.mp4"
  echo "$name: video=$td s (nar=$nd s)"
}

scene s1 img  "$A/cards/card1.png"  0 0 "$NAR/s1.mp3"
scene s2 img  "$A/cards/card2.png"  0 0 "$NAR/s2.mp3"
scene s3 clip "$RAW" 1.0 8.5   "$NAR/s3.mp3"
scene s4 clip "$RAW" 8.5 46.0  "$NAR/s4.mp3"
scene s5 clip "$RAW" 46.0 78.0 "$NAR/s5.mp3"
scene s6 img  "$A/cards/card5.png"  0 0 "$NAR/s6.mp3"
scene s7 img  "$A/cards/card3.png"  0 0 "$NAR/s7.mp3"
scene s8 img  "$A/cards/card4.png"  0 0 "$NAR/s8.mp3"

printf "file '%s.mp4'\n" s1 s2 s3 s4 s5 s6 s7 s8 > "$B/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$B/list.txt" -c:v libx264 -c:a aac -movflags +faststart "$OUT"
echo "OUT: $OUT ($(dur "$OUT")s)"
