import os
import json
import datetime
from typing import Dict, Any, Optional

import functions_framework
from google.cloud import firestore

# Initialize Firestore
_firestore_client = None

def get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client()
    return _firestore_client

def cors_headers(methods: str = 'GET, POST, DELETE, OPTIONS') -> Dict[str, str]:
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': methods,
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600'
    }

@functions_framework.http
def manage_agents(request):
    """
    HTTP Cloud Function for Agent Management
    GET /agents               -> List all agents
    GET /agents?agentId=...   -> Get specific agent
    POST /agents              -> Create/Update agent
    DELETE /agents?agentId=.. -> Delete agent
    """
    
    # Handle CORS
    if request.method == 'OPTIONS':
        return ('', 204, cors_headers())

    try:
        db = get_firestore_client()
        collection_name = 'agents' # Dedicated collection for agents
        
        if request.method == 'GET':
            agent_id = request.args.get('agentId')
            
            # Define built-in agents (mirrors script_generator/agents.py)
            built_in_agents = [
                {
                    "agentId": "prof-classics-001",
                    "name": "Professor Classics",
                    "description": "Formal, structured, academic",
                    "personality": {
                        "traits": ["formal", "structured", "academic", "patience"],
                        "teaching_style": "Socratic method, highly structured, clear explanations",
                        "tone": "Academic and formal",
                        "humor_level": "low"
                    },
                    "voice": {"provider": "google", "voice_id": "en-US-Journey-D"},
                    "is_builtin": True
                },
                {
                    "agentId": "dr-straightforward-001",
                    "name": "Dr. Straightforward",
                    "description": "Direct, concise, no-nonsense",
                    "personality": {
                        "traits": ["direct", "concise", "clear", "efficient"],
                        "teaching_style": "Bullet points, key takeaways, no fluff",
                        "tone": "Professional and direct",
                        "humor_level": "none"
                    },
                    "voice": {"provider": "google", "voice_id": "en-US-Journey-F"},
                    "is_builtin": True
                },
                {
                    "agentId": "coach-motivator-001",
                    "name": "Coach Motivator",
                    "description": "Encouraging, enthusiastic, practical",
                    "personality": {
                        "traits": ["enthusiastic", "supportive", "energetic", "practical"],
                        "teaching_style": "Encourages the learner, frames challenges as opportunities",
                        "tone": "High energy and motivational",
                        "humor_level": "moderate"
                    },
                    "voice": {"provider": "google", "voice_id": "en-US-Studio-M"},
                    "is_builtin": True
                },
                {
                    "agentId": "lit-reviewer-001",
                    "name": "Dr. Aris (Fiction)",
                    "description": "Scholarly literary critic for fiction analysis",
                    "personality": {
                        "traits": ["scholarly", "analytical", "eloquent", "nuanced"],
                        "teaching_style": "Deep literary analysis focusing on themes, narrative structure",
                        "tone": "Academic, thoughtful, and critical",
                        "humor_level": "low"
                    },
                    "voice": {"provider": "google", "voice_id": "en-GB-Neural2-D"},
                    "is_builtin": True
                }
            ]
            
            # Convert built-ins to dict for easy merging
            agents_map = {a['agentId']: a for a in built_in_agents}

            if agent_id:
                # Try Firestore first (override)
                doc = db.collection(collection_name).document(agent_id).get()
                if doc.exists:
                    return (json.dumps(doc.to_dict()), 200, cors_headers())
                elif agent_id in agents_map:
                    return (json.dumps(agents_map[agent_id]), 200, cors_headers())
                else:
                    return ({'error': 'Agent not found'}, 404, cors_headers())
            else:
                # List all (merge Firestore over built-ins)
                docs = db.collection(collection_name).stream()
                for doc in docs:
                    data = doc.to_dict()
                    if 'agentId' in data:
                        agents_map[data['agentId']] = data
                
                return (json.dumps({'agents': list(agents_map.values())}), 200, cors_headers())

        # POST: Create or Update
        elif request.method == 'POST':
            data = request.get_json()
            if not data or 'agentId' not in data:
                return ({'error': 'agentId is required'}, 400, cors_headers())
            
            agent_id = data['agentId']
            
            # Basic validation
            required_fields = ['name', 'personality', 'voice']
            for field in required_fields:
                if field not in data:
                    return ({'error': f'Missing required field: {field}'}, 400, cors_headers())
            
            # Add metadata
            data['updated_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
            if 'created_at' not in data: # Only set if new (handled by client or merge?)
                 # For simplicity, we just set updated_at. 
                 # Firestore merge=True handles partials, but here we likely want full replace for config.
                 pass
            
            db.collection(collection_name).document(agent_id).set(data)
            
            return ({'success': True, 'agentId': agent_id, 'message': 'Agent saved'}, 200, cors_headers())

        # DELETE: Remove
        elif request.method == 'DELETE':
            agent_id = request.args.get('agentId')
            if not agent_id:
                 return ({'error': 'agentId required for deletion'}, 400, cors_headers())
            
            db.collection(collection_name).document(agent_id).delete()
            return ({'success': True, 'message': 'Agent deleted'}, 200, cors_headers())

        else:
            return ({'error': 'Method not allowed'}, 405, cors_headers())

    except Exception as e:
        print(f"Error in manage_agents: {e}")
        return ({'error': str(e)}, 500, cors_headers())
