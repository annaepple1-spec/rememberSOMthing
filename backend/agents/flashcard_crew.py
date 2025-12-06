"""
Multi-agent CrewAI pipeline for generating high-quality flashcards from documents.

This module defines:
- 3 agents: Study Guide Architect, Flashcard Author, QA & Curriculum Designer
- 4 tasks: topic outlining, concept enrichment, flashcard generation, QA/ordering
- Main entry point: run_flashcard_agent_pipeline()
"""
import json
import os
from typing import Any, Dict

from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI


# ---------------------------------------------------------
# AGENTS
# ---------------------------------------------------------

def _build_study_guide_agent() -> Agent:
    """
    Agent 1: Study Guide Architect
    Analyzes document structure and creates outline with topics/concepts.
    """
    return Agent(
        role="Study Guide Architect",
        goal=(
            "Analyze a document and produce a structured study guide: "
            "identify key topics, break them into core concepts, "
            "and note difficulty/importance."
        ),
        backstory=(
            "You are an expert educator and curriculum designer with decades of experience "
            "transforming complex documents into clear, learner-friendly study guides. "
            "You understand how to chunk information into digestible topics and concepts."
        ),
        verbose=True,
        allow_delegation=False,
        llm=ChatOpenAI(model="gpt-4o", temperature=0.2),
    )


def _build_flashcard_agent() -> Agent:
    """
    Agent 2: Flashcard Author
    Creates diverse flashcards (definition, cloze, application, MCQ) from concepts.
    """
    return Agent(
        role="Flashcard Author",
        goal=(
            "Generate high-quality flashcards from a study guide's concepts. "
            "Create multiple card types (definition, cloze, application, MCQ) "
            "to ensure comprehensive coverage and varied practice."
        ),
        backstory=(
            "You are a master flashcard creator who understands spaced repetition, "
            "active recall, and cognitive science. You craft questions that are clear, "
            "concise, and effective for long-term retention."
        ),
        verbose=True,
        allow_delegation=False,
        llm=ChatOpenAI(model="gpt-4o", temperature=0.3),
    )


def _build_qa_agent() -> Agent:
    """
    Agent 3: QA & Curriculum Designer
    Reviews flashcard deck for quality, assigns difficulty, and orders cards.
    """
    return Agent(
        role="QA & Curriculum Designer",
        goal=(
            "Review the generated flashcard deck for quality, coverage, and ordering. "
            "Assign difficulty levels and create a logical progression from easy to hard."
        ),
        backstory=(
            "You are a meticulous quality assurance specialist and instructional designer. "
            "You ensure flashcard decks have proper coverage, no duplicates, appropriate "
            "difficulty ratings, and a pedagogically sound learning sequence."
        ),
        verbose=True,
        allow_delegation=False,
        llm=ChatOpenAI(model="gpt-4o", temperature=0.1),
    )


# ---------------------------------------------------------
# TASKS
# ---------------------------------------------------------

