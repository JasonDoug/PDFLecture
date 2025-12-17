import os
from dataclasses import dataclass
# from google.cloud import firestore <--- Removed top-level import

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

# Define built-in agents
AGENTS = {
    "prof-classics-001": Agent(
        agent_id="prof-classics-001",
        name="Professor Classics",
        description="Witty, Socratic, uses analogies",
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
