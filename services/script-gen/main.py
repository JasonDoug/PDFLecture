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

def generate_section_script(section: Dict[str, Any], agent, document_type: str = "Non-Fiction", prev_context: str = "") -> str:
    """Generate script for a single section using Gemini"""
    # Lazy import to avoid startup overhead
    import google.generativeai as genai
    
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(
        'gemini-3.0-flash',
        system_instruction=agent.system_prompt
    )
    
    # Grounding instructions based on document type
    grounding_instruction = ""
    if document_type == "Fiction":
        grounding_instruction = "This is a work of fiction. RESPECT THE NARRATIVE. Do not treat characters or events as historical facts unless explicitly stated in the text. Focus on the story, themes, and emotional arc."
    else:
        grounding_instruction = "This is non-fiction. Stick STRICTLY to the provided text. Do not hallucinate external facts or go on tangents. If the text doesn't say it, don't invent it."

    # Construct prompt based on agent persona
    prompt = f"""
    TASK: Convert the following section into a spoken lecture script.
    
    CONTEXT:
    Document Type: {document_type}
    {grounding_instruction}
    
    AGENT INFO (Reinforcement):
    Name: {agent.name}
    Tone: {agent.personality.tone}
    
    INPUT SECTION:
    Title: {section.get('title', 'Untitled')}
    Detailed Content (Primary Source): {section.get('detailed_content', 'No detailed content provided.')}
    Key Points (Summary): {section.get('key_points', [])}
    Short Content (Legacy): {section.get('content', '')}
    
    PREVIOUS CONTEXT:
    {prev_context}
    
    OUTPUT GUIDELINES:
    - Write EXACTLY as it should be spoken.
    - {agent.personality.humor_level} humor.
    - Include {agent.personality.example_preference}.
    - Connect to the previous section.
    - NO scene directions.
    - Length: Under {agent.script_config.max_section_length} words.
    """
    
    response = model.generate_content(
        prompt,
        generation_config={
            'temperature': 0.7,
        }
    )
    
    usage = {
        'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', 0),
        'candidates_tokens': getattr(response.usage_metadata, 'candidates_token_count', 0)
    }
    
    return response.text, usage

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
        
        # Determine Document Type (Default to Non-Fiction)
        document_type = analysis.get('document_type', 'Non-Fiction')
        print(f"Document Type: {document_type}")
        
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
        total_script_cost = 0.0
        for i, section in enumerate(sections):
            print(f"Generating section {i+1}/{total_sections}")
            
            # Update progress
            progress = 40 + int((i / total_sections) * 20) # 40% to 60%
            job_ref.update({
                'progress.percentage': progress,
                'progress.message': f'Writing section {i+1} of {total_sections}...'
            })
            
            script_text, usage = generate_section_script(section, agent, document_type, prev_context)
            
            # Calculate cost for this section
            section_cost = (usage['prompt_tokens'] * 0.5e-6) + (usage['candidates_tokens'] * 3.0e-6)
            total_script_cost += section_cost
            
            full_script.append({
                'title': section.get('title'),
                'page_range': section.get('page_range'),
                'text': script_text,
                'usage': usage,
                'cost_usd': section_cost
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
        from google.cloud import firestore
        job_ref.update({
            'script': {
                'storage_path': storage_path,
                'section_count': len(full_script),
                'cost_usd': total_script_cost
            },
            'total_estimated_cost_usd': firestore.Increment(total_script_cost),
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
