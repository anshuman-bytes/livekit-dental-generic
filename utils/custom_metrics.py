import logging
from typing import List
from utils.turn_collector import Turn
from constants.constants import MIN_ENDPOINTING_DELAY

logger = logging.getLogger("smiledesk-agent")
logger.setLevel(logging.INFO)


def calculate_user_to_agent_latency(
    all_turns: List[Turn], min_endpointing_delay: float = MIN_ENDPOINTING_DELAY
) -> float:
    """
    Calculate average User->Agent latency in seconds, ignoring function-call messages.

    The all_turns is assumed to be a list of Turn objects with the fields:
        - role: str         # e.g. "Main Agent", "Testing Agent"
        - start_time: float
        - end_time: float

    Steps:
    1. Filter out function-call messages (keep only user and agent messages).
    2. Sort by start_time (if not already sorted).
    3. Merge consecutive messages from the same role into one combined "turn."
    4. For each user->agent transition, measure the gap between the user's end_time
       and the agent's start_time (clamp negative values to 0).
    5. Return the average of these gaps. If no user->agent transitions exist, return 0.
    """
    logger.info(f"Calculating user->agent latency for {all_turns} turns")

    try:
        # Roles for clarity
        USER_ROLE = "Main Agent"
        AGENT_ROLE = "Testing Agent"

        # 1. Filter out function calls
        filtered = [turn for turn in all_turns if turn.role in (USER_ROLE, AGENT_ROLE)]

        logger.info(f"Filtered: {filtered}")

        if not filtered:
            return 0.0  # No user or agent messages at all

        # 2. Sort by start_time to ensure chronological order
        filtered.sort(key=lambda x: x.start_time)

        # 3. Merge consecutive messages from the same role
        merged_turns = []
        current_turn = None

        for turn in filtered:
            if current_turn is None:
                # Start a new turn
                current_turn = {
                    "role": turn.role,
                    "start_time": turn.start_time,
                    "end_time": turn.end_time,
                }
            else:
                # If same role, extend the current turn
                if turn.role == current_turn["role"]:
                    current_turn["end_time"] = turn.end_time
                else:
                    # Different speaker: push the old turn and start a new one
                    merged_turns.append(current_turn)
                    current_turn = {
                        "role": turn.role,
                        "start_time": turn.start_time,
                        "end_time": turn.end_time,
                    }

        # Append the last turn if it exists
        if current_turn:
            merged_turns.append(current_turn)

        # 4. Compute latencies for every user->agent boundary
        latencies = []
        for i in range(len(merged_turns) - 1):
            this_turn = merged_turns[i]
            next_turn = merged_turns[i + 1]

            # Check for user->agent transition
            if this_turn["role"] == USER_ROLE and next_turn["role"] == AGENT_ROLE:
                gap = next_turn["start_time"] - this_turn["end_time"]
                latencies.append(gap if gap > 0 else 0.0)

        # 5. Calculate average (handle empty case safely)
        if len(latencies) == 0:
            return 0.0
        result = sum(latencies) / len(latencies)
        result += min_endpointing_delay
        return result
    except Exception as e:
        logger.error(f"Error calculating user->agent latency: {e}")
        return 0.0


def calculate_average_from_list_of_floats(list_of_floats: list[float]) -> float:
    filtered_list_of_floats = [x for x in list_of_floats if x > 0]
    filtered_len = len(filtered_list_of_floats)
    try:
        return sum(filtered_list_of_floats) / filtered_len
    except Exception as e:
        print(f"Error calculating average from list of floats: {e}")
        return 0
