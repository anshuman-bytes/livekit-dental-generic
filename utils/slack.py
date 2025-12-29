import logging
import os
import io
import requests
import time
import json

from utils.custom_metrics import (
    calculate_user_to_agent_latency,
    calculate_average_from_list_of_floats,
)
# from slack_sdk import WebClient
from slack_sdk.web.async_client import AsyncWebClient
from typing import Any

logger = logging.getLogger("smiledesk-agent")
logger.setLevel(logging.INFO)


def get_slack_message_config(
    room_name,
    sid,
    usage_collector,
    turn_collector,
    turns_stt_ttft_list,
    turns_llm_ttft_list,
    turns_tts_list,
    call_duration,
    transcription,
    customer_config=None,  # Backward compatibility alias for org_config
    org_config=None,  # Organization configuration parameter for multi-tenant support
) -> dict:
    """Get the config for the slack message."""
    try:
        summary = usage_collector.get_summary()
        
        # Use organization-specific recording URL and name
        # Support both org_config and customer_config for backward compatibility
        config = org_config or customer_config
        if config:
            from customer_context import get_recording_url, get_organization_name, get_customer_name
            recording_url = get_recording_url(config, room_name)
            organization_name = get_organization_name(config) or get_customer_name(config)  # Backward compatibility
        else:
            # Organization config is required for multi-tenant support
            logger.error("Organization config is required but not provided for Slack notification")
            raise ValueError("Organization config is required for Slack notifications. Cannot proceed without organization configuration.")

        # Integrate the turn_collector here with the latency calculation
        all_turns = turn_collector.get_turns()
        logger.info(f"\n\n\n **** All turns: {all_turns} **** \n\n\n")
        logger.info(f"\n\n\n **** All turns length: {len(all_turns)} **** \n\n\n")

        avg_latency = calculate_user_to_agent_latency(all_turns)
        avg_latency = avg_latency * 1000
        logger.info(f"\n\n\n **** User to Agent Latency: {avg_latency} **** \n\n\n")
        avg_latency_stt = calculate_average_from_list_of_floats(turns_stt_ttft_list)
        avg_latency_llm = calculate_average_from_list_of_floats(turns_llm_ttft_list)
        avg_latency_tts = calculate_average_from_list_of_floats(turns_tts_list)

        try:
            avg_latency_stt = avg_latency_stt * 1000
            avg_latency_llm = avg_latency_llm * 1000
            avg_latency_tts = avg_latency_tts * 1000
        except Exception as e:
            logger.error(f"Error converting latencies to milliseconds: {e}")

        # stt_provider = app_config.get("stt", {}).get("provider", "")
        # tts_provider = app_config.get("tts", {}).get("provider", "")
        # base_llm_provider = app_config.get("llm", {}).get("provider", "")
        # llm_base_model = app_config.get("llm", {}).get("base_model", "")
        # llm_provider = f"{base_llm_provider}-{llm_base_model}"

        summary_dict = {
            "llm_prompt_tokens": summary.llm_prompt_tokens,
            "llm_prompt_cached_tokens": summary.llm_prompt_cached_tokens,
            "llm_completion_tokens": summary.llm_completion_tokens,
            "tts_characters_count": summary.tts_characters_count,
            "stt_audio_duration": summary.stt_audio_duration,
        }

        ENV_NAME = os.getenv("ENV_NAME", "production")
        config = {
            # "request_origin": str(request_origin),
            "summary": summary_dict,
            # "metrics_summary": metrics_summary,
            "recording_url": recording_url,
            "room_name": room_name,
            "sid": sid,
            # "stt_provider": stt_provider,
            # "tts_provider": tts_provider,
            # "llm_provider": llm_provider,
            # "org_token": org_token,
            # "user_id": user_id,
            # "user_name": user_name,
            "call_duration": call_duration,
            "organization_name": organization_name,  # Include organization name from customer_config
            "avg_latency": avg_latency,
            "avg_latency_stt": avg_latency_stt,
            "avg_latency_llm": avg_latency_llm,
            "avg_latency_tts": avg_latency_tts,
            # "agent_name": lk_agent_name,
            # "phone": phone,
            "transcription": transcription,
            "call_outcome": None,  # Will be set if available
        }
        logger.info(f"\n\n\n **** Slack message config: {config} **** \n\n\n")
        return config if ENV_NAME != "development" else {}

    except Exception as e:
        logger.error(f"Error getting slack message config: {e}")
        return {}


def rte_header_block(emoji: str, text: str) -> dict:
    return {
        "type": "rich_text_section",
        "elements": [
            {"type": "emoji", "name": emoji, "style": {"bold": True}},
            {
                "type": "text",
                "text": f" {text or 'Unknown'}",
                "style": {"bold": True},
            },
            {"type": "text", "text": "\n\n"},
        ],
    }


