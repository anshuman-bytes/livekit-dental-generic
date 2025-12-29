import logging
import requests
import yaml
import os
import pytz
import asyncio
import time

from dataclasses import dataclass
from typing import Annotated, Literal, Optional
from dotenv import load_dotenv
from pydantic import Field

from constants.constants import (
    keyterms,
    MIN_ENDPOINTING_DELAY,
    MAX_ENDPOINTING_DELAY,
    MIN_INTERRUPTION_DURATION,
    MIN_INTERRUPTION_WORDS,
)

from utils.common import send_slack_message, check_if_phone_number_is_uk_mobile_number, get_phone, get_system_prompt
from utils.slack import get_slack_message_config, send_metrics_slack_notification
from utils.sentiment import analyze_sentiment

from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    AutoSubscribe,
    RoomInputOptions,
    metrics,
    MetricsCollectedEvent,
    get_job_context,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession, RunContext
from livekit.plugins import deepgram, openai, silero, elevenlabs
from livekit.plugins import noise_cancellation
from livekit import api
from livekit.plugins.turn_detector.english import EnglishModel
from utils.chat_ctx import (
    ChatContextInfo,
    format_chat_ctx,
    build_transcription_without_prompts,
)
from utils.turn_collector import TurnCollector
from livekit.agents.voice.events import (
    UserStateChangedEvent,
    ConversationItemAddedEvent,
    AgentStateChangedEvent,
)

from datetime import datetime
from agent_core.agent_factory import AgentFactory
from agent_core.prewarm import prewarm
from agent_core.request import request
from customer_context import (
    OrganizationContext,
    CustomerContext,  # Backward compatibility alias
    get_organization_name,
    get_customer_name,  # Backward compatibility alias
    get_recording_url,
    get_consultation_service_mapping,
)

logger = logging.getLogger("smiledesk-agent")
logger.setLevel(logging.INFO)

load_dotenv()

BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN")

patient_types = Literal["new", "existing"]
booking_types = Literal["private", "nhs"]
request_types = Literal["appointment_booking", "enquiry"]

# Note: consultation_service_mapping, consultation_types, service_ids, and preferred_doctor_ids
# are now loaded dynamically from org_config instead of being hardcoded
# This allows multi-tenant support where each organization can have their own consultation types and doctors

consultation_types = Literal[
    "general_consultation",
    "implant_consultation",
    "orthodontic_consultation",
    "whitening_consultation",
    "hygienist_consultation",
]


@dataclass
class UserData:
    patient_type: Optional[patient_types] = None
    booking_type: Optional[booking_types] = None
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    patient_dob: Optional[str] = None
    patient_relationship: Optional[str] = None
    slot_id: Optional[str] = None
    is_nhs: Optional[bool] = False
    consultation_type: Optional[consultation_types] = None
    patient_id: Optional[str] = None
    service_id: Optional[str] = None
    slot_day: Optional[str] = None
    slot_timing: Optional[str] = None
    request_type: Optional[str] = None
    is_user_phone_number_official_number: Optional[bool] = False
    original_phone_number: Optional[str] = None
    preferred_doctor_id: Optional[str] = "ANY-PROVIDER"  # Changed from Literal to str for flexibility
    preferred_doctor_name: Optional[str] = None

    # State variables
    is_in_booking_tool_call: Optional[bool] = False
    is_in_get_appointment_availability_tool_call: Optional[bool] = False
    room_name: Optional[str] = None
    session_id: Optional[str] = None
    agent_session: Optional[object] = None  # Store the AgentSession instance
    system_prompt: Optional[str] = None
    organization_context: Optional[object] = None  # Store OrganizationContext instance for multi-tenant support
    customer_context: Optional[object] = None  # Backward compatibility alias for organization_context
    call_outcome: Optional[str] = None  # Track call outcome: "booked", "callback_requested", "no_slots", "enquiry_only", "hung_up"

    def __str__(self) -> str:
        return f"""
        Patient Type: {self.patient_type}
        Booking Type: {self.booking_type}
        Patient First Name: {self.patient_first_name}
        Patient Last Name: {self.patient_last_name}
        Patient Phone: {self.patient_phone}
        Patient Email: {self.patient_email}
        Patient Relationship: {self.patient_relationship}
        Slot ID: {self.slot_id}
        Slot Day: {self.slot_day}
        Slot Timing: {self.slot_timing}
        Request Type: {self.request_type}
        """


RunContext_T = RunContext[UserData]
usage_collector = metrics.UsageCollector()


async def update_patient_id(
    patient_id: Annotated[str, Field(description="The patient id")],
    context: RunContext_T,
) -> str:
    userdata = context.userdata
    userdata.patient_id = patient_id


