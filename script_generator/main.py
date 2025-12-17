import base64
import json
import os
from datetime import datetime
from typing import Dict, List, Any

import functions_framework

# Initialize clients lazily to prevent container startup crashes
def get_storage_client():
    from google.cloud import storage
    return storage.Client()

def get_firestore_client():
    from google.cloud import firestore
    return firestore.Client()

def get_pubsub_client():
    from google.cloud import pubsub_v1
    return pubsub_v1.PublisherClient()

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

def upload_json_to_gcs(bucket_name: str, blob_name: str, data: Dict[str, Any]) -> str:
    """Upload JSON to GCS and return storage path"""
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    blob.upload_from_string(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    
    return f"gs://{bucket_name}/{blob_name}"

def generate_section_script(section: Dict[str, Any], agent, prev_context: str = "") -> str:
    """Generate script for a single section using Gemini"""
    # Lazy import to avoid startup overhead
    import google.generativeai as genai
    
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Construct prompt based on agent persona
    prompt = f"""
    You are {agent.name}.
    Description: {agent.description}
    Tone: {agent.personality.tone}
    Teaching Style: {agent.personality.teaching_style}
    
    Your task is to convert the following section of a document into a spoken lecture script.
    
    Section Title: {section.get('title', 'Untitled')}
    Content:
    {section.get('content', '')}
    
    Previous Context: {prev_context}
    
    Guidelines:
    - Write EXACTLY as it should be spoken.
    - Use clear, engaging language.
    - {agent.personality.humor_level} humor.
    - Include {agent.personality.example_preference}.
    - Connect to the previous section if relevant.
    - Do NOT include scene directions or actor notes, just the speech.
    - Keep it under {agent.script_config.max_section_length} words.
    """
    
    response = model.generate_content(prompt)
    return response.text

@functions_framework.cloud_event
def generate_script(cloud_event):
    """
    Cloud Function triggered by Pub/Sub message
    Generates lecture script from analysis
    """
    try:
        # Parse Pub/Sub message
        message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        message = json.loads(message_data)
        
        job_id = message.get('jobId')
        if not job_id:
            print("Error: No jobId in message")
            return
            
        print(f"Starting script generation for job: {job_id}")
        
        # Lazy imports
        from agents import get_agent
        
        # Initialize
        db = get_firestore_client()
        collection_name = os.environ.get('FIRESTORE_COLLECTION', 'lecture-jobs')
        job_ref = db.collection(collection_name).document(job_id)
        
        # Update status
        job_ref.update({
            'status': 'generating_script',
            'progress.current_step': 'generating_script',
            'progress.percentage': 40,
            'progress.message': 'Writing lecture script...'
        })
        
        # Get Job Data
        job_doc = job_ref.get()
        if not job_doc.exists:
            print(f"Job {job_id} not found")
            return
        job_data = job_doc.to_dict()
        
        # Get Analysis
        analysis_path = job_data.get('analysis', {}).get('storage_path')
        if not analysis_path:
            raise ValueError("No analysis storage path found")
            
        analysis = download_json_from_gcs(analysis_path)
        
        # Get Agent
        agent_id = job_data.get('agent', {}).get('agentId', 'prof-classics-001')
        print(f"Using agent: {agent_id}")
        agent = get_agent(agent_id)
        
        # Generate Script
        full_script = []
        # Support both 'suggested_sections' (Gemini output) and 'sections' (legacy)
        sections = analysis.get('suggested_sections') or analysis.get('sections') or []
        
        if not sections:
            print(f"Warning: No sections found in analysis: {analysis.keys()}")
            # Fallback: if analysis is just a list, treat it as sections
            if isinstance(analysis, list):
                sections = analysis
        prev_context = ""
        
        total_sections = len(sections)
        for i, section in enumerate(sections):
            print(f"Generating section {i+1}/{total_sections}")
            
            # Update progress
            progress = 40 + int((i / total_sections) * 20) # 40% to 60%
            job_ref.update({
                'progress.percentage': progress,
                'progress.message': f'Writing section {i+1} of {total_sections}...'
            })
            
            script_text = generate_section_script(section, agent, prev_context)
            
            full_script.append({
                'title': section.get('title'),
                'page_range': section.get('page_range'),
                'text': script_text
            })
            
            # Update context (last 200 chars)
            prev_context = script_text[-200:]
            
        # Compile final script object
        script_data = {
            'jobId': job_id,
            'agent': {
                'id': agent.agent_id,
                'name': agent.name
            },
            'sections': full_script,
            'generated_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Save to GCS
        bucket_name = os.environ.get('GCS_BUCKET_NAME')
        blob_name = f"scripts/{job_id}/script.json"
        storage_path = upload_json_to_gcs(bucket_name, blob_name, script_data)
        
        # Update Job
        job_ref.update({
            'script': {
                'storage_path': storage_path,
                'section_count': len(full_script)
            },
            'status': 'generating_audio', # Next step
            'progress.current_step': 'generating_audio',
            'progress.percentage': 60,
            'progress.message': 'Script generation complete'
        })
        
        print(f"Script generation complete for {job_id}")
        
        # Trigger Audio Generation
        trigger_audio_generation(job_id)
        
    except Exception as e:
        print(f"Error generating script: {str(e)}")
        # Only update if we have a job_ref
        if 'job_ref' in locals():
            job_ref.update({
                'status': 'failed',
                'progress.message': f'Script generation failed: {str(e)}'
            })

def trigger_audio_generation(job_id: str) -> None:
    """Trigger audio generation via Pub/Sub"""
    client = get_pubsub_client()
    project_id = os.environ.get('GCP_PROJECT_ID')
    topic_name = f"projects/{project_id}/topics/audio-generation"
    
    message_data = json.dumps({
        'jobId': job_id,
        'timestamp': datetime.utcnow().isoformat()
    }).encode('utf-8')
    
    future = client.publish(topic_name, message_data)
    print(f"Triggered audio generation: {future.result()}")
