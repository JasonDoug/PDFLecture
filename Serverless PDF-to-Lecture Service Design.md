# Serverless PDF-to-Lecture Service Design
## Executive Summary
A serverless platform that transforms PDF documents into engaging audio lectures with synchronized word-for-word highlighting. The system uses AI agents with customizable personalities to generate educational content tailored to different learning styles.
## System Architecture
### High-Level Flow
1. PDF Upload → 2. Document Understanding (Gemini) → 3. Script Generation (Agent-based) → 4. Audio Generation (TTS) → 5. Interactive Player with Highlighting
### Technology Stack
* **Backend**: Serverless functions (AWS Lambda / Google Cloud Functions / Azure Functions)
* **Document Processing**: Google Gemini API (gemini-3.0-flash or gemini-2.0-flash for vision)
* **Script Generation**: LLM API (Gemini, GPT-4, or Claude)
* **Audio Generation**: Text-to-Speech API (Google Cloud TTS, ElevenLabs, or Azure TTS)
* **Storage**: Object storage (S3/GCS/Azure Blob) for PDFs, audio files
* **Database**: NoSQL (DynamoDB/Firestore/Cosmos DB) for metadata, agent configs
* **Frontend**: React/Vue/Svelte with audio player component
* **Queue System**: Pub/Sub or SQS for async processing
## Core Components
### 1. PDF Upload Service
**Endpoint**: `POST /api/upload`
**Responsibilities**:
* Accept PDF files up to 50MB
* Validate file type and size
* Generate unique job ID
* Upload to object storage
* Trigger document processing pipeline
* Return job ID to client for status tracking
**Storage Structure**:
```warp-runnable-command
/uploads/{jobId}/
  - original.pdf
  - metadata.json
```
### 2. Document Understanding Service
**Trigger**: Message from upload service
**Responsibilities**:
* Retrieve PDF from object storage
* Send to Gemini API for comprehensive analysis
* Extract structured information:
    * Main topics and subtopics
    * Key concepts and definitions
    * Diagrams, charts, tables (visual context)
    * Difficulty level assessment
    * Suggested learning path
