from dataclasses import dataclass
from collections import deque
import time
from datetime import datetime
from typing import Deque, Optional
from enum import Enum


class Role(Enum):
    MAIN_AGENT = "Main Agent"
    TESTING_AGENT = "Testing Agent"


@dataclass
class Turn:
    role: str
    start_time: float
    end_time: float
    time: int
    start_time_human_readable: str
    end_time_human_readable: str

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def is_valid(self) -> bool:
        return self.duration >= 0


class TurnCollector:
    def __init__(self, global_start_time: float):
        self.turns: Deque[Turn] = deque()
        self._current_user_start_time: Optional[float] = None
        self._last_user_stop_time: Optional[float] = None
        self._current_agent_start_time: Optional[float] = None
        self._is_user_speaking: bool = False
        self._is_agent_speaking: bool = False
        self._last_event_time: float = time.time()
        self._global_start_time: float = global_start_time

    @property
    def global_start_time(self) -> float:
        return self._global_start_time

    def handle_event(self, event: str) -> None:
        current_time = time.time()

        # Validate event timing
        if current_time < self._last_event_time:
            raise ValueError("Events must be processed in chronological order")

        self._last_event_time = current_time

        if event == "user_started_speaking":
            # Always capture first start time if none exists
            if self._current_user_start_time is None:
                self._current_user_start_time = current_time
            self._is_user_speaking = True

        elif event == "user_stopped_speaking":
            if self._is_user_speaking:
                self._last_user_stop_time = current_time
            self._is_user_speaking = False

        elif event == "agent_started_speaking":
            # Complete user turn if exists
            self._complete_user_turn()

            # Only start new agent turn if not already speaking
            if not self._is_agent_speaking:
                self._current_agent_start_time = current_time
                self._is_agent_speaking = True

        elif event == "agent_stopped_speaking":
            if self._is_agent_speaking and self._current_agent_start_time is not None:
                self._complete_agent_turn(current_time)
                self._reset_agent_state()

        elif event == "user_speech_committed":
            # Complete user turn if exists, using the last stop time before this event
            self._complete_user_turn()

    def _reset_agent_state(self) -> None:
        self._is_agent_speaking = False
        self._current_agent_start_time = None

    def _reset_user_state(self) -> None:
        self._is_user_speaking = False
        self._current_user_start_time = None
        self._last_user_stop_time = None

    def _complete_user_turn(self) -> None:
        if (
            self._current_user_start_time is not None
            and self._last_user_stop_time is not None
        ):
            turn = Turn(
                role=Role.MAIN_AGENT.value,
                start_time=self._current_user_start_time,
                end_time=self._last_user_stop_time,
                time=time.strftime(
                    "%H:%M:%S", time.gmtime(time.time() - self._global_start_time)
                ),
                start_time_human_readable=datetime.fromtimestamp(
                    self._current_user_start_time
                ).strftime("%Y-%m-%d %H:%M:%S.%f"),
                end_time_human_readable=datetime.fromtimestamp(
                    self._last_user_stop_time
                ).strftime("%Y-%m-%d %H:%M:%S.%f"),
            )
            if turn.is_valid():
                self.turns.append(turn)
            self._reset_user_state()

    def _complete_agent_turn(self, end_time: float) -> None:
        if self._current_agent_start_time is not None:
            turn = Turn(
                role=Role.TESTING_AGENT.value,
                start_time=self._current_agent_start_time,
                end_time=end_time,
                time=time.strftime(
                    "%H:%M:%S", time.gmtime(time.time() - self._global_start_time)
                ),
                start_time_human_readable=datetime.fromtimestamp(
                    self._current_agent_start_time
                ).strftime("%Y-%m-%d %H:%M:%S.%f"),
                end_time_human_readable=datetime.fromtimestamp(end_time).strftime(
                    "%Y-%m-%d %H:%M:%S.%f"
                ),
            )
            if turn.is_valid():
                self.turns.append(turn)

    def get_turns(self) -> list[Turn]:
        return list(self.turns)

    def get_last_turn(self) -> Optional[Turn]:
        return self.turns[-1] if self.turns else None
