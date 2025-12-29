import logging
import aiohttp
from livekit.rtc import Participant, ParticipantKind
from prompts.prompt_manager import format_prompt

logger = logging.getLogger("smiledesk-agent")


def get_system_prompt(
    system_prompt: str, phone_number: bool, existing_patient: bool
) -> str:
    prompt = format_prompt(
        system_prompt,
        {
            "phone_number": phone_number,
            "existing_patient": existing_patient,
        },
    )
    return prompt


def check_if_phone_number_is_uk_mobile_number(phone_number: str) -> bool:
    """Check if the phone number is a UK mobile number."""
    return phone_number.startswith("+447")


def get_phone(participant: Participant) -> str:
    phone = None
    if participant.kind == ParticipantKind.PARTICIPANT_KIND_SIP:
        logger.info(f"all_attributes: {participant.attributes}")
        phone = participant.attributes["sip.phoneNumber"]
        logger.info(f"Phone: {phone}")

    return phone


def format_slack_message(recording_url: str, room_name: str, user_id: str) -> dict:
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":slack_call: AI Agent Call Summary  - {room_name} | {user_id}",
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":video_camera: View Recording",
                            "emoji": True,
                        },
                        "url": f"{recording_url}",
                    }
                ],
            },
        ]
    }


async def send_slack_message(
    webhook_url: str, recording_url: str, room_name: str, user_id: str
) -> None:
    """Send formatted message to Slack webhook."""
    try:
        async with aiohttp.ClientSession() as session:
            message = format_slack_message(recording_url, room_name, user_id)
            async with session.post(webhook_url, json=message) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to send message to Slack. Status: {response.status}"
                    )
                    logger.error(await response.text())
                else:
                    logger.info("Successfully sent metrics to Slack")
    except Exception as e:
        logger.error(f"Error sending message to Slack: {e}")