def rte_list_block(items: list[str]) -> dict:
    return {
        "type": "rich_text_list",
        "style": "bullet",
        "indent": 0,
        "border": 0,
        "elements": items,
    }


def rte_list_item(key: str, value: str, bold: bool = False) -> dict:
    return {
        "type": "rich_text_section",
        "elements": [
            {"type": "text", "text": f"{key}: ", "style": {"bold": bold}},
            {
                "type": "text",
                "text": value or "Unknown",
                "style": {"code": True},
            },
        ],
    }


def format_slack_metrics_main_message(
    organization_name: str,
    # user_name: str,
    duration_text: str,
    avg_latency: float,
    recording_url: str,
    user_sentiment: dict = None,
    call_outcome: str = None,
    # agent_name: str,
) -> dict:
    agent_name_text = "Production"
    
    # Build sentiment section if available
    sentiment_items = []
    if user_sentiment:
        label = user_sentiment.get("label", "UNKNOWN").upper()
        score = user_sentiment.get("score", 0.0)
        
        # Map sentiment to emoji
        if label == "POSITIVE":
            emoji = "😊"
            sentiment_text = f"{emoji} Positive"
        elif label == "NEGATIVE":
            emoji = "😟"
            sentiment_text = f"{emoji} Negative"
        else:
            emoji = "😐"
            sentiment_text = f"{emoji} Neutral/Unknown"
        
        sentiment_items = [
            rte_list_item("User Sentiment", f"{sentiment_text} ({score:.2%})", True),
        ]
    
    # Build call outcome section if available
    outcome_items = []
    if call_outcome:
        # Map outcome to emoji
        outcome_emoji_map = {
            "booked": "✅",
            "callback_requested": "📞",
            "no_slots": "❌",
            "enquiry_only": "❓",
            "transferred": "🔄",
            "hung_up": "📵",
            "unknown": "❔"
        }
        outcome_emoji = outcome_emoji_map.get(call_outcome, "❔")
        outcome_text = call_outcome.replace("_", " ").title()
        outcome_items = [
            rte_list_item("Call Outcome", f"{outcome_emoji} {outcome_text}", True),
        ]
    
    # Build main metrics list
    main_metrics = [
        rte_list_item("Organization", f"{organization_name}", True),
        # rte_list_item("User Name", f"{user_name}", True),
        rte_list_item("Call Duration", f"{duration_text}", True),
        rte_list_item("Avg. Latency", f"{avg_latency:.2f}ms", True),
    ]
    
    # Add outcome to metrics if available
    if outcome_items:
        main_metrics.extend(outcome_items)
    
    # Add sentiment to metrics if available
    if sentiment_items:
        main_metrics.extend(sentiment_items)
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":slack_call: AI Agent Call Summary - {agent_name_text}",
                "emoji": True,
            },
        },
        {"type": "divider"},
        {
            "type": "rich_text",
            "elements": [
                rte_list_block(main_metrics),
            ],
        },
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
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "text": "Open the thread for more information.",
                    "emoji": True,
                }
            ],
        },
        {"type": "divider"},
    ]
    return blocks


def format_slack_metrics_thread_1_message(
    room_name: str,
    sid: str,
    # org_token: str,
    # user_id: str,
    # stt_provider: str,
    # tts_provider: str,
    # llm_provider: str,
    summary: dict,
    avg_latency: float,
    avg_latency_stt: float,
    avg_latency_llm: float,
    avg_latency_tts: float,
    # metrics_summary: dict,
) -> dict:
    """Format the detailed metrics message."""
    room_details_items = [
        rte_list_item("Room", f"{room_name}"),
        rte_list_item("Session ID", f"{sid}"),
        # rte_list_item("Org Token", f"{org_token}"),
        # rte_list_item("User ID", f"{user_id}"),
    ]
    # providers_items = [
    #     rte_list_item("STT", f"{stt_provider}"),
    #     rte_list_item("TTS", f"{tts_provider}"),
    #     rte_list_item("LLM", f"{llm_provider}"),
    # ]
    usage_metrics_items = [
        rte_list_item("LLM Prompt Tokens", f"{summary.get('llm_prompt_tokens', 0)}"),
        rte_list_item(
            "LLM Completion Tokens", f"{summary.get('llm_completion_tokens', 0)}"
        ),
        rte_list_item("TTS Characters", f"{summary.get('tts_characters_count', 0)}"),
        rte_list_item(
            "STT Audio Duration", f"{summary.get('stt_audio_duration', 0):.1f}s"
        ),
    ]
    performance_metrics_items = [
        rte_list_item("Avg. Latency", f"{avg_latency:.2f}ms"),
        rte_list_item("Avg. STT Latency", f"{avg_latency_stt:.2f}ms"),
        rte_list_item("Avg. LLM TTFT Latency", f"{avg_latency_llm:.2f}ms"),
        rte_list_item("Avg. TTS TTFT Latency", f"{avg_latency_tts:.2f}ms"),
    ]
    # for metric, value in metrics_summary.items():
    #     if metric == "total_rag_calls":
    #         performance_metrics_items.append(rte_list_item(f"{metric}", f"{value}"))
    #     elif isinstance(value, float):
    #         performance_metrics_items.append(
    #             rte_list_item(f"{metric}", f"{value:.2f}ms")
    #         )
    #     else:
    #         performance_metrics_items.append(rte_list_item(f"{metric}", f"{value}"))

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":receipt: Detailed Metrics",
                "emoji": True,
            },
        },
        {"type": "divider"},
        {
            "type": "rich_text",
            "elements": [
                rte_header_block("clipboard", "Room Details"),
                rte_list_block(room_details_items),
            ],
        },
        {"type": "divider"},
        # {
        #     "type": "rich_text",
        #     "elements": [
        #         rte_header_block("electric_plug", "Providers"),
        #         rte_list_block(providers_items),
        #     ],
        # },
        # {"type": "divider"},
        {
            "type": "rich_text",
            "elements": [
                rte_header_block("bar_chart", "Usage Metrics"),
                rte_list_block(usage_metrics_items),
            ],
        },
        {"type": "divider"},
        {
            "type": "rich_text",
            "elements": [
                rte_header_block("bar_chart", "Performance Metrics"),
                rte_list_block(performance_metrics_items),
            ],
        },
        {"type": "divider"},
    ]
    return blocks


