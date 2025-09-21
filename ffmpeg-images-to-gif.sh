#!/bin/bash

# Script to convert images in a folder to an animated GIF with fade transitions using ffmpeg
# Usage: ./images_to_gif.sh <input_folder> [output_file] [fps] [duration] [fade_duration]

# Check if ffmpeg is installed
if ! command -v ~/Desktop/ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed. Please install it first."
    echo "Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo "macOS: brew install ffmpeg"
    exit 1
fi

# Check if input folder is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <input_folder> [output_file] [fps] [duration] [fade_duration]"
    echo "  input_folder: Folder containing images"
    echo "  output_file: Output GIF filename (default: output.gif)"
    echo "  fps: Frames per second (default: 10)"
    echo "  duration: Duration each image is shown in seconds (default: 2)"
    echo "  fade_duration: Fade transition duration in seconds (default: 0.5)"
    exit 1
fi

INPUT_FOLDER="$1"
OUTPUT_FILE="${2:-output.gif}"
FPS="${3:-10}"
DURATION="${4:-2}"
FADE_DURATION="${5:-0.5}"

# Check if input folder exists
if [ ! -d "$INPUT_FOLDER" ]; then
    echo "Error: Folder '$INPUT_FOLDER' does not exist"
    exit 1
fi

# Find all image files (jpg, jpeg, png)
IMAGE_FILES=$(find "$INPUT_FOLDER" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) | sort)

# Check if any images were found
if [ -z "$IMAGE_FILES" ]; then
    echo "Error: No image files found in '$INPUT_FOLDER'"
    exit 1
fi

# Count images
IMAGE_COUNT=$(echo "$IMAGE_FILES" | wc -l)
echo "Found $IMAGE_COUNT image(s) in '$INPUT_FOLDER'"

# Create a temporary directory for renamed files
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Copy and rename images with sequential numbers
echo "Preparing images..."
COUNTER=1
while IFS= read -r img; do
    EXT="${img##*.}"
    printf -v PADDED "%05d" $COUNTER
    cp "$img" "$TEMP_DIR/${PADDED}.${EXT}"
    COUNTER=$((COUNTER + 1))
done <<< "$IMAGE_FILES"

# Get the file extension of the first image
FIRST_IMG=$(ls "$TEMP_DIR" | head -n 1)
PATTERN="${FIRST_IMG%.*}"
EXT="${FIRST_IMG##*.}"

# Convert images to GIF using ffmpeg with resize, crop, and fade transitions
echo "Resizing and cropping images to 640x480, adding fade transitions, then creating animated GIF at $FPS fps..."

# Build input files list
INPUT_LIST=""
FILTER_COMPLEX=""
LAST_OUTPUT="[0:v]"

# Calculate offset for xfade (when to start the fade)
OFFSET=$(awk "BEGIN {print $DURATION - $FADE_DURATION}")

COUNTER=0
while IFS= read -r img; do
    INPUT_LIST="$INPUT_LIST -loop 1 -t $DURATION -i $img"
    
    if [ $COUNTER -eq 0 ]; then
        FILTER_COMPLEX="[0:v]scale=640:480:force_original_aspect_ratio=increase,crop=640:480,setsar=1[v0];"
    else
        FILTER_COMPLEX="${FILTER_COMPLEX}[${COUNTER}:v]scale=640:480:force_original_aspect_ratio=increase,crop=640:480,setsar=1[v${COUNTER}];"
    fi
    
    COUNTER=$((COUNTER + 1))
done < <(find "$TEMP_DIR" -type f -name "*.${EXT}" | sort)

# Build xfade transitions
for ((i=0; i<COUNTER-1; i++)); do
    NEXT=$((i + 1))
    if [ $i -eq 0 ]; then
        FILTER_COMPLEX="${FILTER_COMPLEX}[v0][v1]xfade=transition=fade:duration=${FADE_DURATION}:offset=${OFFSET}[f0];"
    else
        PREV=$((i - 1))
        FILTER_COMPLEX="${FILTER_COMPLEX}[f${PREV}][v${NEXT}]xfade=transition=fade:duration=${FADE_DURATION}:offset=$(awk "BEGIN {print $OFFSET + $i * $DURATION - $i * $FADE_DURATION}")[f${i}];"
    fi
done

# Final output from last fade
LAST_FADE=$((COUNTER - 2))
if [ $COUNTER -eq 1 ]; then
    FINAL_OUTPUT="[v0]"
else
    FINAL_OUTPUT="[f${LAST_FADE}]"
fi

# Add palette generation for GIF
FILTER_COMPLEX="${FILTER_COMPLEX}${FINAL_OUTPUT}split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"

# Run ffmpeg with the complete filter
~/Desktop/ffmpeg $INPUT_LIST -filter_complex "$FILTER_COMPLEX" -loop 0 -r $FPS "$OUTPUT_FILE" -y 2>/dev/null

# Check if conversion was successful
if [ $? -eq 0 ]; then
    echo "Success! Created '$OUTPUT_FILE'"
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "File size: $FILE_SIZE"
else
    echo "Error: Failed to create GIF"
    exit 1
fi