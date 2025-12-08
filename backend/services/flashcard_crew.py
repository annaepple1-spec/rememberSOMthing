# backend/agents/flashcard_crew.py

"""
CrewAI multi-agent pipeline for generating flashcards from a document.

This defines:
- 3 Agents:
    * Study Guide Architect
    * Flashcard Author
    * QA & Curriculum Designer
- 4 Tasks:
    * Topic outlining
    * Concept enrichment
    * Flashcard generation
    * QA, coverage check, difficulty scoring & ordering

Main entrypoint:
    run_flashcard_agent_pipeline(document_text: str, title: str) -> dict

Expected output (deck) schema (high-level):

{
  "document_title": "<title>",
  "topics": [
    {
      "name": "Topic name",
      "summary": "Short description",
      "concepts": [
        {
          "name": "Concept name",
          "definition": "Short definition",
          "key_points": ["...", "..."],
          "flashcards": [
            {
              "id": "optional-card-id",
              "type": "definition" | "cloze" | "application" | "mcq",
              "front": "question / prompt",
              "back": "ideal answer or correct option",
              "options": [...],            # for mcq
              "correct_option_index": 1,   # for mcq
              "difficulty": "easy|medium|hard",  # optional
              "order": 1                           # optional
            }
          ]
        }
      ]
    }
  ]
}

The ingest service will turn this into Card ORM objects.
"""

import json
from typing import Any, Dict

from crewai import Agent, Task, Crew

# If you use LangChain / OpenAI:
# from langchain_openai import ChatOpenAI


# ---------------------------------------------------------
# LLM CONFIG (ADAPT TO YOUR SETUP)
# ---------------------------------------------------------

# Example with LangChain (uncomment and adapt):
# llm = ChatOpenAI(
#     model="gpt-4o-mini",
#     temperature=0.3,
# )

# For now, we can pass None and rely on CrewAI's default if configured globally.
llm = None


# ---------------------------------------------------------
# AGENT DEFINITIONS
# ---------------------------------------------------------

def _build_study_guide_agent() -> Agent:
    return Agent(
        role="Study Guide Architect",
        goal=(
            "Transform a raw document into a clear, hierarchical study guide with "
            "topics and concepts that are easy for students to learn from."
        ),
        backstory=(
            "You are an expert educator who can read complex lecture notes or papers "
            "and extract the most important topics and concepts. You think in terms "
            "of structure: topics, subtopics, definitions, and key bullet points."
        ),
        llm=llm,
        verbose=True,
    )


def _build_flashcard_agent() -> Agent:
    return Agent(
        role="Flashcard Author",
        goal=(
            "Create a rich set of flashcards that test understanding of each concept "
            "in multiple ways: definition, cloze, application, and MCQs."
        ),
        backstory=(
            "You are a pedagogy-focused content creator. You design flashcards that "
            "are short, clear, and test one idea at a time. You vary the style of "
            "questions to deepen learning."
        ),
        llm=llm,
        verbose=True,
    )


def _build_qa_agent() -> Agent:
    return Agent(
        role="QA & Curriculum Designer",
        goal=(
            "Check the deck for coverage and quality, then assign difficulty and "
            "ordering within each concept so students can progress from easy to hard."
        ),
        backstory=(
            "You are an experienced teacher who reviews all flashcards to ensure "
            "that each important concept is covered by enough cards, with a good "
            "mix of question types, and organized from easy to hard."
        ),
        llm=llm,
        verbose=True,
    )


# ---------------------------------------------------------
# TASK DEFINITIONS
# ---------------------------------------------------------

