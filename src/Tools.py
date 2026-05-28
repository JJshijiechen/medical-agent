import os
import pickle
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .config import get_settings
from .medical_rag import MedicalRAGService

load_dotenv()

try:
    from langchain.agents import tool
except Exception:  # pragma: no cover - fallback when LangChain is unavailable
    def tool(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]

        def decorator(func):
            return func

        return decorator


SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]


class GoogleClient:
    def __init__(self):
        self.creds = None
        self.calendar_service = None
        self.tasks_service = None
        self._initialize_services()

    def _initialize_services(self):
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                self.creds = pickle.load(token)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open("token.pickle", "wb") as token:
                pickle.dump(self.creds, token)

        self.calendar_service = build("calendar", "v3", credentials=self.creds)
        self.tasks_service = build("tasks", "v1", credentials=self.creds)


class TodoInput(BaseModel):
    subject: str
    dueTime: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None


class ScheduleSchema(BaseModel):
    startTime: str
    endTime: str


class ScheduleSchemaSetData(BaseModel):
    date: Optional[str] = None
    dateTime: Optional[str] = None
    timeZone: Optional[str] = None


class ScheduleSchemaSet(BaseModel):
    summary: str = Field(description="Calendar event title")
    start: ScheduleSchemaSetData
    end: ScheduleSchemaSetData
    isAllDay: bool = False
    description: Optional[str] = None


class ScheduleSearch(BaseModel):
    timeMin: Optional[str] = None
    timeMax: Optional[str] = None


class ScheduleModify(BaseModel):
    timeMin: Optional[str] = None
    timeMax: Optional[str] = None
    description: Optional[str] = None
    start: Optional[ScheduleSchemaSetData] = None
    end: Optional[ScheduleSchemaSetData] = None
    summary: Optional[str] = None


class DeleteSchedule(BaseModel):
    summary: str
    description: Optional[str] = None


class ScheduleDel(BaseModel):
    eventid: str


@tool
def search(query: str) -> str:
    """Use only when current external web information is required."""
    if not os.getenv("SERPAPI_API_KEY"):
        return "Search is not configured because SERPAPI_API_KEY is missing."
    try:
        from langchain_community.utilities import SerpAPIWrapper

        return SerpAPIWrapper().run(query)
    except Exception as exc:
        return f"Search failed: {exc}"


@tool(parse_docstring=True)
def get_info_from_local(query: str) -> str:
    """Retrieve Medicare guidance from the local medical knowledge base.

    Args:
        query: User question about Medicare or medical guidance.
    """
    service = MedicalRAGService(get_settings())
    hits = service.retrieve(query)
    if not hits:
        return "The Medicare knowledge base did not contain a relevant answer."
    lines = []
    for hit in hits[:3]:
        title = hit.document.metadata.get("title", "Medicare guideline")
        url = hit.document.metadata.get("url")
        lines.append(f"{title} ({url}): {hit.document.page_content[:500]}")
    return "\n\n".join(lines)


@tool
def create_todo(todo: TodoInput) -> str:
    """Create a Google Task for medical follow-up tracking."""
    try:
        client = GoogleClient()
        task = {"title": todo.subject, "notes": todo.description or "", "status": "needsAction"}
        if todo.dueTime:
            task["due"] = todo.dueTime
        tasklists = client.tasks_service.tasklists().list().execute()
        tasklist_id = tasklists["items"][0]["id"]
        client.tasks_service.tasks().insert(tasklist=tasklist_id, body=task).execute()
        return f"Created follow-up task: {todo.subject}"
    except Exception as exc:
        return f"Task creation dry-run or failed: {exc}"


@tool
def checkSchedule(schedule: ScheduleSchema) -> str:
    """Check Google Calendar availability for a time range."""
    return _calendar_list(schedule.startTime, schedule.endTime)


@tool
def SearchSchedule(search: ScheduleSearch) -> str:
    """Search Google Calendar events."""
    return _calendar_list(search.timeMin, search.timeMax)


@tool
def SetSchedule(sets: ScheduleSchemaSet) -> str:
    """Create a Google Calendar follow-up event."""
    try:
        settings = get_settings()
        client = GoogleClient()
        event = {"summary": sets.summary, "description": sets.description or ""}
        if sets.isAllDay:
            event["start"] = {"date": sets.start.date}
            event["end"] = {"date": sets.end.date}
        else:
            event["start"] = {
                "dateTime": sets.start.dateTime,
                "timeZone": sets.start.timeZone or settings.default_timezone,
            }
            event["end"] = {
                "dateTime": sets.end.dateTime,
                "timeZone": sets.end.timeZone or settings.default_timezone,
            }
        created = client.calendar_service.events().insert(calendarId=settings.google_calendar_id, body=event).execute()
        return f"Created calendar event: {created.get('htmlLink', sets.summary)}"
    except Exception as exc:
        return f"Calendar creation dry-run or failed: {exc}"


@tool
def ModifySchedule(search: ScheduleModify) -> str:
    """Legacy compatibility stub for modifying a follow-up event."""
    return "Calendar modification should be performed through /api/v1/reminders or Google Calendar directly."


@tool
def DelSchedule(query: DeleteSchedule) -> str:
    """Legacy compatibility stub for deleting a follow-up event."""
    return f"Please confirm deletion in Google Calendar for event matching: {query.summary}"


@tool
def ConfirmDelSchedule(query: ScheduleDel) -> str:
    """Delete a Google Calendar event by ID."""
    try:
        client = GoogleClient()
        client.calendar_service.events().delete(calendarId=get_settings().google_calendar_id, eventId=query.eventid).execute()
        return "Deleted calendar event."
    except Exception as exc:
        return f"Calendar deletion dry-run or failed: {exc}"


def _calendar_list(time_min: Optional[str], time_max: Optional[str]) -> str:
    try:
        client = GoogleClient()
        result = client.calendar_service.events().list(
            calendarId=get_settings().google_calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return str(result)
    except Exception as exc:
        return f"Calendar lookup dry-run or failed: {exc}"