async def register_callback_request(
    context: RunContext_T,
) -> str:
    userdata = context.userdata
    endpoint = f"{os.getenv('BACKEND_API')}/register-other-requests"
    headers = {"Authorization": f"Bearer {BACKEND_API_TOKEN}"}

    # Use organization-specific recording URL from organization_context
    org_context = userdata.organization_context or userdata.customer_context  # Backward compatibility
    recording_url = get_recording_url(org_context.config, userdata.room_name)

    data = {
        "phone": userdata.patient_phone,
        "request_type": "callback_request",
        "recording_url": recording_url,
        "session_id": userdata.session_id or None,
        "message": "AUTOMATICALLY_GENERATED_MESSAGE: No slots available",
    }
    response = requests.post(endpoint, json=data, headers=headers)
    logger.info(f"response: {response.json()}")
    
    # Auto-set outcome to "no_slots"
    userdata.call_outcome = "no_slots"
    logger.info("Call outcome: no_slots (auto-registered callback)")
    
    # Set outcome - no slots available, callback registered
    userdata.call_outcome = "no_slots"
    logger.info("Call outcome: no_slots")


@function_tool()
async def end_call(
    context: RunContext_T,
) -> None:
    """Call this tool when the user has no other further questions or user wants to end the call
    Confirm with the user regarding the further questions and only call this tool if the user says no further questions.
    """
    userdata = context.userdata
    try:
        if userdata.agent_session:
            # Use organization-specific practice name
            org_context = userdata.organization_context or userdata.customer_context  # Backward compatibility
            org_name = get_organization_name(org_context.config)
            await userdata.agent_session.say(
                f"Thank you for calling {org_name}. Have a great day!"
            )
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=job_ctx.room.name)
        )
    except Exception as e:
        logger.error(f"Error deleting room: {e}")
        job_ctx = get_job_context()
        job_ctx.shutdown()


@function_tool()
async def get_consultation_type(
    context: RunContext_T,
) -> str:
    """Call this tool when you need to access the consultation type"""
    userdata = context.userdata
    return userdata.consultation_type


@function_tool()
async def get_patient_type(
    context: RunContext_T,
) -> str:
    """Call this tool when you need to access the patient type"""
    userdata = context.userdata
    return userdata.patient_type


@function_tool()
async def update_preferred_doctor_with_name_and_id(
    preferred_doctor_name: Annotated[
        str, Field(description="The preferred doctor name")
    ],
    preferred_doctor_id: Annotated[
        str, Field(description="The preferred doctor id")
    ],
    context: RunContext_T,
) -> str:
    """Call this tool when you need to update the preferred doctor id"""
    userdata = context.userdata
    
    # Validate doctor ID against organization's available doctors (optional validation)
    # Skip validation if organization_context is not available or if it's ANY-PROVIDER
    org_context = userdata.organization_context or userdata.customer_context  # Backward compatibility
    if org_context and preferred_doctor_id != "ANY-PROVIDER":
        from customer_context import get_all_doctor_ids
        all_doctor_ids = get_all_doctor_ids(org_context.config)
        if all_doctor_ids and preferred_doctor_id not in all_doctor_ids:
            logger.warning(f"Doctor ID {preferred_doctor_id} not found in customer config, but proceeding anyway")
    
    userdata.preferred_doctor_id = preferred_doctor_id
    userdata.preferred_doctor_name = preferred_doctor_name
    return ""


@function_tool()
async def update_phone_number(
    phone_number: Annotated[
        str,
        Field(description="The phone number provided by the patient"),
    ],
    context: RunContext_T,
) -> str:
    """
    Call this tool when you need to update the phone number of the patient.
    Automatically formats UK mobile numbers with +447 prefix.
    """
    userdata = context.userdata

    # Clean the phone number (remove spaces, dashes, etc.)
    cleaned_number = (
        phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    )

    # Format the number to +447XXXXXXXXX format
    if cleaned_number.startswith("+447"):
        # Already in correct format
        formatted_number = cleaned_number
    elif cleaned_number.startswith("447"):
        # Missing the + sign
        formatted_number = "+" + cleaned_number
    elif cleaned_number.startswith("07") and len(cleaned_number) == 11:
        # UK mobile format 07XXXXXXXXX - convert to +447XXXXXXXXX
        formatted_number = "+44" + cleaned_number[1:]
    elif cleaned_number.startswith("7") and len(cleaned_number) == 10:
        # Just the mobile part 7XXXXXXXXX - add +44
        formatted_number = "+447" + cleaned_number[1:]
    else:
        # Invalid format
        return (
            "I need a valid UK mobile number. Please provide your mobile number again."
        )

    # Validate final format (should be exactly 13 characters)
    if len(formatted_number) != 13:
        return "Please provide a valid UK mobile number."

    # Store the formatted phone number
    userdata.patient_phone = formatted_number

    human_readable_phone_number = formatted_number.replace("+44", "0")
    # formatting should be xxxxx xxx xxx
    human_readable_phone_number = f"{human_readable_phone_number[:5]} {human_readable_phone_number[5:8]} {human_readable_phone_number[8:]}"

    return f"""
    Thank you, I have your number as `{human_readable_phone_number}`. Is this correct?

    ## Instructions:
    - If the patient says their number is correct, then you can proceed with the conversation.
    - If the patient says their number is incorrect, then you need to ask them to provide the correct number again and *must* call the tool `update_phone_number` again.
    """


