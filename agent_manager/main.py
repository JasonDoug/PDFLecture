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
        
        # GET: List or Retrieve
        if request.method == 'GET':
            agent_id = request.args.get('agentId')
            
            if agent_id:
                doc = db.collection(collection_name).document(agent_id).get()
                if not doc.exists:
                    return ({'error': 'Agent not found'}, 404, cors_headers())
                return (json.dumps(doc.to_dict()), 200, cors_headers())
            else:
                # List all
                agents = []
                docs = db.collection(collection_name).stream()
                for doc in docs:
                    agents.append(doc.to_dict())
                return (json.dumps({'agents': agents}), 200, cors_headers())

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
