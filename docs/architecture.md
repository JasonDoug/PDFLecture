# System Architecture

The PDF-to-Lecture service is designed as an event-driven, serverless architecture on Google Cloud Platform.

## High-Level Data Flow

1.  **Ingestion**: Client uploads PDF to `upload_handler`.
2.  **Storage**: PDF is stored in Cloud Storage (`gs://<bucket>/uploads/<jobId>/original.pdf`).
3.  **State**: A Job document is created in Firestore to track status.
4.  **Analysis Trigger**: `upload_handler` publishes message to `document-analysis` Pub/Sub topic.
5.  **Analysis**: `document_analyzer` triggers, reads PDF, uses Gemini Vision AI to extract structure/content.
6.  **Script Trigger**: `document_analyzer` publishes message to `script-generation` Pub/Sub topic.
7.  **Script Generation**: `script_generator` triggers, uses Gemini to write spoken content based on Agent persona.
8.  **Output**: Final script is stored in GCS and Firestore is updated.

## Component Details

### 1. Upload Handler (`upload_handler/`)
*   **Type**: Cloud Function (2nd Gen, HTTP)
*   **Runtime**: Python 3.12
*   **Memory**: 512MB
*   **Key Dependencies**: `google-cloud-storage`, `google-cloud-firestore`, `google-cloud-pubsub`
*   **Environment**:
    *   `GCP_PROJECT_ID`
    *   `GCS_BUCKET_NAME`
    *   `FIRESTORE_COLLECTION`

### 2. Document Analyzer (`document_analyzer/`)
*   **Type**: Cloud Function (2nd Gen, Pub/Sub Trigger)
*   **Trigger Topic**: `document-analysis`
*   **Runtime**: Python 3.12
*   **Memory**: 1GB (for PDF processing)
*   **Key Dependencies**: `google-generativeai` (Gemini SDK)
*   **Models**: 
    *   `gemini-2.5-flash` (Default)
    *   `gemini-3.0-flash` (Forward compatible)
*   **Config**: Uses `media_resolution='HIGH'` for optimal PDF rendering.

### 3. Script Generator (`script_generator/`)
*   **Type**: Cloud Function (2nd Gen, Pub/Sub Trigger)
*   **Trigger Topic**: `script-generation`
*   **Runtime**: Python 3.12
*   **Memory**: 512MB
*   **Key Concepts**:
    *   **Agents**: Defined in `script_generator/agents.py`.
    *   **Context Window**: Passes previous context to LLM for continuity.
*   **Output**: JSON file with section-by-section scripts.

### 4. Audio Generator (`audio_generator/`)
*   **Type**: Cloud Function (2nd Gen, Pub/Sub Trigger)
*   **Trigger Topic**: `audio-generation`
*   **Runtime**: Python 3.12
*   **Memory**: 512MB
*   **Providers**:
    *   **ElevenLabs**: High-quality (API Key required).
    *   **Google Cloud TTS**: Cost-effective fallback.
*   **Logic**:
    *   Downloads script JSON.
    *   Determines `VoiceConfig` from Agent.
    *   Synthesizes section-by-section.
    *   Saves `.mp3` and timestamp JSONs to GCS.

## Data Schema

### Firestore Job Document

```json
{
  "jobId": "uuid",
  "status": "script_generated",
  "created_at": "timestamp",
  "pdf": {
    "filename": "file.pdf",
    "storage_path": "gs://..."
  },
  "analysis": {
    "status": "completed",
    "storage_path": "gs://...",
    "main_topics": [...]
  },
  "script": {
    "status": "completed",
    "storage_path": "gs://...",
    "section_count": 5
  },
  "progress": {
    "current_step": "script_generated",
    "percentage": 60,
    "message": "Script generation complete"
  }
}
```

## Infrastructure

Managed via shell scripts (for now):
*   `setup_gcp.sh`: Idempotent resource creation (buckets, topics, DB).
*   `deploy.sh`: `gcloud functions deploy` commands.

## Future Components

*   **Frontend**: Web UI to polling Firestore and play audio.