@function_tool()
async def update_patient_dob(
    dob: Annotated[str, Field(description="patient's date of birth")],
    context: RunContext_T,
) -> str:
    """
    Call this tool when you need to update the patient's date of birth.
    Patient can say their date of birth in any format.
    You need to convert the patient's date of birth to DD-MM-YYYY format
    """
    userdata = context.userdata
    userdata.patient_dob = dob
    return "DOB updated, continue the conversation"


@function_tool()
async def get_current_date_and_time_in_uk(
    context: RunContext_T,
) -> str:
    """Call this tool when you need to get the current time or when you need to tell the patient the current time
    You can also use this tool to get the relative difference between the current date and the slot day (when user is checking the available slots)
    """
    date = datetime.now(pytz.timezone("Europe/London")).strftime("%d %B %Y")
    time = datetime.now(pytz.timezone("Europe/London")).strftime("%H:%M")
    return f"current date and time in UK is {date} at {time}"


@function_tool()
async def get_user_data(
    context: RunContext_T,
) -> str:
    """Use this tool to get the required user data and verify all the data is present"""
    userdata = context.userdata
    return f"Userdata: {userdata}"


@function_tool()
async def set_call_outcome(
    outcome: Annotated[
        Literal["booked", "callback_requested", "no_slots", "enquiry_only", "transferred", "user_hung_up"],
        Field(description="The outcome of the call")
    ],
    context: RunContext_T,
) -> str:
    """
    Set the outcome of the current call for analytics and tracking.
    This helps measure agent performance and customer satisfaction.
    
    Outcomes:
    - booked: Appointment successfully booked
    - callback_requested: Patient requested callback
    - no_slots: No available slots found
    - enquiry_only: Patient only asked questions, no booking needed
    - transferred: Call transferred to human agent
    - user_hung_up: User ended call early
    """
    userdata = context.userdata
    userdata.call_outcome = outcome
    logger.info(f"Call outcome set to: {outcome}")
    return ""


@function_tool()
async def set_call_outcome(
    outcome: Annotated[
        Literal["booked", "callback_requested", "no_slots", "enquiry_only", "transferred", "hung_up"],
        Field(description="The outcome of the call")
    ],
    context: RunContext_T,
) -> str:
    """
    Set the outcome of the current call for analytics and tracking.
    
    Outcomes:
    - booked: Appointment successfully booked
    - callback_requested: Patient requested callback
    - no_slots: No available slots found
    - enquiry_only: Patient only had questions, no booking
    - transferred: Call transferred to human
    - hung_up: Patient hung up during conversation
    """
    userdata = context.userdata
    userdata.call_outcome = outcome
    logger.info(f"Call outcome set to: {outcome}")
    return ""


@function_tool()
async def handle_callback_request_and_forward_message_to_team(
    context: RunContext_T,
    message: Annotated[
        str, Field(description="The message to forward to the team (if any)")
    ],
) -> str:
    """Call this tool when patient asks for a callback request or patient asks to forward the message to the team/reception
    Please inform the patient upfront that he needs to provide his name, Date of Birth and phone number within the message.
    Must **confirm** the message with patient once before calling the function.
    """
    userdata = context.userdata

    endpoint = f"{os.getenv('BACKEND_API')}/register-other-requests"
    headers = {"Authorization": f"Bearer {BACKEND_API_TOKEN}"}

    # Use organization-specific recording URL
    org_context = userdata.organization_context or userdata.customer_context  # Backward compatibility
    recording_url = get_recording_url(org_context.config, userdata.room_name)

    data = {
        "phone": userdata.patient_phone or userdata.original_phone_number,
        "request_type": "callback_request",
        "recording_url": recording_url,
        "session_id": userdata.session_id or None,
        "message": message or "No message provided",
    }
    response = requests.post(endpoint, json=data, headers=headers)
    logger.info(f"response: {response.json()}")
    
    # Set outcome - callback requested
    userdata.call_outcome = "callback_requested"
    logger.info("Call outcome: callback_requested")
    
    return "Message forwarded to the team, someone from the team will get back to you soon."


@function_tool()
async def update_request_type(
    request_type: Annotated[request_types, Field(description="The request type")],
    context: RunContext_T,
) -> str:
    """Call this tool when you diagnose the patient's request into a request type"""
    userdata = context.userdata
    userdata.request_type = request_type
    logger.info(f"request_type: {request_type}")
    return ""


