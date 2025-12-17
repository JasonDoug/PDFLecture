#!/bin/bash

# Setup script for Google Cloud Platform resources
# Run this once to create necessary infrastructure

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found. Copy .env.example to .env and fill in your values."
    exit 1
fi

echo "Setting up GCP resources for PDF-to-Lecture service..."
echo "Project ID: $GCP_PROJECT_ID"
echo ""

# Set the project
gcloud config set project $GCP_PROJECT_ID

# Enable required APIs
# Enable required APIs
echo "Enabling required APIs (skipping for now)..."
# gcloud services enable \
#     cloudfunctions.googleapis.com \
#     cloudrun.googleapis.com \
#     cloudbuild.googleapis.com \
#     storage.googleapis.com \
#     firestore.googleapis.com \
#     pubsub.googleapis.com \
#     artifactregistry.googleapis.com

# Create GCS bucket
echo ""
echo "Creating Cloud Storage bucket: $GCS_BUCKET_NAME"
gsutil mb -l us-central1 gs://$GCS_BUCKET_NAME || echo "Bucket already exists"

# Set bucket CORS for web uploads
echo "Setting CORS policy..."
cat > /tmp/cors.json << EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "POST"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF
gsutil cors set /tmp/cors.json gs://$GCS_BUCKET_NAME
rm /tmp/cors.json

# Create Firestore database (if not exists)
echo ""
echo "Checking Firestore database..."
gcloud firestore databases describe --database="(default)" 2>/dev/null || \
    gcloud firestore databases create --location=us-central1 --type=firestore-native

# Create Pub/Sub topic for document analysis
echo ""
echo "Creating Pub/Sub topic..."
gcloud pubsub topics create document-analysis || echo "Topic already exists"
gcloud pubsub topics create script-generation || echo "Topic already exists"
gcloud pubsub topics create audio-generation || echo "Topic already exists"

echo ""
echo "✓ GCP resources setup complete!"
echo ""
echo "Next steps:"
echo "1. Add your GEMINI_API_KEY to .env file"
echo "2. Run 'pip install -r requirements.txt'"
echo "3. Test locally with './run_local.sh'"
echo "4. Deploy with './deploy.sh'"
