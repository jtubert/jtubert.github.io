
mkdir -p resized
for f in assets/*.jpeg; do
  ~/Desktop/ffmpeg -i "$f" -vf "scale=500:-1,crop=500:380:(in_w-out_w)/2:0" "resized/$(basename "$f")"
done

for f in assets/*.png; do
  ~/Desktop/ffmpeg -i "$f" -vf "scale=500:-1,crop=500:380:(in_w-out_w)/2:0" "resized/$(basename "$f")"
done

for f in assets/*.gif; do
  ~/Desktop/ffmpeg -i "$f" -vf "scale=500:-1,crop=500:380:(in_w-out_w)/2:0" "resized/$(basename "$f")"
done
