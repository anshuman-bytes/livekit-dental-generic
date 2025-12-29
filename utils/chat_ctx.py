import time
from dataclasses import dataclass

from livekit.agents import ChatContext
from livekit.agents.voice.agent_activity import update_instructions


def build_transcription_without_prompts(
    all_items, include_fnc_call=True, include_fnc_call_output=True
):
    """
    Build a transcription from the chat history.
    """
    transcription = []
    for item in all_items:
        item_id = item.get("id", "")
        item_type = item.get("type", "message")
        if "lk." in item_id or "internal" in item_id:
            continue
        if not include_fnc_call and item_type == "function_call":
            continue
        if (
            not include_fnc_call or not include_fnc_call_output
        ) and item_type == "function_call_output":
            continue
        transcription.append(item)
    return transcription


def format_chat_ctx(
    base_chat_ctx: ChatContext,
    cleaned_chat_ctx: ChatContext,
    base_instructions: str,
    turns_additional_info: list,
) -> str:
    chat_ctx = base_chat_ctx.copy()
    # Update base instructions - As we change the Assistants
    update_instructions(
        chat_ctx,
        instructions=base_instructions,
        add_if_missing=True,
    )

    all_items = chat_ctx.to_dict()["items"]
    # cleaned_items = cleaned_chat_ctx.copy().to_dict()["items"]

    def _convert_content_to_text(items):
        for item in items:
            if item.get("content", None):
                if isinstance(item["content"], list):
                    string_items = [
                        item for item in item["content"] if isinstance(item, str)
                    ]
                    item["content"] = "\n".join(string_items)
        return items

    all_items = _convert_content_to_text(all_items)
    # cleaned_items = _convert_content_to_text(cleaned_items)
    cleaned_items = build_transcription_without_prompts(
        all_items=all_items, include_fnc_call=False, include_fnc_call_output=False
    )
    # Add start_time and end_time to the cleaned_items
    turns_dict = {turn["unique_id"]: turn for turn in turns_additional_info}
    for item in cleaned_items:
        turn = turns_dict.get(
            item["id"],
            {
                "start_time": None,
                "end_time": None,
            },
        )
        item["start_time"] = turn["start_time"]
        item["end_time"] = turn["end_time"]

    return all_items, cleaned_items


@dataclass
class Turn:
    unique_id: str
    role: str
    start_time: float | None
    end_time: float | None


class ChatContextInfo:
    def __init__(self):
        self._pending_speech_data = {
            "user": {"start_times": [], "end_times": []},
            "assistant": {"start_times": [], "end_times": []},
        }
        self._turns: list[Turn] = []

    @property
    def turns(self) -> list[Turn]:
        return self._turns

    def to_dict(self) -> dict:
        return {
            "turns": [item.__dict__ for item in self._turns],
        }

    def add_speech_time(
        self, role: str, start_time: float = None, end_time: float = None
    ):
        """Track speech times for a role before message is committed."""
        if role not in self._pending_speech_data:
            self._pending_speech_data[role] = {"start_times": [], "end_times": []}

        if start_time is not None:
            self._pending_speech_data[role]["start_times"].append(start_time)
        if end_time is not None:
            self._pending_speech_data[role]["end_times"].append(end_time)

    def _get_speech_times(self, role: str):
        """Get the first start time and last end time for a role."""
        if role not in self._pending_speech_data:
            return None, None

        start_times = self._pending_speech_data[role]["start_times"]
        end_times = self._pending_speech_data[role]["end_times"]

        start_time = min(start_times) if start_times else None
        end_time = max(end_times) if end_times else None

        return start_time, end_time

    def clear_pending_speech_data(self, role: str):
        """Clear the pending speech data for a role after it's been used."""
        if role in self._pending_speech_data:
            self._pending_speech_data[role] = {"start_times": [], "end_times": []}

    def add_turn(self, unique_id: str, role: str) -> Turn:
        start_time, end_time = self._get_speech_times(role)
        # Adding end time for turns because sometimes event is fired after the turn is committed
        if end_time is None:
            end_time = time.time()

        turn: Turn = Turn(
            unique_id=unique_id,
            role=role,
            start_time=start_time,
            end_time=end_time,
        )
        self._turns.append(turn)
        self.clear_pending_speech_data(role)
        return turn
