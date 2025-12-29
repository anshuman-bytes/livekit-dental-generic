import os
import logging

from livekit.agents import JobProcess
from livekit.plugins import silero

ENV_NAME = os.environ.get("ENV_NAME", "").lower()
logger = logging.getLogger("smiledesk-agent")


def prewarm(proc: JobProcess):
    # preload silero VAD in memory to speed up session start
    if ENV_NAME != "development":
        proc.userdata["vad"] = silero.VAD.load(
            min_silence_duration=0.15, min_speech_duration=0.02
        )
