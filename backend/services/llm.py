import os
import json
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from backend.models import CardType

# Ensure .env is loaded
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Initialize OpenAI LLM
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("[LLM WARNING] No OPENAI_API_KEY found in environment")
    llm = None
else:
    print(f"[LLM] OpenAI API key loaded successfully")
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7, api_key=api_key)


def generate_qa_cards_from_text(text: str, max_cards: int = 10) -> List[Dict]:
    """
    Use AI to identify key concepts in text and generate Q&A flashcards.

    Args:
        text: The document text to analyze
        max_cards: Maximum number of cards to generate (default 10)

    Returns:
        List of card dictionaries with 'question', 'answer', 'topic', and 'difficulty'
    """
    if not llm:
        print("[LLM] OpenAI API not configured, using fallback")
        return []

    if not text or len(text.strip()) < 100:
        print("[LLM] Text too short for AI analysis")
        return []

    try:
        # Truncate text to avoid token limits (keep first 4000 chars)
        text_excerpt = text[:4000]

        prompt = f"""You are an expert educational content creator. Analyze the following text and create {max_cards} important study questions.

For EACH question:
1. Identify a KEY CONCEPT that students must understand
2. Create a clear, specific QUESTION (not too long, 10-30 words)
3. Write a concise ANSWER (1-2 sentences, 20-50 words)
4. Assign a DIFFICULTY (easy, medium, or hard based on concept complexity)
5. Identify the TOPIC/CONCEPT NAME (2-4 words)

Text to analyze:
{text_excerpt}

Return ONLY a valid JSON array with NO additional text. Format:
[
  {{"question": "What is...", "answer": "It is...", "topic": "Concept Name", "difficulty": "easy"}},
  {{"question": "How does...", "answer": "It works by...", "topic": "Process Description", "difficulty": "medium"}}
]

IMPORTANT:
- Return ONLY the JSON array
- Ensure valid JSON syntax
- Create exactly {max_cards} cards
- Make questions require knowledge of the text
"""

        print(f"[LLM] Generating {max_cards} Q&A cards using GPT-3.5...")
        response = llm.invoke(prompt)

        # Parse the response
        response_text = response.content.strip()

        # Try to extract JSON from the response
        try:
            # Find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                cards = json.loads(json_str)
            else:
                print(f"[LLM] Could not find JSON array in response")
                return []
        except json.JSONDecodeError as e:
            print(f"[LLM] Failed to parse JSON response: {e}")
            return []

        # Validate and normalize cards
        validated_cards = []
        for i, card in enumerate(cards):
            if isinstance(card, dict) and 'question' in card and 'answer' in card:
                validated_cards.append({
                    'question': str(card.get('question', '')).strip(),
                    'answer': str(card.get('answer', '')).strip(),
                    'topic': str(card.get('topic', f'Concept {i+1}')).strip()[:50],
                    'difficulty': str(card.get('difficulty', 'medium')).lower()
                })

        print(f"[LLM] Successfully generated {len(validated_cards)} cards")
        return validated_cards

    except Exception as e:
        print(f"[LLM ERROR] Failed to generate cards: {e}")
        import traceback
        traceback.print_exc()
        return []


def grade_answer(question: str, correct_answer: str, student_answer: str) -> dict:
    """
    Temporary fake grader for student answers.

    Rules:
    - score = 0 if student answer is empty
    - score = 3 if student answer (lowercased) contains the correct answer text
    - otherwise score = 1

    Returns:
        dict: {"score": int, "explanation": str}
    """
    student_answer_lower = student_answer.strip().lower()
    correct_answer_lower = correct_answer.strip().lower()

    if not student_answer_lower:
        return {
            "score": 0,
            "explanation": "No answer provided."
        }

    if correct_answer_lower in student_answer_lower:
        return {
            "score": 3,
            "explanation": "Great! Your answer contains the key information."
        }

    return {
        "score": 1,
        "explanation": "Your answer is partially correct, but missing key details."
    }
