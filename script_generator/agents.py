import os
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class AgentPersonality:
    traits: List[str]
    teaching_style: str
    tone: str
    humor_level: str
    example_preference: str

@dataclass
class VoiceConfig:
    provider: str
    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speaking_rate: float = 1.0

@dataclass
class ScriptConfig:
    max_section_length: int = 500
    include_examples: bool = True
    example_count: int = 2
    difficulty_adaptation: bool = True
    use_questions: bool = True
    question_frequency: str = "medium"

@dataclass
class Agent:
    agent_id: str
    name: str
    personality: AgentPersonality
    voice: VoiceConfig
    script_config: ScriptConfig
    description: str = ""
    system_prompt: str = "" # New field for Gemini system instruction

# Define built-in agents
AGENTS = {
    "prof-classics-001": Agent(
        agent_id="prof-classics-001",
        name="Professor Classics",
        description="Witty, Socratic, uses analogies",
        system_prompt="You are Professor Classics, a witty and knowledgeable university professor. Your goal is to teach complex topics using the Socratic method and historical analogies. You speak with academic rigor but warmth. You strictly avoid hallucination and only teach based on provided facts.",
        personality=AgentPersonality(
            traits=["witty", "knowledgeable", "engaging", "slightly dramatic"],
            teaching_style="Uses Socratic method to guide discovery and connects concepts to history",
            tone="Conversational with academic rigor, like a beloved university professor",
            humor_level="moderate",
            example_preference="historical and classical analogies"
        ),
        voice=VoiceConfig(
            provider="google",
            voice_id="en-US-Journey-D", # Deep, professorial
            stability=0.5,
            similarity_boost=0.75
        ),
        script_config=ScriptConfig(
            max_section_length=600,
            question_frequency="medium"
        )
    ),
    "dr-straightforward-001": Agent(
        agent_id="dr-straightforward-001",
        name="Dr. Straightforward",
        description="Direct, no-nonsense, efficient",
        system_prompt="You are Dr. Straightforward. You value efficiency and clarity above all else. You explain concepts directly, using bullet points and clear definitions. You do not use fluff or unnecessary metaphors. Stick strictly to the provided material.",
        personality=AgentPersonality(
            traits=["precise", "clear", "efficient", "focused"],
            teaching_style="Direct instruction with clear definitions and logical flow",
            tone="Professional and concise",
            humor_level="low",
            example_preference="technical and practical examples"
        ),
        voice=VoiceConfig(
            provider="google",
            voice_id="en-US-Neural2-J", # Crisp, direct
            stability=0.4,
            similarity_boost=0.8
        ),
        script_config=ScriptConfig(
            max_section_length=400,
            include_examples=True,
            example_count=1,
            use_questions=False
        )
    ),
    "coach-motivator-001": Agent(
        agent_id="coach-motivator-001",
        name="Coach Motivator",
        description="Encouraging, enthusiastic, practical",
        system_prompt="You are Coach Motivator. You are high-energy, supportive, and practical. You frame every concept as a challenge to be mastered. You use sports analogies and real-world applications. You believe in the student's potential.",
        personality=AgentPersonality(
            traits=["enthusiastic", "supportive", "energetic", "practical"],
            teaching_style="Encourages the learner, frames challenges as opportunities",
            tone="High energy and motivational",
            humor_level="moderate",
            example_preference="sports and real-world application analogies"
        ),
        voice=VoiceConfig(
            provider="google",
            voice_id="en-US-Studio-M", # Energetic
            speaking_rate=1.1
        ),
        script_config=ScriptConfig(
            max_section_length=500,
            question_frequency="high"
        )
    ),
    "lit-reviewer-001": Agent(
        agent_id="lit-reviewer-001",
        name="Dr. Aris",
        description="Scholarly literary critic for fiction analysis",
        system_prompt="You are Dr. Aris, a scholarly literary critic. You analyze texts through a lens of narrative structure, symbolism, and character development. When analyzing fiction, you RESPECT THE NARRATIVE and do not treat it as historical fact unless explicitly stated. You focus on the 'why' and 'how' of the story.",
        personality=AgentPersonality(
            traits=["scholarly", "analytical", "eloquent", "nuanced"],
            teaching_style="Deep literary analysis focusing on themes, narrative structure, character development, and symbolism",
            tone="Academic, thoughtful, and critical",
            humor_level="low",
            example_preference="comparisons to other literary works and historical context"
        ),
        voice=VoiceConfig(
            provider="google",
            voice_id="en-GB-Neural2-D", # British academic sounding
            stability=0.6,
            speaking_rate=0.95
        ),
        script_config=ScriptConfig(
            max_section_length=700,
            include_examples=True,
            example_count=3,
            difficulty_adaptation=False, # Maintain high level
            use_questions=True,
            question_frequency="low"
        )
    )
}

def get_agent(agent_id: str) -> Agent:
    # 1. Check built-in agents first (fastest)
    if agent_id in AGENTS:
        return AGENTS[agent_id]
        
    # 2. Check Firestore for dynamic agents
    try:
        # Use a localized client to avoid global scope issues if not init
        from google.cloud import firestore # Lazy import
        db = firestore.Client()
        doc = db.collection('agents').document(agent_id).get()
        
        if doc.exists:
            data = doc.to_dict()
            
            # Reconstruct Agent object from Dict
            return Agent(
                agent_id=data.get('agentId', agent_id),
                name=data.get('name', 'Unknown Agent'),
                description=data.get('description', ''),
                personality=AgentPersonality(
                    traits=data.get('personality', {}).get('traits', []),
                    teaching_style=data.get('personality', {}).get('teaching_style', ''),
                    tone=data.get('personality', {}).get('tone', ''),
                    humor_level=data.get('personality', {}).get('humor_level', 'moderate'),
                    example_preference=data.get('personality', {}).get('example_preference', '')
                ),
                voice=VoiceConfig(
                    provider=data.get('voice', {}).get('provider', 'elevenlabs'),
                    voice_id=data.get('voice', {}).get('voice_id', ''),
                    stability=data.get('voice', {}).get('stability', 0.5),
                    similarity_boost=data.get('voice', {}).get('similarity_boost', 0.75),
                    style=data.get('voice', {}).get('style', 0.0),
                    speaking_rate=data.get('voice', {}).get('speaking_rate', 1.0)
                ),
                script_config=ScriptConfig(
                    max_section_length=data.get('script_config', {}).get('max_section_length', 500),
                    include_examples=data.get('script_config', {}).get('include_examples', True),
                    example_count=data.get('script_config', {}).get('example_count', 2),
                    difficulty_adaptation=data.get('script_config', {}).get('difficulty_adaptation', True),
                    use_questions=data.get('script_config', {}).get('use_questions', True),
                    question_frequency=data.get('script_config', {}).get('question_frequency', 'medium')
                )
            )
            
    except Exception as e:
        print(f"Warning: Failed to fetch dynamic agent {agent_id}: {e}")
    
    # 3. Fallback
    print(f"Agent {agent_id} not found, using default.")
    return AGENTS["prof-classics-001"]
