#!/bin/bash

# Assistant Script for Hosting Deployment

echo "🚀 preparing Audio Intelligence Suite for Hosting..."

# Check for firebase-tools
if ! command -v firebase &> /dev/null; then
    echo "❌ Firebase CLI not found."
    echo "Please install it: npm install -g firebase-tools"
    echo "Then log in: firebase login"
    exit 1
fi

echo "--- Configuration Setup ---"
echo "We need the Production URLs from your backend services."
echo "If you haven't deployed them yet, run ./deploy_services.sh first."
echo ""

read -p "Enter PDF Processor URL (e.g., https://...extract_pdf): " PDF_URL
read -p "Enter TTS Service URL (e.g., https://...synthesize_text): " TTS_URL

if [ -z "$PDF_URL" ] || [ -z "$TTS_URL" ]; then
    echo "❌ URLs cannot be empty."
    exit 1
fi

# Basic URL Sanitization/Validation
if [[ ! "$PDF_URL" =~ ^https?:// ]] || [[ ! "$TTS_URL" =~ ^https?:// ]]; then
    echo "❌ URLs must start with http:// or https://"
    exit 1
fi

echo ""
echo "📝 Generating Production Config..."

# Create .env.production for Audiobook App
cat > apps/audiobook/.env.production <<EOF
VITE_API_PDF_URL=$PDF_URL
VITE_API_TTS_URL=$TTS_URL
EOF

echo "✅ Created apps/audiobook/.env.production"

echo ""
echo "🏗️  Building Audiobook App..."
cd apps/audiobook || { echo "❌ Failed to enter apps/audiobook"; exit 1; }
npm install
npm run build
cd ../.. || { echo "❌ Failed to return to root"; exit 1; }

echo ""
echo "🔥 Ready to Deploy!"
echo "Running: firebase deploy"
echo "------------------------------------------------"
firebase deploy

echo ""
echo "🎉 Deployment Complete!"
