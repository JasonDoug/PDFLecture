#!/bin/bash

# Deployment script for Google Cloud Functions

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

REGION=${REGION:-us-central1}

echo "Deploying PDF-to-Lecture Cloud Functions..."
echo "Project: $GCP_PROJECT_ID"
echo "Region: $REGION"
echo ""

# Copy requirements.txt to all function directories
echo "Copying requirements.txt to function directories..."
for dir in upload_handler document_analyzer script_generator audio_generator status_handler agent_manager; do
    if [ -d "$dir" ]; then
        cp requirements.txt "$dir/"
    fi
done

# Deploy Upload Handler (HTTP trigger)
echo "Deploying upload_pdf function..."
gcloud functions deploy upload_pdf \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=./upload_handler \
    --entry-point=upload_pdf \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,FIRESTORE_COLLECTION=$FIRESTORE_COLLECTION" \
    --max-instances=10 \
    --memory=512MB \
    --timeout=60s

# Deploy Document Analyzer (Pub/Sub trigger)
echo ""
echo "Deploying analyze_document function..."
gcloud functions deploy analyze_document \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=./document_analyzer \
    --entry-point=analyze_document \
    --trigger-topic=document-analysis \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,FIRESTORE_COLLECTION=$FIRESTORE_COLLECTION" \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
    --max-instances=5 \
    --memory=1GB \
    --timeout=540s

# Deploy Script Generator (Pub/Sub trigger)
echo ""
echo "Deploying generate_script function..."
gcloud functions deploy generate_script \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=./script_generator \
    --entry-point=generate_script \
    --trigger-topic=script-generation \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,FIRESTORE_COLLECTION=$FIRESTORE_COLLECTION" \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
    --max-instances=5 \
    --memory=1GB \
    --timeout=540s

# Deploy Audio Generator (Pub/Sub trigger)
echo ""
echo "Deploying generate_audio function..."
gcloud functions deploy generate_audio \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=./audio_generator \
    --entry-point=generate_audio \
    --trigger-topic=audio-generation \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,FIRESTORE_COLLECTION=$FIRESTORE_COLLECTION" \
    --max-instances=5 \
    --memory=1GB \
    --timeout=540s

# Deploy Status Handler (HTTP trigger)
echo ""
echo "Deploying get_job_status function..."
gcloud functions deploy get_job_status \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=./status_handler \
    --entry-point=get_job_status \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,FIRESTORE_COLLECTION=$FIRESTORE_COLLECTION,GCS_BUCKET_NAME=$GCS_BUCKET_NAME" \
    --max-instances=10 \
    --memory=256MB \
    --timeout=30s

# Deploy Agent Manager (HTTP trigger)
echo ""
echo "Deploying manage_agents function..."
gcloud functions deploy manage_agents \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=./agent_manager \
    --entry-point=manage_agents \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,FIRESTORE_COLLECTION=agents" \
    --max-instances=2 \
    --memory=256MB \
    --timeout=30s

echo ""
echo "✓ Deployment complete!"
echo ""
echo "Upload endpoint:"
gcloud functions describe upload_pdf --region=$REGION --gen2 --format="value(serviceConfig.uri)"
echo ""
echo "Note: You need to create a secret in Secret Manager for GEMINI_API_KEY:"
echo "echo -n 'your-api-key' | gcloud secrets create GEMINI_API_KEY --data-file=-"
echo "gcloud secrets add-iam-policy-binding GEMINI_API_KEY \\"
echo "  --member='serviceAccount:$GCP_PROJECT_ID@appspot.gserviceaccount.com' \\"
echo "  --role='roles/secretmanager.secretAccessor'"
