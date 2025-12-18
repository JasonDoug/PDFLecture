#!/bin/bash

# Audio Intelligence Suite Launcher
# Starts the Portal, Frontends, AND Local Backends for the Monorepo

echo "🚀 Starting Audio Intelligence Suite (Monorepo)..."

# Load Environment Variables
if [ -f .env ]; then
    export $(cat .env | xargs)
    echo "🔑 Environment variables loaded."
else
    echo "⚠️  No .env file found. Backend services may fail."
fi

# Ensure venv is available
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "⚠️  Virtual environment not found. Ensure dependencies are installed."
fi

# 1. Start PDF Processor (Backend) - Port 9200
echo "Starting PDF Processor Backend on http://localhost:9200..."
functions-framework --target=extract_pdf --source=services/pdf-processor/main.py --port=9200 --debug >> suite_debug.log 2>&1 &
PID_BACK1=$!

# 2. Start TTS Service (Backend) - Port 9202
echo "Starting TTS Backend on http://localhost:9202..."
functions-framework --target=synthesize_text --source=services/tts-service/main.py --port=9202 --debug >> suite_debug.log 2>&1 &
PID_BACK2=$!

# 3. Start Lecture Frontend - Port 8085
echo "Starting Lecture Client on http://localhost:8085..."
(cd apps/lecture && python3 -m http.server 8085 >> ../../suite_debug.log 2>&1) &
PID_FRONT1=$!

# 4. Start Audiobook Frontend - Port 5173
echo "Starting Audiobook Client on http://localhost:5173..."
if [ -d "apps/audiobook" ]; then
    (cd apps/audiobook && npm run dev >> ../../suite_debug.log 2>&1) &
    PID_FRONT2=$!
else
    echo "⚠️  Audiobook directory not found at apps/audiobook" | tee -a suite_debug.log
fi

# 5. Start Portal - Port 3000
echo "Starting Portal on http://localhost:3000..."
(cd apps/portal && python3 -m http.server 3000 >> ../../suite_debug.log 2>&1) &
PID_PORTAL=$!

# Cleanup function
cleanup() {
    echo "Shutting down all services..."
    kill $PID_BACK1 $PID_BACK2 $PID_FRONT1 $PID_FRONT2 $PID_PORTAL 2>/dev/null
    exit
}

trap cleanup INT

echo ""
echo "✅ Suite Active!"
echo "------------------------------------------------"
echo "🌐 MAIN PORTAL:  http://localhost:3000"
echo "------------------------------------------------"
echo "🎓 Lecture App:  http://localhost:8085"
echo "🎧 Audiobook:    http://localhost:5173"
echo "   ↳ Backend:    http://localhost:9200, 9202"
echo "------------------------------------------------"
echo "Press Ctrl+C to stop all services."

# Wait for Portal as keep-alive
wait $PID_PORTAL
