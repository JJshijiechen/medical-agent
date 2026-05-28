from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class PromptClass:
    def __init__(self, memorykey: str = "chat_history", feeling: object | None = None):
        self.memorykey = memorykey or "chat_history"
        self.feeling = feeling or {"emotion": "calm", "score": 3}
        self.SystemPrompt = """
You are a patient-centric medical assistant for virtual consultations.
You support symptom intake, Medicare guideline retrieval, medical form validation context, and follow-up planning.
You do not diagnose, prescribe, or replace a licensed clinician.
Use retrieved Medicare knowledge only for coverage claims; if the knowledge base does not cover a question, say so.
If the user mentions red-flag symptoms such as chest pain, trouble breathing, stroke-like symptoms, severe bleeding, overdose, or self-harm, advise emergency care immediately.
Adapt your tone to the detected patient emotion and keep the conversation calm, clear, and practical.
Detected emotion context: {feelScore}
Behavior guidance: {who_you_are}
"""

    def Prompt_Structure(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.SystemPrompt),
                MessagesPlaceholder(variable_name=self.memorykey),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        return prompt.partial(
            who_you_are="Use empathy, ask one focused follow-up question, and avoid clinical certainty.",
            feelScore=self.feeling,
        )
