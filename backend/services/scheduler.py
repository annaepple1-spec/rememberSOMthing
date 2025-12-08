from datetime import datetime, timedelta
from backend.models import UserCardState


def update_card_state(state: UserCardState, score: int, now: datetime) -> None:
    """
    Update the user card state based on the score using SM-2 algorithm.

    Updates:
    - mastery: exponential moving average based on performance
    - spaced repetition scheduling (SM-2 style)
    - easiness factor
    - last_score, last_review_at, and next_due_at

    Args:
        state: The UserCardState to update
        score: The score from 0-3
        now: Current datetime
    """
    # Update mastery with exponential moving average
    performance = score / 3.0
    alpha = 0.3
    # Initialize mastery if it's None
    if state.mastery is None:
        state.mastery = 0.0
    state.mastery = (1 - alpha) * state.mastery + alpha * performance

    # Update easiness factor (SM-2 style)
    # q is the quality of the response (0-5 scale, we map 0-3 to 0-5)
    q = (score / 3.0) * 5.0
    # Initialize easiness if it's None
    if state.easiness is None:
        state.easiness = 2.5
    state.easiness = state.easiness + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))

    # Ensure easiness doesn't go below 1.3
    if state.easiness < 1.3:
        state.easiness = 1.3

    # Initialize repetitions and interval if they're None
    if state.repetitions is None:
        state.repetitions = 0
    if state.interval_days is None:
        state.interval_days = 1.0

    # Update spaced repetition scheduling based on score
    if score == 0:
        # Didn't know at all - reset to "new" status with immediate review (10 minutes)
        state.repetitions = 0
        state.interval_days = 10 / (24 * 60)  # 10 minutes in days (0.0069 days)
        state.easiness = max(1.3, state.easiness - 0.2)  # Penalize easiness
    elif score == 1:
        # Hard - short interval, needs more practice soon
        state.repetitions = 0
        state.interval_days = 1.0  # Review tomorrow
        state.easiness = max(1.3, state.easiness - 0.1)  # Slight penalty
    elif score == 2:
        # Good - normal spaced repetition progression
        state.repetitions += 1

        if state.repetitions == 1:
            state.interval_days = 3.0  # First success: 3 days
        elif state.repetitions == 2:
            state.interval_days = 7.0  # Second success: 1 week
        else:
            # Use previous interval * easiness
            state.interval_days = state.interval_days * state.easiness
    else:  # score == 3
        # Perfect - longer intervals, card is well mastered
        state.repetitions += 1

        if state.repetitions == 1:
            state.interval_days = 7.0  # First perfect: 1 week
        elif state.repetitions == 2:
            state.interval_days = 14.0  # Second perfect: 2 weeks
        else:
            # Use previous interval * (easiness + bonus for perfect score)
            state.interval_days = state.interval_days * (state.easiness + 0.3)

    # Update tracking fields
    state.last_score = score
    state.last_review_at = now
    state.next_due_at = now + timedelta(days=state.interval_days)