@function_tool()
async def update_name(
    first_name: Annotated[str, Field(description="The patient's first name")],
    last_name: Annotated[str, Field(description="The patient's last name")],
    context: RunContext_T,
) -> str:
    """Call this tool when the patient provides their first and last name.
    Confirm the spelling with the patient before calling the function."""
    userdata = context.userdata
    userdata.patient_first_name = first_name
    userdata.patient_last_name = last_name
    return ""


@function_tool()
async def update_patient_type(
    patient_type: Annotated[
        patient_types, Field(description="The user's patient type")
    ],
    context: RunContext_T,
) -> str:
    """Call this tool when the user provides their patient type."""
    userdata = context.userdata
    userdata.patient_type = patient_type

    logger.info(f"patient_type: {patient_type}")

    await context.session.current_agent.update_instructions(
        get_system_prompt(
            system_prompt=userdata.system_prompt,
            phone_number=userdata.patient_phone or userdata.original_phone_number,
            existing_patient=True if patient_type == "existing" else False,
        )
    )

    return ""


@function_tool()
async def update_booking_type(
    booking_type: Annotated[booking_types, Field(description="The booking type")],
    context: RunContext_T,
) -> str:
    """Call this tool when the patient provides their booking type."""
    userdata = context.userdata
    userdata.booking_type = booking_type

    consultation_type = userdata.consultation_type

    if booking_type == "nhs":
        # Define NHS-available consultation types
        nhs_available_types = ["hygienist_consultation", "orthodontic_consultation"]

        if consultation_type in nhs_available_types:
            return (
                f"Unfortunately, we do not offer {consultation_type} for NHS patients."
            )
        else:
            return "Please call back during office hours"
    else:
        return "The booking type is updated to private"


@function_tool()
async def update_patient_relationship(
    patient_relationship: Annotated[
        str, Field(description="The relationship to the patient")
    ],
    context: RunContext_T,
) -> str:
    """Call this tool when determining the relationship to the patient from conversation context.

    AUTOMATICALLY call this function when you can infer the relationship from user's language:
    - If user says "I have/am having [symptoms]" or "I need [treatment]" → use "myself"
    - If user says "my child has [symptoms]" or "for my son/daughter" → use "my child"
    - If user says "my parent/mother/father has [symptoms]" → use "my parent"
    - If user says "my partner/spouse/husband/wife has [symptoms]" → use "my partner"

    Examples of when to call with "myself":
    - "I am having a toothache"
    - "I need a dental checkup"
    - "I want to book an appointment"
    - "My teeth hurt"
    - "My tooth is wobbling now"
    """
    userdata = context.userdata
    userdata.patient_relationship = patient_relationship
    return ""


@function_tool()
async def get_appointment_availability(
    context: RunContext_T,
) -> str:
    """Call this tool when the patient asks about appointment availability. or if you need to get the appointment availability."""
    userdata = context.userdata

    if userdata.is_in_get_appointment_availability_tool_call:
        return "Please hold on for a moment while I check the appointment availability"

    userdata.is_in_get_appointment_availability_tool_call = True

    if not userdata.service_id or not userdata.consultation_type:
        userdata.is_in_get_appointment_availability_tool_call = False
        return "Can you please provide the problem you are facing?"

    BACKEND_API = os.getenv("BACKEND_API")
    api_url = f"{BACKEND_API}/availability/{userdata.service_id}/{userdata.patient_type}/{userdata.preferred_doctor_id}"
    headers = {"Authorization": f"Bearer {BACKEND_API_TOKEN}"}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        json_data = response.json()

        # Format the data in a more LLM-friendly structure
        availability = json_data.get("availability", {})
        slot_duration = availability.get("slot_duration_minutes", 0)
        available_slots = availability.get("available_slots", [])

        if "No slots available" in available_slots:
            userdata.is_in_get_appointment_availability_tool_call = False
            try:
                await register_callback_request(context)
            except Exception as e:
                logger.error(f"Error registering callback request: {e}")

            userdata.is_in_get_appointment_availability_tool_call = False
            return "Unfortunately, there are no slots available. I have notified the team, they will get back to you soon."

        userdata.is_in_get_appointment_availability_tool_call = False

        # Group slots by date for better readability
        slots_by_date = {}
        for slot in available_slots:
            date = slot["date"]
            if date not in slots_by_date:
                slots_by_date[date] = []
            slots_by_date[date].append(
                {"slot_id": slot["hash_id"], "time": slot["start"]}
            )

        # Create LLM-friendly YAML structure
        formatted_data = {
            "appointment_availability": {
                "slot_duration_minutes": slot_duration,
                "available_dates_and_times": slots_by_date,
            }
        }
        data = yaml.dump(formatted_data, default_flow_style=False)
        return f"""Here are the available slots:
        {data}
        
        IMPORTANT INSTRUCTIONS:
        - Do not tell the year for the slot date or slot time
        - Show availability for ONLY FIRST TWO AVAILABLE DAYS at a time, one slot per day.
        - Show maximum 1 slot per day and atmost 2 days if applicable. If only one slot is available, then only tell about that slot on that day
        - Start with the earliest/closest available day
        - If user asks for more slots on the same day, show 2 more slots for that day (if available) or 2 slots from next available day.
        - If user asks for a different day, show slots for that specific day
        - Always limit to 2 slots maximum per response if applicalable or 1 slot if only 1 slot is present
        - No need to ask the user regarding if they want to the booking morning or afternoon
        - If no slots are available for the appointment, convey the same to the user
        - Only list out the slots that are available do not make up any slots that are not available
        """
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting appointment availability: {e}")
        userdata.is_in_get_appointment_availability_tool_call = False
        return f"Error getting appointment availability: {e}"


