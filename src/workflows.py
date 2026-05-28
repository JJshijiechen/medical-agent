import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .config import Settings, get_settings
from .medical_memory import PatientMemoryStore
from .schemas import ReminderRequest, ReminderResponse


class CalendarService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def create_follow_up(
        self,
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        try:
            from .Tools import GoogleClient

            client = GoogleClient()
            event = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start_time.isoformat(), "timeZone": self.settings.default_timezone},
                "end": {"dateTime": end_time.isoformat(), "timeZone": self.settings.default_timezone},
            }
            created = client.calendar_service.events().insert(
                calendarId=self.settings.google_calendar_id,
                body=event,
            ).execute()
            return {"status": "created", "event": created}
        except Exception as exc:
            return {
                "status": "dry_run",
                "reason": str(exc),
                "event": {
                    "summary": summary,
                    "description": description,
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
            }


class NotifierService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    async def notify(self, channel: str, recipient: Optional[str], message: str) -> Dict[str, Any]:
        if channel == "slack":
            return await asyncio.to_thread(self._notify_slack, recipient, message)
        if channel == "telegram":
            return await self._notify_telegram(recipient, message)
        return {"channel": channel, "status": "dry_run", "message": message}

    def _notify_slack(self, recipient: Optional[str], message: str) -> Dict[str, Any]:
        if not self.settings.slack_bot_token or not recipient:
            return {"channel": "slack", "status": "dry_run", "message": message}
        try:
            from slack_sdk import WebClient

            client = WebClient(token=self.settings.slack_bot_token)
            response = client.chat_postMessage(channel=recipient, text=message)
            return {"channel": "slack", "status": "sent", "ts": response.get("ts")}
        except Exception as exc:
            return {"channel": "slack", "status": "error", "error": str(exc)}

    async def _notify_telegram(self, recipient: Optional[str], message: str) -> Dict[str, Any]:
        if not self.settings.telegram_bot_token or not recipient:
            return {"channel": "telegram", "status": "dry_run", "message": message}
        try:
            from telegram import Bot

            bot = Bot(token=self.settings.telegram_bot_token)
            response = await bot.send_message(chat_id=recipient, text=message)
            return {"channel": "telegram", "status": "sent", "message_id": response.message_id}
        except Exception as exc:
            return {"channel": "telegram", "status": "error", "error": str(exc)}


class ReminderWorkflow:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        calendar_service: Optional[CalendarService] = None,
        notifier_service: Optional[NotifierService] = None,
        memory_store: Optional[PatientMemoryStore] = None,
    ):
        self.settings = settings or get_settings()
        self.calendar_service = calendar_service or CalendarService(self.settings)
        self.notifier_service = notifier_service or NotifierService(self.settings)
        self.memory_store = memory_store or PatientMemoryStore(self.settings)

    async def create_reminder(self, request: ReminderRequest) -> ReminderResponse:
        start = self._resolve_start_time(request)
        end = start + timedelta(minutes=request.duration_minutes)
        summary = self._build_summary(request.user_text)
        description = f"Medical follow-up reminder created from patient request: {request.user_text}"
        calendar_result = self.calendar_service.create_follow_up(summary, description, start, end)

        notification_message = f"Follow-up reminder set: {summary} at {start.isoformat()}"
        notifications: List[Dict[str, Any]] = []
        if request.channel in {"slack", "telegram"}:
            notifications.append(await self.notifier_service.notify(request.channel, request.recipient, notification_message))
        else:
            notifications.append({"channel": "api", "status": "dry_run", "message": notification_message})

        status = "created" if calendar_result.get("status") == "created" else "dry_run"
        payload = {
            "summary": summary,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "calendar": calendar_result,
            "notifications": notifications,
        }
        self.memory_store.add_follow_up(request.session_id, payload)
        return ReminderResponse(
            status=status,
            summary=summary,
            start_time=start,
            end_time=end,
            calendar_event=calendar_result,
            notifications=notifications,
            message=notification_message,
        )

    def _resolve_start_time(self, request: ReminderRequest) -> datetime:
        timezone = ZoneInfo(self.settings.default_timezone)
        if request.start_time:
            value = request.start_time
            return value if value.tzinfo else value.replace(tzinfo=timezone)

        now = datetime.now(timezone)
        text = request.user_text.lower()
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}(?::\d{2})?", text)
        if iso_match:
            return datetime.fromisoformat(iso_match.group(0)).replace(tzinfo=timezone)
        if "next week" in text or "下周" in text:
            return (now + timedelta(days=7)).replace(hour=9, minute=0, second=0, microsecond=0)
        if "tomorrow" in text or "明天" in text:
            return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    @staticmethod
    def _build_summary(user_text: str) -> str:
        cleaned = re.sub(r"\s+", " ", user_text).strip()
        cleaned = re.sub(r"(?i)\b(remind me|please remind me|create|schedule|tomorrow|next week)\b", "", cleaned)
        cleaned = re.sub(r"(?i)\b(to\s+)?follow\s+up\s+(about|on)?\b", "", cleaned)
        cleaned = re.sub(r"(?i)\b(to|about|on)\b\s*$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" :,-")
        return f"Patient follow-up: {cleaned[:80] or 'check in'}"