def thread_2_file_header_block() -> list[dict[str, Any]]:
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "💬 Conversation Transcript",
            },
        },
        {"type": "divider"},
    ]
    return blocks


def format_slack_metrics_thread_2_file_message(transcription: list[dict]) -> str:
    final_message = ""
    for item in transcription:
        item_type = item.get("type", "message")
        if item_type == "message":
            role = item.get("role", "")
            content = item.get("content", "")
            if role == "assistant":
                icon = "🤖"
                role_display = "Agent"
            elif role == "user":
                icon = "👤"
                role_display = "User"
            else:
                role_display = role.capitalize()
            final_message += f"{icon} *{role_display}*: {content}\n"
        elif item_type == "function_call":
            icon = "🛠️"
            role_display = "Tool"
            name = item.get("name", "")
            arguments = item.get("arguments", "")
            final_message += f"{icon} *{role_display}*: {name} - `{arguments}`\n"
    return final_message


def utf8len(s: str) -> int:
    return len(s.encode("utf-8"))


def create_file_data_from_text(text: str):
    return io.StringIO(text)


def send_slack_blocks(blocks, slack_hook):
    slack_data = {"blocks": blocks}
    try:
        response = requests.post(
            slack_hook,
            data=json.dumps(slack_data),
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            logger.error(f"Failed to send slack notification: {response.text}")
        else:
            logger.info("Slack notification sent successfully")
    except Exception as e:
        logger.error(f"Error while sending slack blocks: {e}")


async def send_metrics_slack_notification(message_config: dict, retry_count: int = 0) -> None:
    """
    Send a slack notification for a metrics.
    Will retry up to 3 times if an exception occurs.
    Falls back to sending failure notification to Slack if all retries fail.
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 10  # seconds
    SLACK_CHANNEL_ID = "C08VB17LX35"

    try:
        if not message_config:
            return

        slack_channel_id = SLACK_CHANNEL_ID

        internal_client = AsyncWebClient(token=os.getenv("SLACK_INTERNAL_BOT_TOKEN"))
        thread_ts = None
        try:

            def _get_duration_text(call_duration):
                try:
                    call_duration_mins = call_duration / 60
                    # Convert to human readable format
                    minutes = int(call_duration_mins)
                    seconds = int((call_duration_mins - minutes) * 60)

                    if minutes > 0:
                        if seconds > 0:
                            duration_text = (
                                f"{minutes} minute{'s' if minutes != 1 else ''} "
                                f"{seconds} second{'s' if seconds != 1 else ''}"
                            )
                        else:
                            duration_text = (
                                f"{minutes} minute{'s' if minutes != 1 else ''}"
                            )
                    else:
                        duration_text = f"{seconds} second{'s' if seconds != 1 else ''}"
                except (TypeError, ZeroDivisionError) as e:
                    logger.error(f"Error converting call duration to minutes: {e}")
                    duration_text = "0 seconds"
                return duration_text

            # Main Message - Summary Metrics
            main_msg_blocks = format_slack_metrics_main_message(
                organization_name=message_config.get("organization_name", "Dental Practice"),
                duration_text=_get_duration_text(message_config.get("call_duration"))
                or "0 seconds",
                avg_latency=message_config.get("avg_latency") or 0,
                recording_url=message_config.get("recording_url") or "Unknown",
                user_sentiment=message_config.get("user_sentiment"),
                call_outcome=message_config.get("call_outcome"),
            )
            main_response = await internal_client.chat_postMessage(
                channel=slack_channel_id,
                blocks=main_msg_blocks,
                text="AI Agent Call Summary",
            )
            thread_ts = main_response.get("ts", None)
            logger.info(f"Main message slack response: {main_response}")
        except Exception as e:
            logger.error(f"Error sending main metrics slack notification: {str(e)}")
        if thread_ts:
            # Thread 1 - Detailed Metrics
            try:
                thread_1_msg_blocks = format_slack_metrics_thread_1_message(
                    room_name=message_config.get("room_name") or "Unknown",
                    sid=message_config.get("sid") or "Unknown",
                    # org_token=message_config.get("org_token") or "Unknown",
                    # user_id=message_config.get("user_id") or "Unknown",
                    # stt_provider=message_config.get("stt_provider") or "Unknown",
                    # tts_provider=message_config.get("tts_provider") or "Unknown",
                    # llm_provider=message_config.get("llm_provider") or "Unknown",
                    summary=message_config.get("summary") or {},
                    avg_latency=message_config.get("avg_latency") or 0,
                    avg_latency_stt=message_config.get("avg_latency_stt") or 0,
                    avg_latency_llm=message_config.get("avg_latency_llm") or 0,
                    avg_latency_tts=message_config.get("avg_latency_tts") or 0,
                    # metrics_summary=message_config.get("metrics_summary") or {},
                )
                thread_1_response = await internal_client.chat_postMessage(
                    channel=slack_channel_id,
                    blocks=thread_1_msg_blocks,
                    thread_ts=thread_ts,
                    text="AI Agent Call Summary - Thread 1",
                )
                logger.info(f"Thread 1 message slack response: {thread_1_response}")
            except Exception as e:
                logger.error(
                    f"Error sending thread 1 metrics slack notification: {str(e)}"
                )
            # Thread 2 - Transcript
            # Here we are sending it via file
            # Step 1: call the app.client.files_getUploadURLExternal which returns upload_url and file_id
            # Step 2: upload the file to the upload_url
            # Step 3: call the app.client.files_completeUploadExternal with the file_id, channel_id, thread_ts, and blocks
            try:
                content = format_slack_metrics_thread_2_file_message(
                    transcription=message_config.get("transcription") or "Unknown"
                )
                filename = f"transcript_{message_config.get('sid', 'unknown')}.txt"
                upload_url_external_res = await internal_client.files_getUploadURLExternal(
                    filename=filename,
                    length=utf8len(content),
                    snippet_type="text",
                )

                file_id = None
                upload_res_status_code = 400
                if upload_url_external_res.data.get("ok", False):
                    upload_url = upload_url_external_res.data.get("upload_url")
                    file_id = upload_url_external_res.data.get("file_id")

                if file_id:
                    file_data = create_file_data_from_text(content)
                    files = {
                        "file": (
                            filename,
                            file_data,
                            "text/plain",
                        )
                    }
                    upload_res = requests.post(upload_url, files=files)
                    upload_res_status_code = upload_res.status_code
                else:
                    logger.error(f"Failed to upload file to slack: {upload_res.text}")

                if int(upload_res_status_code) == 200:
                    complete_upload_url_res = (
                        await internal_client.files_completeUploadExternal(
                            files=[{"id": file_id}],
                            channel_id=slack_channel_id,
                            thread_ts=thread_ts,
                            initial_comment="Conversation Transcript",
                        )
                    )
                    logger.info(
                        f"Thread 2 file upload response: {complete_upload_url_res}"
                    )
            except Exception as e:
                logger.error(
                    f"Error sending thread 2 metrics slack notification: {str(e)}"
                )
    except Exception as e:
        logger.error(f"Error sending metrics slack notification: {str(e)}")

        # Implement retry logic
        if retry_count < MAX_RETRIES:
            logger.info(
                f"Retrying send_metrics_slack_notification. Attempt {retry_count + 1} of {MAX_RETRIES}"
            )
            time.sleep(RETRY_DELAY)
            send_metrics_slack_notification(
                message_config=message_config, retry_count=retry_count + 1
            )
        else:
            logger.error(
                f"All {MAX_RETRIES} attempts failed for sending metrics notification. Sending failure alert."
            )
            # Create fallback blocks for failure notification
            fallback_blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ Metrics Notification Failed",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Failed to send metrics notification for:*\n• SID: {message_config['sid']}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n{e}",
                    },
                },
            ]
            try:
                send_slack_blocks(
                    blocks=fallback_blocks,
                    slack_hook="C07TNG4C0B1",
                )
                logger.info("Successfully sent metrics failure notification")
            except Exception as fallback_error:
                logger.error(f"Fallback notification also failed: {fallback_error}")