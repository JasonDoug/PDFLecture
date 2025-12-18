import base64
import json
import os
from datetime import datetime
from typing import Dict, List, Any

import functions_framework

# Initialize clients lazily
def get_storage_client():
    from google.cloud import storage
    return storage.Client()

from google.cloud import firestore

def get_firestore_client():
    return firestore.Client()



# pubsub_v1 is not used in this file, so it can be removed if not needed elsewhere.
# For now, keeping it as it was not explicitly removed by the instruction.
# from google.cloud import pubsub_v1


def download_json_from_gcs(storage_path: str) -> Dict[str, Any]:
    """Download and parse JSON from GCS"""
    client = get_storage_client()
    
    if storage_path.startswith('gs://'):
        path_parts = storage_path.replace('gs://', '').split('/', 1)
        bucket_name = path_parts[0]
        blob_name = path_parts[1]
    else:
        raise ValueError(f"Invalid storage path: {storage_path}")
        
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    content = blob.download_as_string()
    return json.loads(content)

def upload_to_gcs(bucket_name: str, blob_path: str, content: Any, content_type: str) -> str:
    """Upload content to GCS"""
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    if isinstance(content, str):
        blob.upload_from_string(content, content_type=content_type)
    elif isinstance(content, bytes):
        blob.upload_from_string(content, content_type=content_type)
    else:
        # Assume JSON payload if dict/list
        blob.upload_from_string(json.dumps(content), content_type=content_type)
        
    return f"gs://{bucket_name}/{blob_path}"

@functions_framework.cloud_event
def generate_audio(cloud_event):
    """
    Cloud Function triggered by Pub/Sub message
    Generates audio from script
    """
    try:
        # Parse Pub/Sub message
        message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        message = json.loads(message_data)
        
        job_id = message.get('jobId')
        if not job_id:
            print("Error: No jobId in message")
            return
            
        print(f"Starting audio generation for job: {job_id}")
        
        # Lazy loads
        from agents import get_agent, Agent, VoiceConfig
        from tts_providers import get_provider, TTSConfig

        # Initialize
        db = get_firestore_client()
        collection_name = os.environ.get('FIRESTORE_COLLECTION', 'lecture-jobs')
        job_ref = db.collection(collection_name).document(job_id)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            print(f"Error: Job {job_id} not found")
            return
            
        job_data = job_doc.to_dict()
        
        # Update status
        job_ref.update({
            'status': 'generating_audio',
            'progress.current_step': 'generating_audio',
            'progress.percentage': 70,
            'progress.message': 'Synthesizing audio (this may take a while)...'
        })
        
        # Get Script Path
        script_path = job_data.get('script', {}).get('storage_path')
        if not script_path:
            raise ValueError("No script storage path found")
            
        # Download Script
        script_data = download_json_from_gcs(script_path)
        sections = script_data.get('sections', [])
        
        # Determine Agent and Voice Config
        agent_id = script_data.get('agentId') or job_data.get('agent', {}).get('agentId', 'prof-classics-001')
        agent = get_agent(agent_id)
        
        # Create TTS Config
        tts_config = TTSConfig(
            provider=agent.voice.provider,
            voice_id=agent.voice.voice_id,
            stability=agent.voice.stability,
            similarity_boost=agent.voice.similarity_boost,
            style=agent.voice.style,
            speaking_rate=agent.voice.speaking_rate
        )
        
        # Instantiate Provider
        provider = get_provider(tts_config.provider)
        print(f"Using TTS Provider: {tts_config.provider} with voice {tts_config.voice_id}")
        
        bucket_name = os.environ.get('GCS_BUCKET_NAME', 'pdf-lecture-uploads')
        audio_results = []
        total_duration = 0.0
        total_audio_cost = 0.0
        
        for i, section in enumerate(sections):
            section_id = section.get('section_id', i+1)
            text = section.get('text') or section.get('script', '')
            
            if not text:
                print(f"Skipping empty section {section_id}")
                continue
                
            print(f"Generating audio for section {section_id} ({len(text)} chars)...")
            
            # Generate Audio
            try:
                result = provider.generate_audio(text, tts_config)
                
                # Calculate TTS Cost (2025 Pricing)
                char_count = len(text)
                if tts_config.provider == 'google':
                     # Journey/Chirp HD: $30.00/1M chars, Studio: $160.00/1M chars
                     # We use a blend or check voice name for precision
                     if 'Studio' in tts_config.voice_id:
                         section_audio_cost = char_count * 160.0e-6
                     else:
                         # Default to Journey/Chirp HD rate
                         section_audio_cost = char_count * 30.0e-6
                else:
                     # ElevenLabs: $0.20 per 1k = $200.00 per 1M characters
                     section_audio_cost = char_count * 200.0e-6
                
                total_audio_cost += section_audio_cost
            except Exception as e:
                print(f"Error generating audio for section {section_id}: {e}")
                raise
            
            total_duration += result.duration_seconds
            
            # Upload Audio
            audio_path = f"uploads/{job_id}/audio/section_{section_id}.mp3"
            gcs_audio_uri = upload_to_gcs(bucket_name, audio_path, result.audio_content, "audio/mpeg")
            
            # Upload Timestamps
            time_path = f"uploads/{job_id}/audio/section_{section_id}_timestamps.json"
            gcs_time_uri = upload_to_gcs(bucket_name, time_path, result.timestamps, "application/json")
            
            audio_results.append({
                "section_id": section_id,
                "audio_path": gcs_audio_uri,
                "timestamps_path": gcs_time_uri,
                "duration_seconds": result.duration_seconds,
                "characters": char_count,
                "cost_usd": section_audio_cost
            })
            
            # Update progress
            progress_pct = 70 + int((i + 1) / len(sections) * 25)  # 70% -> 95%
            job_ref.update({
                'progress.percentage': progress_pct,
                'progress.message': f'Synthesized section {i+1} of {len(sections)}...'
            })

        # Final Update
        job_ref.update({
            'status': 'completed',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'audio': {
                'status': 'completed',
                'total_duration_seconds': total_duration,
                'sections': audio_results,
                'cost_usd': total_audio_cost
            },
            'total_estimated_cost_usd': firestore.Increment(total_audio_cost),
            'progress': {
                'current_step': 'completed',
                'percentage': 100,
                'message': 'Lecture generation complete! Ready to play.'
            }
        })
        
        print(f"Job {job_id} completed successfully!")
        
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        if 'job_ref' in locals():
            job_ref.update({
                'status': 'failed',
                'progress.message': f'Audio generation failed: {str(e)}'
            })

@functions_framework.http
def generate_audio_http(request):
    """HTTP trigger for testing"""
    try:
        data = request.get_json()
        job_id = data.get('jobId')
        
        class MockEvent:
            data = {
                "message": {
                    "data": base64.b64encode(json.dumps({'jobId': job_id}).encode())
                }
            }
            
        generate_audio(MockEvent())
        return {'success': True}, 200
    except Exception as e:
        return {'error': str(e)}, 500
