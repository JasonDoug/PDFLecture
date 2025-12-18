#!/bin/bash

# Deploy All Monorepo Services to Cloud Functions

echo "🚀 Starting Production Backend Deployment..."

# Common Env Vars
PROJECT_ID=$(gcloud config get-value project)
REGION="us-west1"
SERVICE_ACCOUNT="852565109955-compute@developer.gserviceaccount.com"

echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Account: $SERVICE_ACCOUNT"
echo "--------------------------------------"

deploy_service() {
    NAME=$1
    SOURCE=$2
    ENTRY_POINT=$3
    MEMORY=$4
    TRIGGER_TYPE=${5:-"http"}
    
    echo "Deploying $NAME..."
    
    if [ "$TRIGGER_TYPE" == "http" ]; then
        TRIGGER_FLAG="--trigger-http --allow-unauthenticated"
    else
        TRIGGER_FLAG="--trigger-topic=$TRIGGER_TYPE"
    fi
    
    gcloud functions deploy $NAME \
        --gen2 \
        --runtime=python310 \
        --region=$REGION \
        --source=$SOURCE \
        --entry-point=$ENTRY_POINT \
        $TRIGGER_FLAG \
        --memory=$MEMORY \
        --service-account=$SERVICE_ACCOUNT \
        --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,ELEVENLABS_API_KEY=ELEVENLABS_API_KEY:latest" \
        --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_NAME=pdf-storage-bucket-5472,FIRESTORE_COLLECTION=pdf2lecturefb"
}

# 1. Upload Handler
deploy_service "upload_pdf" "services/upload-handler" "upload_pdf" "512MB"

# 2. Document Analyzer (Pub/Sub Trigger)
echo "Deploying analyze_document..."
gcloud functions deploy analyze_document \
    --gen2 \
    --runtime=python310 \
    --region=$REGION \
    --source="services/analyzer" \
    --entry-point="analyze_document" \
    --trigger-topic="document-analysis" \
    --memory="2GiB" \
    --service-account=$SERVICE_ACCOUNT \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_NAME=pdf-storage-bucket-5472,FIRESTORE_COLLECTION=pdf2lecturefb"

# 2b. Document Analyzer (HTTP Trigger for Manual)
deploy_service "analyze_document_http" "services/analyzer" "analyze_document_http" "2GiB" "http"

# 3. Script Generator
echo "Deploying generate_script..."
gcloud functions deploy generate_script \
    --gen2 \
    --runtime=python310 \
    --region=$REGION \
    --source="services/script-gen" \
    --entry-point="generate_script" \
    --trigger-topic="script-generation" \
    --memory="1GiB" \
    --service-account=$SERVICE_ACCOUNT \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_NAME=pdf-storage-bucket-5472,FIRESTORE_COLLECTION=pdf2lecturefb"

# 4. Audio Generator
echo "Deploying generate_audio..."
gcloud functions deploy generate_audio \
    --gen2 \
    --runtime=python310 \
    --region=$REGION \
    --source="services/audio-gen" \
    --entry-point="generate_audio" \
    --trigger-topic="audio-generation" \
    --memory="1GiB" \
    --service-account=$SERVICE_ACCOUNT \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,ELEVENLABS_API_KEY=ELEVENLABS_API_KEY:latest" \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_NAME=pdf-storage-bucket-5472,FIRESTORE_COLLECTION=pdf2lecturefb"

# 5. Agent Manager
deploy_service "manage_agents" "services/agent-manager" "manage_agents" "256MB"

# 6. Status Handler
deploy_service "get_job_status" "services/status-handler" "get_job_status" "256MB"

# 7. PDF Processor (Audiobook)
deploy_service "extract_pdf" "services/pdf-processor" "extract_pdf" "1GiB"

# 8. TTS Service (Audiobook)
deploy_service "synthesize_text" "services/tts-service" "synthesize_text" "512MB"

echo "--------------------------------------"
echo "✅ Backend Deployment Complete!"
echo "Retrieving Service URLs..."
echo ""
echo "PDF Processor URL:"
gcloud functions describe extract_pdf --gen2 --region=$REGION --format="value(serviceConfig.uri)"
echo ""
echo "TTS Service URL:"
gcloud functions describe synthesize_text --gen2 --region=$REGION --format="value(serviceConfig.uri)"
echo ""
echo "Please copy these URLs for your Frontend Configuration."

