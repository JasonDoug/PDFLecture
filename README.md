# PDF-to-Lecture Service

Serverless platform that transforms PDF documents into engaging audio lectures using AI.

## Features

- 📄 PDF Upload & Storage
- 🤖 AI-powered document analysis with Gemini vision model
- 📝 Intelligent lecture script generation
- 🎙️ Text-to-speech audio generation
- 🎯 Word-level highlighting synchronized with audio

## Architecture

Built on Google Cloud Platform:
- **Cloud Functions (Gen 2)**: Serverless compute
- **Cloud Storage**: PDF and audio file storage
- **Firestore**: Job metadata and state management
- **Pub/Sub**: Event-driven processing pipeline
- **Gemini API**: Document understanding

## Prerequisites

- Python 3.12+
- Google Cloud SDK (`gcloud`)
- Google Cloud Project with billing enabled
- Gemini API key

## Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to project
cd PDFLecture

# Copy environment template
cp .env.example .env

# Edit .env and fill in your values:
# - GCP_PROJECT_ID
# - GCS_BUCKET_NAME
# - GEMINI_API_KEY
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup GCP Resources

```bash
# Make scripts executable
chmod +x *.sh

# Run setup (creates bucket, Firestore, Pub/Sub topic, etc.)
./setup_gcp.sh
```

### 4. Local Development

```bash
# Start local development servers
./run_local.sh

# In another terminal, test with a PDF
./test_upload.sh path/to/sample.pdf
```

The local server runs two endpoints:
- Upload: `http://localhost:8080`
- Analyzer: `http://localhost:8081/analyze`

### 5. Deploy to Production

```bash
# Store Gemini API key in Secret Manager
echo -n 'your-gemini-api-key' | gcloud secrets create GEMINI_API_KEY --data-file=-

# Grant access to the secret
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:$GCP_PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Deploy functions
./deploy.sh
```

## API Usage

### Upload PDF

```bash
curl -X POST \
  -F "file=@document.pdf" \
  https://YOUR-FUNCTION-URL/upload
```

Response:
```json
{
  "success": true,
  "jobId": "job-uuid-123",
  "message": "PDF uploaded successfully",
  "pdf": {
    "filename": "document.pdf",
    "size_mb": 2.5
  },
  "status": "processing"
}
```

### Check Job Status

Query Firestore for job status:
```javascript
const job = await firestore
  .collection('lecture-jobs')
  .doc(jobId)
  .get();
```

## Project Structure

```
PDFLecture/
├── upload_handler/
│   └── main.py              # PDF upload function
├── document_analyzer/
│   └── main.py              # Gemini document analysis
├── script_generator/
│   ├── main.py              # Script generation function
│   └── agents.py            # Agent persona definitions
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
├── setup_gcp.sh            # GCP infrastructure setup
├── deploy.sh               # Deployment script
├── run_local.sh            # Local development
└── test_upload.sh          # Test script
```

## Data Flow

1. **Upload**: PDF uploaded to Cloud Storage, job created in Firestore
2. **Trigger**: Pub/Sub message sent to analyzer
3. **Analysis**: Gemini vision model analyzes PDF comprehensively
4. **Store**: Analysis saved to Cloud Storage and Firestore
5. **Script**: Agent persona generates spoken script in chunks
6. **Store**: Script saved to Cloud Storage and Firestore
7. **Next**: Audio generation (TODO)
6. **Audio**: TTS generation (TODO)
7. **Complete**: Audio ready for playback

## Cost Estimates

Per 20-page PDF lecture:
- Cloud Functions: $0.05-0.10
- Gemini API: $0.05-0.10
- Cloud Storage: $0.01/month
- **Total**: ~$0.10-0.20 per lecture

## Development Status

- [x] PDF upload handler
- [x] Document analysis with Gemini
- [x] Script generation service
- [x] Agent management (embedded in script generator)
- [ ] Audio generation (TTS)
- [ ] Audio generation (TTS)
- [ ] Interactive web player
- [ ] Status polling endpoint

## License

MIT
