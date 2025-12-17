#!/bin/bash

# Load environment variables
export $(cat .env | xargs)

echo "Starting local Cloud Functions..."
echo "Upload service: http://localhost:8080"
echo "Analyzer service: http://localhost:8081"
echo ""

# Run both functions in parallel
functions-framework --target=upload_pdf --source=upload_handler/main.py --port=8080 --debug &
PID1=$!

functions-framework --target=analyze_document_http --source=document_analyzer/main.py --port=8081 --debug &
PID2=$!

# Trap Ctrl+C and cleanup
trap "kill $PID1 $PID2; exit" INT

# Wait for both processes
wait $PID1 $PID2
