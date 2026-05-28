import asyncio

from .medical_agent import MedicalAgentService
from .schemas import ChatRequest


class AgentClass:
    """Compatibility wrapper for older Slack/classroom entrypoints."""

    def __init__(self):
        self.service = MedicalAgentService()

    def run_agent(self, input, session_id=None):
        request = ChatRequest(message=input, session_id=session_id or "default")
        try:
            response = asyncio.run(self.service.chat(request))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            response = loop.run_until_complete(self.service.chat(request))
        return {
            "output": response.answer,
            "emotion": response.emotion.model_dump(),
            "citations": [citation.model_dump() for citation in response.citations],
            "safety_flags": [flag.model_dump() for flag in response.safety_flags],
            "next_steps": response.next_steps,
            "session_id": response.session_id,
        }
