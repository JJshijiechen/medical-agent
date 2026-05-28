from src.medical_emotion import EmotionDetector
from src.medical_memory import PatientMemoryStore
from src.medical_safety import detect_red_flags, triage_from_flags


def test_emotion_detector_returns_required_schema():
    result = EmotionDetector().detect("I am very worried and scared about this pain!")

    assert result.emotion in {"anxious", "distressed"}
    assert 1 <= result.score <= 10
    assert result.risk_level in {"moderate", "high", "crisis"}
    assert result.comfort_strategy


def test_red_flag_detection_marks_emergency():
    flags = detect_red_flags("I have chest pain and difficulty breathing")

    assert {flag.code for flag in flags} >= {"chest_pain", "breathing"}
    assert triage_from_flags(flags) == "urgent"


def test_patient_memory_key_is_stable():
    assert PatientMemoryStore.session_history_key("abc") == "medical_agent:chat:abc"