@function_tool()
async def update_slot_id_and_slot_day_and_timing(
    slot_id: Annotated[str, Field(description="The slot id")],
    slot_day: Annotated[
        str, Field(description="The slot day in DD-MM-YYYY format (e.g., 23-06-2025)")
    ],
    slot_timing: Annotated[
        str, Field(description="The slot timing in HH:MM:SS format (e.g., 14:00:00)")
    ],
    context: RunContext_T,
) -> str:
    """Call this tool when the patient provides the slot day and timing (after getting the appointment availability)
    slot_day should be in DD-MM-YYYY format (e.g., 23-06-2025)
    slot_timing should be in HH:MM:SS format (e.g., 14:00:00)
    """
    userdata = context.userdata
    userdata.slot_id = slot_id
    userdata.slot_day = slot_day
    userdata.slot_timing = slot_timing

    logger.info(f"slot_id: {slot_id}")
    logger.info(f"slot_day: {slot_day}")
    logger.info(f"slot_timing: {slot_timing}")

    return ""


@function_tool()
async def update_consultation_type(
    consultation_type: Annotated[
        consultation_types, Field(description="The consultation type")
    ],
    context: RunContext_T,
) -> str:
    """Call this tool when you diagnose the patient's request into a consultation type
    You don't have to tell the patient the consultation type
    """
    userdata = context.userdata
    userdata.consultation_type = consultation_type
    logger.info(f"consultation_type: {consultation_type}")

    # Get consultation mapping from organization config dynamically
    org_context = userdata.organization_context or userdata.customer_context  # Backward compatibility
    consultation_mapping = get_consultation_service_mapping(org_context.config)
    
    if consultation_type in consultation_mapping:
        service_id = consultation_mapping[consultation_type]
        userdata.service_id = service_id
        logger.info(f"service_id: {service_id}")
    else:
        logger.error(f"Consultation type {consultation_type} not found in customer config")
        return f"Consultation type {consultation_type} is not available for this practice."

    return ""


@function_tool()
async def book_appointment(
    context: RunContext_T,
) -> str:
    # """Called when the patient confirms the request for booking an appointment"""
    userdata = context.userdata

    if userdata.is_in_booking_tool_call:
        return "Booking request has already been made."

    userdata.is_in_booking_tool_call = True

    if not userdata.patient_first_name or not userdata.patient_last_name:
        userdata.is_in_booking_tool_call = False
        return "Please provide your name and phone number first."

    if not userdata.slot_id or not userdata.slot_day or not userdata.slot_timing:
        userdata.is_in_booking_tool_call = False
        return "Please provide the slot day and slot timing first."

    if not userdata.patient_type or not userdata.booking_type:
        userdata.is_in_booking_tool_call = False
        return "Please provide your patient type and booking type first."

    if not userdata.patient_relationship:
        userdata.is_in_booking_tool_call = False
        return "Please provide your relationship to the patient first."

    if not userdata.consultation_type or not userdata.service_id:
        userdata.is_in_booking_tool_call = False
        return "Please provide the consultation type first."

    BACKEND_API = os.getenv("BACKEND_API")
    api_url = f"{BACKEND_API}/book-appointment"
    headers = {"Authorization": f"Bearer {BACKEND_API_TOKEN}"}
    try:
        # Use customer-specific recording URL
        recording_url = get_recording_url(userdata.customer_context.config, userdata.room_name)
        
        required_data = {
            "slot_id": userdata.slot_id,
            "phone": userdata.patient_phone,
            "original_phone_number": userdata.original_phone_number,
            "dob": userdata.patient_dob,
            "first_name": userdata.patient_first_name,
            "last_name": userdata.patient_last_name,
            "email": userdata.patient_email or None,
            "patient_type": userdata.patient_type,
            "is_nhs": userdata.booking_type == "nhs",
            "consultation_type": userdata.consultation_type,
            "consultation_for": userdata.patient_relationship,
            "service_id": userdata.service_id,
            "slot_day": userdata.slot_day,
            "slot_timing": userdata.slot_timing,
            "patient_id": userdata.patient_id,
            "request_type": userdata.request_type,
            "recording_url": recording_url,
            "doctor_name": userdata.preferred_doctor_name,
            "doctor_id": userdata.preferred_doctor_id,
        }
        response = requests.post(api_url, json=required_data, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"response_data: {response_data}")
        userdata.is_in_booking_tool_call = False
        
        # Set outcome - appointment successfully booked
        userdata.call_outcome = "booked"
        logger.info("Call outcome: booked")
        
        return f"""Below is the response from server regarding the booking. Please convey the exact message to the patient without tampering it. basically read it out load the same message.
        Response:
        {response_data['message']}"""
    except requests.exceptions.RequestException as e:
        logger.error(f"Error booking appointment: {e}")
        userdata.is_in_booking_tool_call = False
        return f"Error booking appointment: {e}"