def _build_tasks(
    study_guide_agent: Agent,
    flashcard_agent: Agent,
    qa_agent: Agent,
) -> Dict[str, Task]:
    """
    Builds the 4 sequential tasks for the flashcard generation pipeline.
    """
    
    topic_outline_task = Task(
        description=(
            "Step 1: Define 4–8 Macro Topics and their Micro Topics (concept groups).\n\n"
            "CRITICAL: Slides may be fragmented; SYNTHESIZE and INTERPRET. Avoid project/assignment items.\n\n"
            "Document: {{document_title}}\n"
            "Content: {{document_text}}\n\n"
            "Macro topics should align with SCM operations such as: 'MRP', 'Aggregate Planning', 'Lot Sizing', 'Independent vs Dependent Demand'.\n"
            "Under each macro, list 3–7 Micro Topics (e.g., for MRP: 'MRP Process', 'BOM Structure', 'Inventory Optimization', 'Customer Satisfaction').\n\n"
            "EXCLUDE any items that are student project options, assignments, proposals, or deliverables.\n\n"
            "Return ONLY valid JSON with this schema:\n"
            "{\n"
            '  "document_title": "{{document_title}}",\n'
            '  "macros": [\n'
            '    {"name": "MRP", "micros": [{"name": "MRP Process"}, {"name": "BOM Structure"}, {"name": "Inventory Optimization"}, {"name": "Customer Satisfaction"}]},\n'
            '    {"name": "Aggregate Planning", "micros": [{"name": "Chase Strategy"}, {"name": "Level Strategy"}]}\n'
            '  ]\n'
            "}\n\n"
            "NO markdown fences. Pure JSON only."
        ),
        expected_output="JSON with document_title and macros[].micros[] representing macro/micro topics, excluding project items.",
        agent=study_guide_agent,
        name="Macro/Micro Outline Task",
    )

    concept_enrichment_task = Task(
        description=(
            "Step 2: For each Micro Topic, identify 2–6 core concepts with definitions, key points, and difficulty.\n\n"
            "Input: JSON from Step 1 with macros[].micros[] and the original document_text.\n\n"
            "Output: SAME structure extended with 'concepts' under each micro:\n"
            "{\n"
            '  "document_title": "...",\n'
            '  "macros": [\n'
            '    {"name": "MRP", "micros": [\n'
            '      {"name": "MRP Process", "concepts": [\n'
            '        {"name": "Master Production Schedule", "definition": "...", "key_points": ["..."], "difficulty": "easy|medium|hard"}\n'
            '      ]}\n'
            '    ]}\n'
            '  ]\n'
            "}\n\n"
            "Rules:\n"
            "- Focus on crucial concepts; avoid project/assignment items.\n"
            "- Keep language concise and grounded to the document.\n"
            "- RESPOND WITH JSON ONLY."
        ),
        expected_output="JSON with macros[].micros[].concepts[] enriched.",
        agent=study_guide_agent,
        name="Concept Enrichment Task",
    )

    flashcard_generation_task = Task(
        description=(
            "Step 3: Generate high-quality, exam-ready flashcards per concept under the correct Micro Topic.\n\n"
            "CRITICAL: Create flashcards that test UNDERSTANDING, not memorization of random text fragments.\n\n"
            "Input: Study guide JSON with macros[].micros[].concepts[].\n\n"
            "For EACH concept, create 3-6 flashcards with these types:\n"
            "1. 'definition' - Test core understanding\n"
            "   - front: 'What is [concept]?' or 'Define [concept]'\n"
            "   - back: Clear, complete definition (1-2 sentences)\n\n"
            "2. 'cloze' - Test key details with fill-in-blank\n"
            "   - front: Statement with ONE blank (use _____ for blank)\n"
            "   - back: The missing word/phrase only\n\n"
            "3. 'application' - Test real-world understanding\n"
            "   - front: 'How would you...?' or 'Why is... important?'\n"
            "   - back: Practical explanation showing understanding\n\n"
            "4. 'mcq' - Test recognition and discrimination\n"
            "   - front: Clear question\n"
            "   - options: Array of 4 plausible choices\n"
            "   - correct_option_index: Index (0-3) of correct answer\n"
            "   - back: Not used for MCQ\n\n"
            "BAD Examples (DO NOT CREATE THESE):\n"
            "❌ Q: 'Summarize this section in one sentence'\n"
            "❌ A: 'requirements planning system: • Creates schedules identifying...'\n"
            "❌ Q: 'What are the key concepts in this section?'\n\n"
            "GOOD Examples:\n"
            "✓ Q: 'What is Material Requirements Planning (MRP)?'\n"
            "✓ A: 'A system that calculates materials and components needed to manufacture products based on the master production schedule.'\n\n"
            "✓ Q: 'MRP determines order release dates based on _____.'\n"
            "✓ A: 'lead times'\n\n"
            "✓ Q: 'Why would a company use a Chase Strategy instead of Level Strategy?'\n"
            "✓ A: 'To minimize inventory holding costs and respond quickly to demand changes, despite higher hiring/firing costs.'\n\n"
            "Return JSON with flashcards added to each concept, preserving macro/micro nesting:\n"
            "{\n"
            '  "document_title": "...",\n'
            '  "macros": [\n'
            '    {"name": "...", "micros": [\n'
            '      {"name": "...", "concepts": [\n'
            '        {"name": "...", "definition": "...", "key_points": [...], "difficulty": "easy|medium|hard", "flashcards": [{"type": "definition", "front": "...", "back": "..."}]}\n'
            '      ]}\n'
            '    ]}\n'
            '  ]\n'
            "}\n\n"
            "Rules:\n"
            "- One idea per card. Keep fronts short.\n"
            "- Variation: at least 1 definition, 1 cloze, 1 application per concept when possible.\n"
            "- MCQ distractors should be plausible.\n"
            "- DO NOT generate flashcards for student projects/assignments/options.\n"
            "- RESPOND WITH JSON ONLY."
        ),
        expected_output="Study guide JSON with macros[].micros[].concepts[].flashcards[] added.",
        agent=flashcard_agent,
        name="Flashcard Generation Task",
    )

    qa_and_ordering_task = Task(
        description=(
            "Step 4: QA and ordering.\n\n"
            "Input:\n"
            "- A full deck JSON: document_title, macros[].micros[].concepts[] and flashcards[].\n\n"
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
            "- Reject and remove any items that are student project options, assignments, proposals, or deliverables.\n"
            "- Ensure every flashcard remains under a defined micro → macro.\n"
            "- RESPOND WITH JSON ONLY."
        ),
        expected_output=(
            "Final deck JSON with macro/micro grouping and difficulty/order fields per flashcard, excluding project items."
        ),
        agent=qa_agent,
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

    print(f"[CREW] Result type: {type(result)}")
    print(f"[CREW] Result attributes: {dir(result)}")
    
    # CrewAI returns a CrewOutput object. Try to access the actual output.
    # Try common attributes: .raw, .output, .json_output, or just convert to string
    result_data = None
    if hasattr(result, 'raw'):
        result_data = result.raw
        print(f"[CREW] Using result.raw, type: {type(result_data)}")
    elif hasattr(result, 'output'):
        result_data = result.output
        print(f"[CREW] Using result.output, type: {type(result_data)}")
    elif hasattr(result, 'json_output'):
        result_data = result.json_output
        print(f"[CREW] Using result.json_output, type: {type(result_data)}")
    else:
        # Fallback to string conversion
        result_data = str(result)
        print(f"[CREW] Using str(result)")
    
    # If it's already a dict, return it
    if isinstance(result_data, dict):
        return result_data

    # If it's a string, parse it
    if isinstance(result_data, str):
        # Remove markdown code fences if present
        result_str = result_data.strip()
        if result_str.startswith("```json"):
            result_str = result_str[7:]  # Remove ```json
        elif result_str.startswith("```"):
            result_str = result_str[3:]  # Remove ```
        if result_str.endswith("```"):
            result_str = result_str[:-3]  # Remove trailing ```
        result_str = result_str.strip()
        
        print(f"[CREW] Parsing JSON, first 200 chars: {result_str[:200]}")
        
        try:
            parsed = json.loads(result_str)
            print(f"[CREW] Successfully parsed JSON with {len(parsed.get('topics', []))} topics")
            return parsed
        except json.JSONDecodeError as e:
            print(f"[CREW] JSON parse error: {e}")
            # If it's not valid JSON, wrap it into a minimal structure
            return {
                "document_title": title,
                "topics": [],
                "raw_text": document_text,
                "raw_agent_output": result_str,
            }
    
    # Fallback for unknown type
    return {
        "document_title": title,
        "topics": [],
        "raw_text": document_text,
        "raw_agent_output": str(result_data),
    }

    # Fallback: empty deck + raw
    return {
        "document_title": title,
        "topics": [],
        "raw_text": document_text,
        "raw_agent_output": str(result),
    }