def _build_tasks(study_guide_agent: Agent,
                 flashcard_agent: Agent,
                 qa_agent: Agent) -> Dict[str, Task]:
    """
    Define the 4 main tasks. All tasks will receive `document_title` and `document_text`,
    and tasks build on the JSON produced by previous tasks.
    """

    topic_outline_task = Task(
        description=(
            "Step 1: Read the document.\n"
            "Title: {{document_title}}\n\n"
            "Your job is to identify the MAIN TOPICS of the document.\n\n"
            "Output a JSON object with:\n"
            "{\n"
            '  "document_title": "<title>",\n'
            '  "topics": [\n'
            '    {\n'
            '      "name": "Topic name",\n'
            '      "summary": "2–3 sentence summary of this topic",\n'
            '      "importance": "high|medium|low"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- 3–8 topics for most documents.\n"
            "- Use concise, student-friendly topic names.\n"
            "- DO NOT include concepts or flashcards yet.\n"
            "- RESPOND WITH JSON ONLY."
        ),
        expected_output="A JSON object with document_title and topics as specified.",
        agent=study_guide_agent,
        output_json=True,
        name="Topic Outlining Task",
    )

    concept_enrichment_task = Task(
        description=(
            "Step 2: Build a full study guide.\n\n"
            "You are given:\n"
            "- document_title\n"
            "- topics[] from the previous step\n"
            "- the full document text\n\n"
            "For EACH topic, populate a `concepts` array.\n\n"
            "For each concept, include:\n"
            "- name: short concept name\n"
            "- definition: 1–3 sentence student-friendly definition\n"
            "- key_points: list of 2–5 bullet points (short strings)\n"
            "- difficulty: 'easy' | 'medium' | 'hard' (relative within the document)\n\n"
            "Return a JSON object:\n"
            "{\n"
            '  "document_title": "...",\n'
            '  "topics": [\n'
            '    {\n'
            '      "name": "...",\n'
            '      "summary": "...",\n'
            '      "importance": "high|medium|low",\n'
            '      "concepts": [\n'
            '        {\n'
            '          "name": "...",\n'
            '          "definition": "...",\n'
            '          "key_points": ["...", "..."],\n'
            '          "difficulty": "easy|medium|hard"\n'
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Focus on *crucial* concepts, not every noun.\n"
            "- Keep language concise and understandable to a motivated student.\n"
            "- RESPOND WITH JSON ONLY."
        ),
        expected_output="A JSON study guide with topics and enriched concepts.",
        agent=study_guide_agent,
        output_json=True,
        name="Concept Enrichment Task",
    )

    flashcard_generation_task = Task(
        description=(
            "Step 3: Generate flashcards from the study guide.\n\n"
            "Input:\n"
            "- A study guide JSON: document_title, topics[], each with concepts[].\n\n"
            "For EACH concept, create a `flashcards` array with multiple cards.\n"
            "Aim for 4–8 cards per concept, including different types:\n"
            "- type: 'definition' | 'cloze' | 'application' | 'mcq'\n"
            "- front: the question text\n"
            "- back: the ideal short answer (or correct option text for MCQ)\n"
            "- options (MCQ only): array of 3–5 options\n"
            "- correct_option_index (MCQ only): index of correct option in 'options'\n\n"
            "Return the SAME structure as the study guide, but with flashcards added:\n"
            "{\n"
            '  "document_title": "...",\n'
            '  "topics": [\n'
            '    {\n'
            '      "name": "...",\n'
            '      "summary": "...",\n'
            '      "importance": "...",\n'
            '      "concepts": [\n'
            '        {\n'
            '          "name": "...",\n'
            '          "definition": "...",\n'
            '          "key_points": [...],\n'
            '          "difficulty": "easy|medium|hard",\n'
            '          "flashcards": [\n'
            '            {\n'
            '              "type": "definition",\n'
            '              "front": "...",\n'
            '              "back": "..." \n'
            "            }\n"
            "          ]\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- One idea per card. Keep fronts short.\n"
            "- Variation: at least 1 definition, 1 cloze, 1 application per concept when possible.\n"
            "- MCQ distractors should be plausible.\n"
            "- RESPOND WITH JSON ONLY."
        ),
        expected_output="Study guide JSON with flashcards[] added to each concept.",
        agent=flashcard_agent,
        output_json=True,
        name="Flashcard Generation Task",
    )

    qa_and_ordering_task = Task(
        description=(
            "Step 4: QA and ordering.\n\n"
            "Input:\n"
            "- A full deck JSON: document_title, topics[], each with concepts[] and flashcards[].\n\n"
            "Your goals:\n"
            "1. Check coverage: each concept should have at least 3 flashcards and at least "
            "   one non-definition card (cloze/application/mcq) if possible.\n"
            "2. Optionally remove or merge obvious duplicates.\n"
            "3. Assign a difficulty to EACH flashcard: 'easy' | 'medium' | 'hard'.\n"
            "   - Simple definition recall → easy\n"
            "   - Cloze or simple MCQ → medium\n"
            "   - Multi-step application scenarios → hard\n"
            "4. Add an 'order' field (integer) per flashcard within each concept such that:\n"
            "   - easy come first, then medium, then hard.\n"
            "   - Within each difficulty group, order can be arbitrary but stable.\n\n"
            "Return the SAME JSON structure but with added fields:\n"
            "- flashcards[].difficulty\n"
            "- flashcards[].order\n\n"
            "Rules:\n"
            "- You may slightly adjust or drop very low-quality cards.\n"
            "- Ensure every concept still has good coverage.\n"
            "- RESPOND WITH JSON ONLY."
        ),
        expected_output=(
            "Final deck JSON with difficulty and order fields for each flashcard."
        ),
        agent=qa_agent,
        output_json=True,
        name="QA & Ordering Task",
    )

    return {
        "topic_outline": topic_outline_task,
        "concept_enrichment": concept_enrichment_task,
        "flashcard_generation": flashcard_generation_task,
        "qa_ordering": qa_and_ordering_task,
    }


# ---------------------------------------------------------
# CREW + PIPELINE
# ---------------------------------------------------------

def _build_crew() -> Crew:
    study_guide_agent = _build_study_guide_agent()
    flashcard_agent = _build_flashcard_agent()
    qa_agent = _build_qa_agent()

    tasks = _build_tasks(
        study_guide_agent=study_guide_agent,
        flashcard_agent=flashcard_agent,
        qa_agent=qa_agent,
    )

    crew = Crew(
        agents=[study_guide_agent, flashcard_agent, qa_agent],
        tasks=[
            tasks["topic_outline"],
            tasks["concept_enrichment"],
            tasks["flashcard_generation"],
            tasks["qa_ordering"],
        ],
        verbose=True,
    )
    return crew


def run_flashcard_agent_pipeline(document_text: str, title: str) -> Dict[str, Any]:
    """
    Entry point used by the ingest service.

    - Builds the crew
    - Runs the 4-task pipeline
    - Returns the final deck JSON as a Python dict

    If anything fails, this function should raise or fall back to a simple structure
    that the ingest service can handle.
    """
    crew = _build_crew()

    # Inputs are available as {{document_title}} and {{document_text}} in task descriptions
    result = crew.kickoff(
        inputs={
            "document_title": title,
            "document_text": document_text,
        }
    )

    # CrewAI often returns the last task's output directly.
    # It might already be a dict if output_json=True, but we guard for strings.
    if isinstance(result, dict):
        return result

    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # If it's not valid JSON, wrap it into a minimal structure
            return {
                "document_title": title,
                "topics": [],
                "raw_text": document_text,
                "raw_agent_output": result,
            }

    # Fallback: empty deck + raw
    return {
        "document_title": title,
        "topics": [],
        "raw_text": document_text,
        "raw_agent_output": str(result),
    }
