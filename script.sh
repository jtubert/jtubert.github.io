#!/bin/sh

# Set your variables
URL="https://docs.google.com/spreadsheets/d/14C-HoYPzEA0CzmX80Lj_6H3qliqbl2NOjAwSuWFejIY/gviz/tq?tqx=out:csv&sheet=Sheet1"
NEW_NAME="stories.csv"
DEST_DIR="/Users/jtubert/Desktop/dev-projects/_personal/jtubert.github.io/_data/"

# Create destination directory if it doesn't exist
#mkdir -p "$DEST_DIR"

# Download the CSV (using curl)
curl -o "/tmp/temp_download.csv" "$URL"

# Rename and move
mv "/tmp/temp_download.csv" "$DEST_DIR/$NEW_NAME"

echo "Downloaded, renamed, and moved to $DEST_DIR/$NEW_NAME"
