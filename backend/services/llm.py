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
