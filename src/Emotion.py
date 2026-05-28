from .medical_emotion import EmotionDetector


class EmotionClass:
    """Backward-compatible adapter for the original EmotionClass API."""

    def __init__(self, model=None):
        self.detector = EmotionDetector()
        self.Emotion = None

    def Emotion_Sensing(self, input):
        result = self.detector.detect(input or "")
        self.Emotion = result.model_dump()
        return self.Emotion
