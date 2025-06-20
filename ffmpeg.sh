#!/bin/bash

# converts mov to mp4
#~/Desktop/ffmpeg -i assets/meataversity.mov -vcodec libx264 -preset fast -crf 23 -acodec aac -b:a 192k meataversity.mp4

# Folder containing videos
VIDEO_DIR="./assets"  # Change this to your folder
OUTPUT_DIR="./assets"  # Where images will be saved
mkdir -p "$OUTPUT_DIR"

# Loop through video files
for video in "$VIDEO_DIR"/*.{mp4,mov,mkv,avi}; do
  [ -e "$video" ] || continue  # Skip if no matching files

  # Get filename without extension
  filename=$(basename "$video")
  name="${filename%.*}"

  # Extract frame at 1 second and save as JPEG
  ~/Desktop/ffmpeg -y -ss 00:00:01.000 -i "$video" -vframes 1 -q:v 2 "$OUTPUT_DIR/${name}.jpg"
done
