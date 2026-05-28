#!/usr/bin/env python
import asyncio
import logging

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .config import get_settings
from .medical_agent import MedicalAgentService
from .schemas import ChatRequest


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler("slack_connection.log"), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)


logger = setup_logging()
load_dotenv()
settings = get_settings()

if not settings.slack_bot_token or not settings.slack_app_token:
    raise EnvironmentError("Missing SLACK_BOT_TOKEN or SLACK_APP_TOKEN")

app = App(token=settings.slack_bot_token)
agent = MedicalAgentService(settings=settings)


@app.event("message")
def handle_message_events(body, say):
    try:
        event = body.get("event", {})
        if "bot_id" in event:
            return

        text = event.get("text", "")
        user_id = event.get("user")
        channel_id = event.get("channel")
        if not text or not user_id or not channel_id:
            return

        session_id = f"slack_{user_id}_{channel_id}"
        response = asyncio.run(agent.chat(ChatRequest(message=text, session_id=session_id)))
        say(text=_format_response(response))
    except Exception as exc:
        logger.exception("Error processing Slack message: %s", exc)
        say(text="I am sorry, I could not process that medical intake message right now.")


def _format_response(response) -> str:
    citation_text = ""
    if response.citations:
        citation_text = "\n\nSources:\n" + "\n".join(f"- {item.title}: {item.url}" for item in response.citations[:3])
    safety_text = ""
    if response.safety_flags:
        safety_text = "\n\nSafety flags:\n" + "\n".join(f"- {flag.message}" for flag in response.safety_flags)
    return f"{response.answer}{safety_text}{citation_text}"


def main():
    handler = SocketModeHandler(app, settings.slack_app_token)
    logger.info("Starting Slack medical agent in Socket Mode...")
    handler.start()


if __name__ == "__main__":
    main()
