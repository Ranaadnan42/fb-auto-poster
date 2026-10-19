#!/bin/bash
# Dry run video ka preview (frames ki sheet + chhoti mp4) "previews" branch par - check karne ke liye
set -e
V="$1"; NAME="$2"
[ -f "$V" ] || exit 0
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")
mkdir -p /tmp/pv && rm -f /tmp/pv/*
for i in $(seq 1 16); do
  T=$(python3 -c "print(round($D*($i-0.5)/16,2))")
  ffmpeg -loglevel error -y -ss "$T" -i "$V" -frames:v 1 -vf "scale=480:-2" "/tmp/pv/f$(printf %02d $i).jpg"
done
ffmpeg -loglevel error -y -pattern_type glob -i '/tmp/pv/f*.jpg' -vf "tile=4x4" -frames:v 1 "/tmp/pv/${NAME}_sheet.jpg"
ffmpeg -loglevel error -y -i "$V" -vf "scale=-2:480" -c:v libx264 -crf 32 -preset veryfast -c:a aac -b:a 64k -fs 45M "/tmp/pv/${NAME}_preview.mp4"
cd /tmp && rm -rf pvrepo && git clone -q --depth 1 --branch previews "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" pvrepo 2>/dev/null || {
  mkdir pvrepo && cd pvrepo && git init -q && git checkout -q -b previews && git remote add origin "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"; cd /tmp; }
cd /tmp/pvrepo
cp "/tmp/pv/${NAME}_sheet.jpg" "/tmp/pv/${NAME}_preview.mp4" .
# Kaggle ke AI clips + log (jaanch ke liye)
if [ -d "$GITHUB_WORKSPACE/work_cine/kclips" ]; then
  mkdir -p kclips && rm -f kclips/*
  cp "$GITHUB_WORKSPACE"/work_cine/kclips/*.mp4 "$GITHUB_WORKSPACE"/work_cine/kclips/*.log kclips/ 2>/dev/null || true
fi
git config user.name "auto-poster"; git config user.email "auto-poster@users.noreply.github.com"
git add -A && git commit -q -m "preview $NAME" && git push -q -f origin previews
