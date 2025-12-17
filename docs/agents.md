# Agent System Documentation

The Agent System is the core personality engine of the PDF-to-Lecture service. It transforms dry analysis data into engaging, character-driven audio lectures.

## Core Concepts

### 1. Agent Persona
An agent is defined by its `AgentPersonality`, which dictates *how* it teaches. This includes:
- **Traits**: Keywords describing behavioral characteristics (e.g., "witty", "sarcastic").
- **Teaching Style**: The pedagogical approach (e.g., "Socratic method", "Direct instruction").
- **Tone**: The emotional quality of the voice and text.
- **Example Preference**: What kind of analogies the agent uses (e.g., "historical", "pop culture").

### 2. Script Configuration
Control how the lecture script is structured:
- `max_section_length`: Target word count per section.
- `include_examples`: Whether to insert generated examples.
- `use_questions`: Whether to use rhetorical questions.
- `question_frequency`: "low", "medium", or "high".

### 3. Voice Configuration
Settings for the TTS provider (currently ElevenLabs):
- `voice_id`: The unique ID of the voice model.
- `stability`: Consistenc vs. variability (lower = more emotional range).
- `similarity_boost`: How closely to stick to the original voice.

## Implementation Details

Located in `script_generator/agents.py`.

### Built-in Agents

#### Professor Classics (`prof-classics-001`)
*   **Vibe**: A beloved university professor who loves history.
*   **Style**: Uses high-quality analogies and Socratic questioning.
*   **Voice**: Stable, slightly dramatic.

#### Dr. Straightforward (`dr-straightforward-001`)
*   **Vibe**: Efficient, no-nonsense technical instructor.
*   **Style**: Pure information density, minimal fluff.
*   **Voice**: Crisp, professional, fast-paced.

#### Coach Motivator (`coach-motivator-001`)
*   **Vibe**: High-energy sports coach or motivational speaker.
*   **Style**: Frames learning as a challenge/workout.
*   **Voice**: Energetic, variable speed.

## Extending the System

To add a new agent, add an entry to the `AGENTS` dictionary in `script_generator/agents.py`:

```python
    "new-agent-id": Agent(
        agent_id="new-agent-id",
        name="Agent Name",
        description="Short description",
        personality=AgentPersonality(
            traits=["trait1", "trait2"],
            teaching_style="Description of style",
            tone="Description of tone",
            humor_level="low|moderate|high",
            example_preference="type of examples"
        ),
        voice=VoiceConfig(
            provider="elevenlabs",
            voice_id="VOICE_ID",
            stability=0.5
        ),
        script_config=ScriptConfig(
            max_section_length=500
        )
    )
```
