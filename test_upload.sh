#!/bin/bash

# Test script for uploading a PDF locally

if [ -z "$1" ]; then
    echo "Usage: ./test_upload.sh <path-to-pdf>"
    exit 1
fi

PDF_FILE=$1

if [ ! -f "$PDF_FILE" ]; then
    echo "Error: File not found: $PDF_FILE"
    exit 1
fi

echo "Uploading $PDF_FILE to local server..."
echo ""

RESPONSE=$(curl -X POST \
  -F "file=@$PDF_FILE" \
  http://localhost:8080 \
  -s)

echo "$RESPONSE" | python3 -m json.tool

# Extract jobId and trigger analysis
JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('jobId', ''))")

if [ -n "$JOB_ID" ]; then
    echo ""
    echo "Job ID: $JOB_ID"
    echo ""
    echo "Triggering analysis..."
    curl -X POST \
      -H "Content-Type: application/json" \
      -d "{\"jobId\": \"$JOB_ID\"}" \
      http://localhost:8081/analyze \
      -s | python3 -m json.tool
fi
