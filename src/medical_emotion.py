import re

from .schemas import EmotionResult


class EmotionDetector:
    """Deterministic first-pass emotion detector for safe, testable routing."""

    KEYWORDS = {
        "anxious": ("worried", "anxious", "scared", "panic", "afraid", "害怕", "担心", "焦虑"),
        "angry": ("angry", "furious", "upset", "mad", "生气", "愤怒"),
        "sad": ("sad", "depressed", "hopeless", "crying", "难过", "沮丧", "绝望"),
        "confused": ("confused", "unclear", "don't understand", "not sure", "困惑", "不明白"),
        "distressed": ("pain", "severe", "can't", "cannot", "terrible", "疼", "严重", "受不了"),
        "positive": ("thank", "thanks", "great", "better", "谢谢", "好多了"),
    }

    def detect(self, text: str) -> EmotionResult:
        lowered = text.lower()
        hits = {
            emotion: sum(1 for keyword in keywords if keyword.lower() in lowered)
            for emotion, keywords in self.KEYWORDS.items()
        }
        emotion = max(hits, key=hits.get)
        if hits[emotion] == 0:
            emotion = "calm"

        exclamation_boost = min(text.count("!"), 2)
        severe_words = len(re.findall(r"\b(severe|terrible|emergency|urgent|worst)\b", lowered))
        negative = hits.get("anxious", 0) + hits.get("angry", 0) + hits.get("sad", 0) + hits.get("distressed", 0)
        score = min(10, max(1, 3 + negative * 2 + severe_words * 2 + exclamation_boost))
        if emotion == "positive":
            score = max(1, 3 - hits["positive"])

        if score >= 9:
            risk = "crisis"
        elif score >= 7:
            risk = "high"
        elif score >= 5:
            risk = "moderate"
        else:
            risk = "low"

        strategies = {
            "anxious": "Acknowledge worry, slow down the intake, and ask one concrete question at a time.",
            "angry": "Stay calm, validate frustration, and focus on the next practical step.",
            "sad": "Use supportive language and avoid overwhelming the patient with long instructions.",
            "confused": "Use plain language, summarize what is known, and clarify missing details.",
            "distressed": "Prioritize safety screening and immediate care guidance if red flags are present.",
            "positive": "Keep the tone warm and concise while continuing structured intake.",
            "calm": "Use clear, calm language and ask one focused follow-up question.",
        }
        return EmotionResult(
            emotion=emotion,  # type: ignore[arg-type]
            score=score,
            risk_level=risk,  # type: ignore[arg-type]
            comfort_strategy=strategies[emotion],
        )