class BaseAgent(Agent):
    async def on_enter(self) -> None:
        agent_name = self.__class__.__name__
        logger.info(f"entering task {agent_name}")

        # self.session.generate_reply(tool_choice="none")


async def entrypoint(ctx: JobContext):
    call_start_time = time.time()
    chat_ctx_info = ChatContextInfo()
    turn_collector = TurnCollector(call_start_time)
    logger.info(f"room_name: {ctx.room.name}")

    # Connect and wait for participant first
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()
    phone = get_phone(participant)
    if not phone:
        # Use environment variable for fallback phone, or fail if not configured
        phone = os.getenv("FALLBACK_TEST_PHONE")
        if not phone:
            logger.error("No phone number found and FALLBACK_TEST_PHONE not configured")
            raise ValueError("Phone number is required for call processing")
        logger.warning(f"No phone number found, using configured fallback: {phone[:5]}...")

    # Use AgentFactory to get organization context/config
    session_metadata = {"room_name": ctx.room.name, "phone": phone}
    agent_session_obj = await AgentFactory.create_agent(session_metadata)
    org_id = agent_session_obj.org_id
    org_config = agent_session_obj.config
    
    logger.info(f"Organization identified: {org_id}")

    # Get organization-specific configuration
    system_prompt = org_config.get("system_prompt", "")
    storage_config = org_config.get("azure_storage", {})
    org_name = get_organization_name(org_config)
    
    # Use organization-specific storage path
    storage_container = storage_config.get("container", "dental")
    storage_base_path = storage_config.get("folder", org_id)
    req = api.RoomCompositeEgressRequest(
        room_name=ctx.room.name,
        audio_only=True,
        file_outputs=[
            api.EncodedFileOutput(
                file_type=api.EncodedFileType.OGG,
                filepath=f"{storage_base_path}/{ctx.room.name}.ogg",
                azure=api.AzureBlobUpload(
                    account_name=os.getenv("AZURE_PUBLIC_STORAGE_ACCOUNT_NAME"),
                    account_key=os.getenv("AZURE_PUBLIC_STORAGE_ACCOUNT_KEY"),
                    container_name=storage_container,
                ),
            )
        ],
    )
    lkapi = api.LiveKitAPI()

    # Retry logic for starting room composite egress
    max_retries = 5
    retry_delay = 2.0  # 1 second delay between retries
    last_exception = None

    try:

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Starting room composite egress (attempt {attempt + 1}/{max_retries})"
                )
                res = await lkapi.egress.start_room_composite_egress(req)
                logger.info(
                    f"Successfully started room composite egress on attempt {attempt + 1}"
                )
                break
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Failed to start room composite egress on attempt {attempt + 1}/{max_retries}: {e}"
                )

                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to start room composite egress after {max_retries} attempts. "
                        f"Last error: {last_exception}"
                    )
                    # Re-raise the last exception after all retries are exhausted
                    raise last_exception

        try:
            await lkapi.aclose()
        except Exception as e:
            logger.error(f"Error closing LiveKit API client: {e}")
            # Don't re-raise this exception as it's cleanup
    except Exception as e:
        logger.error(f"Error starting room composite egress: {e}")

    # Create user in backend with organization-specific recording URL
    BACKEND_API = os.getenv("BACKEND_API")
    api_url = f"{BACKEND_API}/user/create"
    headers = {"Authorization": f"Bearer {BACKEND_API_TOKEN}"}
    
    recording_url = get_recording_url(org_config, ctx.room.name)

    max_retries_user_creation = 3
    retry_delay_user_creation = 1.0
    last_exception_user_creation = None
    user_id = None

    for attempt in range(max_retries_user_creation):
        try:
            logger.info(
                f"Creating user (attempt {attempt + 1}/{max_retries_user_creation})"
            )
            response = requests.post(
                api_url,
                json={
                    "phone": phone,
                    "session_id": ctx.job.room.sid,
                    "room_name": ctx.room.name,
                    "recording_url": recording_url,
                },
                headers=headers,
            )
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"response_data: {response_data}")
            user_id = response_data["id"]
            logger.info(f"Successfully created user on attempt {attempt + 1}")
            break
        except requests.exceptions.RequestException as e:
            last_exception_user_creation = e
            logger.warning(
                f"Failed to create user on attempt {attempt + 1}/{max_retries_user_creation}: {e}"
            )

            if attempt < max_retries_user_creation - 1:
                logger.info(f"Retrying in {retry_delay_user_creation} seconds...")
                await asyncio.sleep(retry_delay_user_creation)
            else:
                logger.error(
                    f"Failed to create user after {max_retries_user_creation} attempts. "
                    f"Last error: {last_exception_user_creation}"
                )

    # Use fallback user_id if all retries failed
    if not user_id:
        fallback_user_id = os.getenv("FALLBACK_USER_ID")
        if fallback_user_id:
            user_id = fallback_user_id
            logger.warning(f"Using configured fallback user_id: {user_id}")
        else:
            logger.error("Failed to create user and no FALLBACK_USER_ID configured")
            raise RuntimeError("Unable to create user and no fallback configured")

    # Create UserData with organization context
    userdata = UserData()
    userdata.original_phone_number = phone
    if check_if_phone_number_is_uk_mobile_number(phone):
        userdata.patient_phone = phone
    userdata.patient_id = user_id
    userdata.system_prompt = system_prompt
    userdata.organization_context = OrganizationContext(org_id, org_config)
    userdata.customer_context = userdata.organization_context  # Backward compatibility alias
    
    try:
        userdata.room_name = ctx.room.name
        userdata.session_id = ctx.job.room.sid
    except Exception as e:
        logger.error(f"Error getting room name and session id: {e}")

    # Get organization-specific voice configuration
    voice_config = org_config.get("voice", {})
    voice_id = voice_config.get("voice_id", "rfkTsdZrVWEVhDycUYn9")  # Default voice
    voice_model = voice_config.get("model", "eleven_multilingual_v2")
    
    # Voice settings with organization-specific overrides
    voice_settings_config = voice_config.get("settings", {})
    voice_settings = elevenlabs.VoiceSettings(
        stability=voice_settings_config.get("stability", 0.6),
        similarity_boost=voice_settings_config.get("similarity_boost", 0.8),
        speed=voice_settings_config.get("speed", 0.87),
        use_speaker_boost=voice_settings_config.get("use_speaker_boost", True),
    )
    
    logger.info(f"Using voice: {voice_id} (model: {voice_model}) for organization: {org_id}")

    # Create agent session with customer-specific voice
    session = AgentSession[UserData](
        turn_detection=EnglishModel(),
        userdata=userdata,
        stt=deepgram.STT(keyterms=keyterms),
        llm=openai.LLM.with_azure(azure_deployment="gpt-4.1-mini"),
        tts=elevenlabs.TTS(
            voice_id=voice_id,
            model=voice_model,
            voice_settings=voice_settings,
        ),
        vad=silero.VAD.load(),
        max_tool_steps=10,
        min_endpointing_delay=MIN_ENDPOINTING_DELAY,
        max_endpointing_delay=MAX_ENDPOINTING_DELAY,
        min_interruption_duration=MIN_INTERRUPTION_DURATION,
        min_interruption_words=MIN_INTERRUPTION_WORDS,
    )

    userdata.agent_session = session

    await session.start(
        agent=BaseAgent(
            instructions=get_system_prompt(
                system_prompt=system_prompt, phone_number=phone, existing_patient=False
            ),
            tools=[
                update_request_type,
                update_name,
                update_phone_number,
                update_patient_dob,
                update_patient_type,
                update_booking_type,
                update_patient_relationship,
                get_appointment_availability,
                update_slot_id_and_slot_day_and_timing,
                update_consultation_type,
                book_appointment,
                get_current_date_and_time_in_uk,
                end_call,
                get_patient_type,
                get_consultation_type,
                update_preferred_doctor_with_name_and_id,
                handle_callback_request_and_forward_message_to_team,
                set_call_outcome,  # Analytics: Track call outcomes
            ],
        ),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

    # Use organization-specific greeting
    greeting = org_config.get("greeting")
    if not greeting:
        # Fallback to generic greeting with organization name
        from customer_context import get_agent_name
        agent_name = get_agent_name(org_config)
        greeting = f"Hi, this is {org_name}, I'm {agent_name}, how can I help you?"
    
    await session.say(greeting, allow_interruptions=False)

    if not userdata.session_id:
        try:
            userdata.session_id = ctx.job.room.sid
        except Exception as e:
            logger.error(f"Error getting session id: {e}")

    turns_stt_ttft_list = []
    turns_llm_ttft_list = []
    turns_tts_list = []

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

        if isinstance(ev.metrics, metrics.EOUMetrics):
            turns_stt_ttft_list.append(ev.metrics.transcription_delay)

        elif isinstance(ev.metrics, metrics.LLMMetrics):
            turns_llm_ttft_list.append(ev.metrics.ttft)

        elif isinstance(ev.metrics, metrics.TTSMetrics):
            turns_tts_list.append(ev.metrics.ttfb)

    @session.on("user_state_changed")
    def _on_user_state_changed(ev: UserStateChangedEvent):
        if ev.new_state == "speaking":
            turn_collector.handle_event("user_started_speaking")
            chat_ctx_info.add_speech_time(role="user", start_time=time.time())
            logger.info("User is speaking")
        elif ev.new_state == "listening":
            turn_collector.handle_event("user_stopped_speaking")
            chat_ctx_info.add_speech_time(role="user", end_time=time.time())
            logger.info("User is listening")

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        if ev.new_state == "speaking":
            turn_collector.handle_event("agent_started_speaking")
            chat_ctx_info.add_speech_time(role="assistant", start_time=time.time())
            logger.info("Agent is speaking")
        elif ev.new_state == "listening":
            turn_collector.handle_event("agent_stopped_speaking")
            chat_ctx_info.add_speech_time(role="assistant", end_time=time.time())
            logger.info("Agent is listening")

    @session.on("conversation_item_added")
    def _on_conversation_item_added(ev: ConversationItemAddedEvent):
        item = ev.item
        if item.role == "user":
            turn_collector.handle_event("user_speech_committed")
            chat_ctx_info.add_turn(item.id, "user")
            logger.info("User speech committed")
        elif item.role == "assistant":
            turn_collector.handle_event("agent_speech_committed")
            chat_ctx_info.add_turn(item.id, "assistant")
            logger.info("Agent speech committed")

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    async def send_slack_message_on_shutdown():
        room_name = ctx.room.name
        sid = ctx.job.room.sid
        call_end_time = time.time()
        call_duration = call_end_time - call_start_time
        logger.info(
            f"Call Duration: {call_duration:.2f} seconds ({call_duration/60:.2f} minutes)"
        )
        if session.current_speech:
            session.current_speech.interrupt()

        if "fake_room" in room_name.lower():
            return
        try:
            turns_additional_info = chat_ctx_info.to_dict()["turns"]
            all_items, cleaned_items = format_chat_ctx(
                session.current_agent.chat_ctx.copy(),
                session.history,
                system_prompt,
                turns_additional_info,
            )
            transcription = build_transcription_without_prompts(
                all_items, include_fnc_call=True, include_fnc_call_output=False
            )
            
            # Extract user utterances and analyze sentiment
            sentiment_result = None
            try:
                user_utterances = [
                    item.get("content", "") 
                    for item in transcription 
                    if item.get("role") == "user" and item.get("content", "").strip()
                ]
                if user_utterances:
                    full_user_text = " ".join(user_utterances)
                    sentiment_result = analyze_sentiment(full_user_text)
                    logger.info(f"Call sentiment analysis: {sentiment_result}")
            except Exception as sentiment_error:
                logger.warning(f"Sentiment analysis failed (non-critical): {sentiment_error}")
                sentiment_result = None
            
            message_config = get_slack_message_config(
                room_name,
                sid,
                usage_collector,
                turn_collector,
                turns_stt_ttft_list,
                turns_llm_ttft_list,
                turns_tts_list,
                call_duration,
                transcription,
                customer_config=org_config,  # Pass org_config for organization-specific data (backward compatibility)
            )
            
            # Add sentiment to message config if available
            if sentiment_result:
                message_config["user_sentiment"] = sentiment_result
            
            # Add call outcome to message config
            message_config["call_outcome"] = userdata.call_outcome or "unknown"
            logger.info(f"Call outcome for Slack: {message_config['call_outcome']}")
            
            await send_metrics_slack_notification(message_config)
            # await send_slack_message(
            #     os.getenv("SLACK_WEBHOOK_URL"),
            #     f"https://oaipublic.blob.core.windows.net/dental/westbury-dental-care/{room_name}.ogg",
            #     room_name,
            #     user_id,
            # )
        except Exception as e:
            logger.error(f"Error sending slack message: {e}")

    ctx.add_shutdown_callback(send_slack_message_on_shutdown)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            request_fnc=request,
            load_threshold=0.9,
            shutdown_process_timeout=60,
            job_memory_warn_mb=3000,
        )
    )