* Store analysis results
**Gemini Implementation**:
```python
from google import genai
import io
client = genai.Client()
# Upload PDF to Gemini Files API
with open(pdf_path, 'rb') as f:
    uploaded_file = client.files.upload(
        file=io.BytesIO(f.read()),
        config={'mime_type': 'application/pdf'}
    )
# Analyze document structure
analysis_prompt = """
Analyze this PDF document and provide:
1. Main topics (hierarchical structure)
2. Key concepts with definitions
3. Visual elements (diagrams, charts, tables) and their context
4. Difficulty level (beginner/intermediate/advanced)
5. Prerequisite knowledge needed
6. Suggested section breakdown for a lecture series
Output as structured JSON.
"""
response = client.models.generate_content(
    model="gemini-3.0-flash",
    contents=[uploaded_file, analysis_prompt],
    config={'response_mime_type': 'application/json'}
)
```
**Output Storage**:
```warp-runnable-command
/uploads/{jobId}/
  - analysis.json (document structure)
  - sections.json (lecture breakdown)
```
### 3. Agent Management Service
**Endpoints**:
* `POST /api/agents` - Create new agent
* `GET /api/agents` - List available agents
* `GET /api/agents/{agentId}` - Get agent details
* `PUT /api/agents/{agentId}` - Update agent
* `DELETE /api/agents/{agentId}` - Delete agent
**Agent Schema**:
```json
{
  "agentId": "prof-classics-001",
  "name": "Professor Classics",
  "personality": {
    "traits": ["witty", "sarcastic", "socratic"],
    "teaching_style": "Uses Socratic method to guide discovery",
    "tone": "Conversational with academic rigor",
    "humor_level": "moderate",
    "example_preference": "real-world analogies"
  },
  "voice": {
    "provider": "elevenlabs",
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "speaking_rate": 1.0
  },
  "script_config": {
    "max_section_length": 500,
    "include_examples": true,
    "example_count": 2,
    "difficulty_adaptation": true,
    "use_questions": true,
    "question_frequency": "medium"
  },
  "created_at": "2025-12-16T00:00:00Z",
  "updated_at": "2025-12-16T00:00:00Z"
}
```
**Built-in Agent Templates**:
* **Professor Classics**: Witty, Socratic, uses analogies
* **Dr. Straightforward**: Direct, no-nonsense, efficient
* **Coach Motivator**: Encouraging, enthusiastic, practical
* **Sage Contemplative**: Philosophical, thoughtful, reflective
### 4. Script Generation Service
**Trigger**: Completion of document understanding + agent selection
**Input**:
* Document analysis from step 2
* Selected agent configuration
* User preferences (section selection, length, etc.)
**Responsibilities**:
* Generate lecture script section by section
* Apply agent personality to content
* Insert rhetorical questions (if agent config specifies)
* Add examples and analogies
* Ensure natural speech patterns
* Create word-level timestamps (estimated for TTS)
**Implementation Approach**:
```python
def generate_script(analysis, agent, section):
    system_prompt = f"""
You are {agent.name}, an AI lecturer with the following personality:
- Traits: {agent.personality.traits}
- Teaching Style: {agent.personality.teaching_style}
- Tone: {agent.personality.tone}
Your goal is to transform educational content into engaging lectures.
Generate a natural, spoken lecture script (not written text).
Include:
- Conversational transitions
- {agent.script_config.example_count} relevant examples per major concept
- Rhetorical questions to engage listeners
- Clear explanations that build on each other
"""
    
    user_prompt = f"""
Create a lecture script for this section:
Title: {section.title}
Key Concepts: {section.concepts}
Visual Elements: {section.visuals}
Difficulty: {section.difficulty}
Make it {agent.personality.tone} and approximately {agent.script_config.max_section_length} words.
"""
    
    response = llm_api.generate(
        system=system_prompt,
        prompt=user_prompt,
        temperature=0.7
    )
    
    return {
        "section_id": section.id,
        "script": response.text,
        "word_count": len(response.text.split()),
        "estimated_duration_seconds": estimate_duration(response.text)
    }
```
**Output Structure**:
```json
{
  "jobId": "job-123",
  "agentId": "prof-classics-001",
  "sections": [
    {
      "section_id": 1,
      "title": "Introduction to Quantum Mechanics",
      "script": "Well, hello there! Today we're diving into...",
      "word_count": 450,
      "estimated_duration": 180
    }
  ],
  "total_duration_estimate": 1200,
  "generated_at": "2025-12-16T00:00:00Z"
}
```
### 5. Audio Generation Service
**Trigger**: Script generation completion
**Responsibilities**:
* Convert script to speech using agent's voice configuration
* Generate word-level timestamps
* Handle long scripts (chunking if necessary)
* Optimize audio format for web playback
* Store audio files with metadata
**TTS Implementation Options**:
**Option A: ElevenLabs (Best quality, natural)**
```python
import requests
def generate_audio_elevenlabs(script, voice_config):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_config.voice_id}/with-timestamps"
    
    payload = {
        "text": script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": voice_config.stability,
            "similarity_boost": voice_config.similarity_boost,
            "style": voice_config.style,
            "use_speaker_boost": True
        }
    }
    
    response = requests.post(url, json=payload)
    
    return {
        "audio_data": response.content,
        "alignment": response.json()["alignment"],  # word timestamps
        "duration": calculate_duration(response.content)
    }
```
**Option B: Google Cloud TTS (Cost-effective, good quality)**
```python
from google.cloud import texttospeech
def generate_audio_google(script, voice_config):
    client = texttospeech.TextToSpeechClient()
    
    synthesis_input = texttospeech.SynthesisInput(text=script)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name=voice_config.voice_id,
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=voice_config.speaking_rate,
        pitch=0.0,
        enable_time_pointing=[texttospeech.AudioConfig.TimepointType.SSML_MARK]
    )
    
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
        enable_time_pointing=True
    )
    
    return {
        "audio_data": response.audio_content,
        "timepoints": response.timepoints,
        "duration": estimate_duration(response.audio_content)
    }
```
**Word-Level Timestamp Generation**:
If TTS provider doesn't support word-level timestamps:
```python
import webrtcvad
import wave
def generate_word_timestamps(audio_file, script):
    # Use forced alignment tools like Montreal Forced Aligner
    # or Gentle for precise word-level timestamps
    words = script.split()
    duration = get_audio_duration(audio_file)
    
    # Simplified approach: estimate based on average speaking rate
    # Better: use forced alignment library
    avg_word_duration = duration / len(words)
    
    timestamps = []
    current_time = 0
    
    for i, word in enumerate(words):
        timestamps.append({
            "word": word,
            "start": current_time,
            "end": current_time + avg_word_duration,
            "index": i
        })
        current_time += avg_word_duration
    
    return timestamps
```
**Output Storage**:
```warp-runnable-command
/uploads/{jobId}/
  - audio/
    - section_1.mp3
    - section_1_timestamps.json
    - section_2.mp3
    - section_2_timestamps.json
  - complete.mp3 (optional full lecture)
```
### 6. Interactive Player Service
**Frontend Component Requirements**:
* HTML5 audio player with custom controls
* Real-time word highlighting synchronized with audio
* Section navigation
* Playback speed control
* Bookmark/note-taking functionality
**Player Features**:
* **Synchronized Highlighting**: Current word highlighted in script display
* **Click-to-seek**: Click any word to jump to that point
* **Section Navigation**: Jump between major sections
* **Progress Tracking**: Remember playback position
* **Transcript Display**: Show full script with scroll-to-current
**Implementation Example (React)**:
```js
import React, { useState, useEffect, useRef } from 'react';
function LecturePlayer({ jobId, sections, audioUrl, timestamps }) {
  const audioRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [currentWordIndex, setCurrentWordIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  useEffect(() => {
    const audio = audioRef.current;
    
    const updateTime = () => {
      const time = audio.currentTime;
      setCurrentTime(time);
      
      // Find current word based on timestamp
      const wordIndex = timestamps.findIndex(
        (ts, i) => ts.start <= time && 
                   (i === timestamps.length - 1 || timestamps[i + 1].start > time)
      );
      
      if (wordIndex !== -1) {
        setCurrentWordIndex(wordIndex);
      }
    };
    
    audio.addEventListener('timeupdate', updateTime);
    return () => audio.removeEventListener('timeupdate', updateTime);
  }, [timestamps]);
  
  const handleWordClick = (timestamp) => {
    audioRef.current.currentTime = timestamp.start;
  };
  
  return (
    <div className="lecture-player">
      <audio ref={audioRef} src={audioUrl} />
      
      <div className="controls">
        <button onClick={() => audioRef.current.play()}>
          Play
        </button>
        <button onClick={() => audioRef.current.pause()}>
          Pause
        </button>
        <input 
          type="range" 
          min="0" 
          max={audioRef.current?.duration || 0}
          value={currentTime}
          onChange={(e) => audioRef.current.currentTime = e.target.value}
        />
      </div>
      
      <div className="transcript">
        {timestamps.map((ts, index) => (
          <span
            key={index}
            className={index === currentWordIndex ? 'highlight' : ''}
            onClick={() => handleWordClick(ts)}
          >
            {ts.word}{' '}
          </span>
        ))}
      </div>
    </div>
  );
}
```
**API Endpoints for Player**:
* `GET /api/lectures/{jobId}` - Get lecture metadata
* `GET /api/lectures/{jobId}/audio/{sectionId}` - Stream audio
* `GET /api/lectures/{jobId}/timestamps/{sectionId}` - Get word timestamps
* `POST /api/lectures/{jobId}/progress` - Save playback position
## Data Models
### Job Schema
```json
{
  "jobId": "job-uuid-123",
  "userId": "user-456",
  "status": "processing|completed|failed",
  "created_at": "2025-12-16T00:00:00Z",
  "updated_at": "2025-12-16T00:05:00Z",
  "pdf": {
    "filename": "quantum_mechanics.pdf",
    "size_bytes": 2500000,
    "page_count": 45,
    "storage_path": "s3://bucket/uploads/job-123/original.pdf"
  },
  "analysis": {
    "status": "completed",
    "main_topics": ["quantum states", "wave functions"],
    "difficulty": "advanced",
    "storage_path": "s3://bucket/uploads/job-123/analysis.json"
  },
  "agent": {
    "agentId": "prof-classics-001",
    "name": "Professor Classics"
  },
  "script": {
    "status": "completed",
    "section_count": 5,
    "total_words": 2500,
    "storage_path": "s3://bucket/uploads/job-123/script.json"
  },
  "audio": {
    "status": "completed",
    "total_duration_seconds": 1200,
    "format": "mp3",
    "storage_paths": [
      "s3://bucket/uploads/job-123/audio/section_1.mp3"
    ]
  },
  "progress": {
    "current_step": "completed",
    "percentage": 100,
    "message": "Lecture ready to play"
  }
}
```
## Pipeline Orchestration
### Workflow State Machine
```warp-runnable-command
UPLOAD → ANALYZING → GENERATING_SCRIPT → GENERATING_AUDIO → COMPLETED
                ↓            ↓                  ↓
              FAILED       FAILED            FAILED
```
### Step Functions / Cloud Workflows Definition
```yaml
states:
  - name: UploadComplete
    type: trigger
    next: AnalyzeDocument
  
  - name: AnalyzeDocument
    type: task
    function: document-understanding-service
    timeout: 300s
    retry:
      max_attempts: 3
      backoff_rate: 2
    next: GenerateScript
    error_handler: HandleFailure
  
  - name: GenerateScript
    type: task
    function: script-generation-service
    timeout: 600s
    retry:
      max_attempts: 2
    next: GenerateAudio
    error_handler: HandleFailure
  
  - name: GenerateAudio
    type: task
    function: audio-generation-service
    timeout: 900s
    retry:
      max_attempts: 2
    next: Complete
    error_handler: HandleFailure
  
  - name: Complete
    type: success
    notification: true
  
  - name: HandleFailure
    type: failure
    notification: true
```
## Serverless Function Architecture
### AWS Lambda Example Structure
**Functions**:
1. `pdf-upload-handler` (API Gateway trigger)
2. `document-analyzer` (S3 trigger)
3. `script-generator` (EventBridge/SQS trigger)
4. `audio-generator` (EventBridge/SQS trigger)
5. `status-poller` (API Gateway trigger)
6. `agent-crud` (API Gateway trigger)
**Environment Variables**:
```warp-runnable-command
GEMINI_API_KEY=xxx
OPENAI_API_KEY=xxx (if using GPT for scripts)
ELEVENLABS_API_KEY=xxx
S3_BUCKET_NAME=pdf-lectures
DYNAMODB_TABLE=lecture-jobs
DYNAMODB_AGENTS_TABLE=lecture-agents
```
### Cost Optimization
* Use Gemini Flash models for cost-effective document analysis
* Cache document analysis results
* Implement tiered storage (frequent access → infrequent → archive)
* Use spot instances for batch processing if needed
* Compress audio files appropriately
## Security Considerations
### Authentication & Authorization
* User authentication via OAuth2/JWT
* API key management for external services
* Per-user rate limiting
* Job ownership validation
### Data Privacy
* Encrypt PDFs at rest (S3 encryption)
* Encrypt audio files at rest
* Signed URLs for temporary access
* Automatic deletion policy (configurable retention)
* GDPR compliance for user data
### Content Safety
* Input validation (PDF format, size)
* Malware scanning on upload
* Content moderation for generated scripts
* Rate limiting to prevent abuse
## Monitoring & Observability
### Metrics to Track
* Upload success rate
* Average processing time per stage
* API error rates (Gemini, TTS providers)
* Audio generation quality scores
* User engagement (play time, completion rate)
### Logging Strategy
* Structured logging (JSON format)
* Log levels: ERROR, WARN, INFO, DEBUG
* Correlation IDs across services
* Performance timing for each stage
### Alerting
* Failed job rate > 5%
* Processing time > SLA threshold
* API quota exhaustion warnings
* Storage capacity warnings
## Scalability Considerations
* Async processing with message queues
* Parallel section generation for large documents
* CDN for audio file delivery
* Database read replicas for heavy read operations
* Horizontal scaling of serverless functions
## Future Enhancements
### Phase 2 Features
* **Multi-language support**: Generate lectures in different languages
* **Interactive quizzes**: Generate comprehension questions based on content
* **Adaptive learning**: Adjust difficulty based on user feedback
* **Collaborative notes**: Share annotations with other learners
* **Mobile apps**: Native iOS/Android applications
### Phase 3 Features
* **Live tutoring mode**: AI agent answers follow-up questions
* **Study groups**: Synchronized playback for groups
* **Custom voice cloning**: Upload your own voice for agents
* **Video generation**: Add visual slides synchronized with audio
* **Learning analytics**: Track comprehension and recommend content
## Cost Estimates (per lecture)
### Assumptions
* 20-page PDF
* 10-minute audio output
* Using Gemini Flash + Google Cloud TTS
**Estimated Costs**:
* Document analysis (Gemini): $0.05 - $0.10
* Script generation (LLM): $0.10 - $0.30
* Audio generation (TTS): $0.20 - $0.50
* Storage (S3): $0.01/month
* Compute (Lambda): $0.05 - $0.10
**Total per lecture**: ~$0.40 - $1.00
**With ElevenLabs TTS**: ~$1.00 - $2.00
## Development Roadmap
### MVP (Minimum Viable Product)
* Single agent (Professor Classics)
* Basic PDF upload (< 50MB)
* Document analysis with Gemini
* Simple script generation
* Audio generation with timestamps
* Basic web player with highlighting
### Phase 1 (Months 1-2)
* Multi-agent support
* Agent customization UI
* Enhanced player (speed control, bookmarks)
* User accounts and job history
* Status polling and notifications
### Phase 2 (Months 3-4)
* Advanced script customization
* Multiple PDF support (comparative lectures)
* Section selection and editing
* Audio quality improvements
* Mobile-responsive design
### Phase 3 (Months 5-6)
* Interactive features (Q&A)
* Analytics dashboard
* API for third-party integrations
* Performance optimizations
* Enterprise features
