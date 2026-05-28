import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import Settings, get_settings
from .schemas import EmotionResult, SafetyFlag


class PatientMemoryStore:
    _fallback_store: Dict[str, str] = {}

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.redis = None
        try:
            import redis

            client = redis.Redis.from_url(self.settings.redis_url, decode_responses=True)
            client.ping()
            self.redis = client
        except Exception:
            self.redis = None

    @staticmethod
    def session_history_key(session_id: str) -> str:
        return f"medical_agent:chat:{session_id}"

    def _profile_key(self, session_id: str) -> str:
        return f"medical_agent:patient_profile:{session_id}"

    def _read_json(self, key: str) -> Dict[str, Any]:
        raw = self.redis.get(key) if self.redis is not None else self._fallback_store.get(key)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _write_json(self, key: str, value: Dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        if self.redis is not None:
            self.redis.set(key, payload)
        else:
            self._fallback_store[key] = payload

    def get_profile(self, session_id: str) -> Dict[str, Any]:
        profile = self._read_json(self._profile_key(session_id))
        if profile:
            return profile
        return {
            "session_id": session_id,
            "preferences": {},
            "symptom_summary": [],
            "follow_ups": [],
            "emotion_trend": [],
            "updated_at": None,
        }

    def save_profile(self, session_id: str, profile: Dict[str, Any]) -> None:
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self._profile_key(session_id), profile)

    def update_after_chat(
        self,
        session_id: str,
        message: str,
        emotion: EmotionResult,
        safety_flags: list[SafetyFlag],
    ) -> Dict[str, Any]:
        profile = self.get_profile(session_id)
        profile.setdefault("symptom_summary", [])
        profile.setdefault("emotion_trend", [])
        profile["symptom_summary"] = (profile["symptom_summary"] + [message[:240]])[-10:]
        profile["emotion_trend"] = (
            profile["emotion_trend"]
            + [
                {
                    "emotion": emotion.emotion,
                    "score": emotion.score,
                    "risk_level": emotion.risk_level,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )[-20:]
        if safety_flags:
            profile["last_safety_flags"] = [flag.model_dump() for flag in safety_flags]
        self.save_profile(session_id, profile)
        return profile

    def add_follow_up(self, session_id: str, reminder: Dict[str, Any]) -> Dict[str, Any]:
        profile = self.get_profile(session_id)
        profile.setdefault("follow_ups", [])
        profile["follow_ups"] = (profile["follow_ups"] + [reminder])[-20:]
        self.save_profile(session_id, profile)
        return profile
