import os
import logging

from livekit.agents import JobRequest

ENV_NAME = os.environ.get("ENV_NAME", "").lower()
logger = logging.getLogger("smiledesk-agent")


async def request(req: JobRequest):
    try:
        room_name = req.job.room.name

        if "smiledesk-agent" in room_name.lower():
            return await req.accept()

    except Exception as e:
        logger.error(f"Error rejecting job: {e}")
        return await req.reject()
