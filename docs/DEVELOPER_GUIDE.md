# 🛠️ Developer Guide

This guide provides technical details for engineers wanting to contribute to or maintain the Audio Intelligence Suite.

## 📦 Monorepo Structure

The project is organized into two primary layers: `apps` (frontends) and `services` (backends).

```text
.
├── apps/
│   ├── portal/        # Main landing page (Vanilla HTML/CSS)
│   ├── lecture/       # University Lecture frontend (Vanilla JS)
│   └── audiobook/     # Premium Audiobook (React/Vite)
├── services/
│   ├── orchestrator/  # API Gateway & Logic Layer
│   ├── analyzer/      # Gemini Vision/Text analyzer
│   ├── script-gen/    # Gemini Script generator
│   └── audio-gen/     # TTS synthesis and cost tracking
├── docs/              # Extended documentation
└── start_suite.sh     # Local development orchestrator
```

## 🛠️ Local Development Setup

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- Google Cloud CLI (`gcloud`)
- Firebase CLI (`npm install -g firebase-tools`)

### 2. Environment Configuration
Create a `.env` file in the root directory:
```bash
GCP_PROJECT_ID=your-project-id
GCS_BUCKET_NAME=your-bucket-name
FIRESTORE_COLLECTION=pdf2lecture
GEMINI_API_KEY=your-api-key
ELEVENLABS_API_KEY=your-key (optional)
```

### 3. Running Locally
The `start_suite.sh` script launches all backends (using Functions Framework) and the Portal Launcher.
```bash
./start_suite.sh
```
- **Portal**: http://localhost:3000
- **Lecture App**: http://localhost:8085
- **Audiobook App**: http://localhost:5173

## ☁️ Cloud Architecture & Deployment

### Backend Services
Backends are deployed as **Google Cloud Functions (Gen 2)**.
Use the provided script for batch deployment:
```bash
./deploy_services.sh
```

### Frontend Hosting
All three apps are hosted via **Firebase Hosting**.
The `deploy_hosting.sh` script handles:
1. Vite builds for the Audiobook app.
2. Injecting production backend URLs into client configs.
3. Multi-path deployment to `pdf2audiobook-477309.web.app`.

### Pipeline Flow
1. **Orchestrator** receives PDF.
2. PDF is cleaned by **PDF Processor**.
3. **Analyzer** (Gemini) extracts structured metadata.
4. **Script Gen** (Gemini) crafts the narration.
5. **Audio Gen** (TTS) synthesizes audio and increments character costs in Firestore.

## 💰 Cost Calculation Logic
Costs are aggregated in the `audio-gen` service using `firestore.Increment`.
- **Google TTS**: Charges based on character count ($30/1M for Journey, $160/1M for Studio).
- **Gemini**: Usage metadata (tokens) is passed through the pipeline.
- **Conversion**: Token/Character counts are converted to USD decimals at the end of each stage.
