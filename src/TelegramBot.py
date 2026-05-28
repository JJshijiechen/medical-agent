import logging

from dotenv import load_dotenv

from .config import get_settings
from .medical_agent import MedicalAgentService
from .schemas import ChatRequest


load_dotenv()
logger = logging.getLogger(__name__)


async def handle_message(update, context) -> None:
    if update.effective_chat is None or update.message is None:
        return
    service: MedicalAgentService = context.application.bot_data["medical_agent"]
    session_id = f"telegram_{update.effective_chat.id}"
    response = await service.chat(ChatRequest(message=update.message.text or "", session_id=session_id))
    await update.message.reply_text(_format_response(response))


def _format_response(response) -> str:
    citation_text = ""
    if response.citations:
        citation_text = "\n\nSources:\n" + "\n".join(f"- {item.title}: {item.url}" for item in response.citations[:3])
    return f"{response.answer}{citation_text}"


def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise EnvironmentError("Missing TELEGRAM_BOT_TOKEN")
    try:
        from telegram.ext import Application, MessageHandler, filters
    except Exception as exc:
        raise RuntimeError("python-telegram-bot is required for TelegramBot") from exc

    logging.basicConfig(level=logging.INFO)
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["medical_agent"] = MedicalAgentService(settings=settings)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Starting Telegram medical agent bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
