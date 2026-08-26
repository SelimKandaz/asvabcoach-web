from __future__ import annotations

import json

from app.config import get_settings


class OpenAIService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    @property
    def enabled(self) -> bool:
        return self.settings.openai_available

    def _get_client(self):
        if not self.enabled:
            return None
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.settings.openai_api_key)
        return self._client

    def explain_question(self, payload: dict) -> dict | None:
        client = self._get_client()
        if client is None:
            return None

        response = client.chat.completions.create(
            model=self.settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful ASVAB-style tutor. Return valid JSON with keys: "
                        "simple_explanation, quick_method, why_correct, wrong_answer_reasons, test_taking_tip."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def generate_similar_questions(self, payload: dict) -> list[dict] | None:
        client = self._get_client()
        if client is None:
            return None

        response = client.chat.completions.create(
            model=self.settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate ASVAB-style practice questions. Return JSON with an items array. "
                        "Each item needs question_text, choices, correct_answer, explanation, skill_tag, difficulty_level."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        content = response.choices[0].message.content or '{"items": []}'
        return json.loads(content).get("items", [])

    def build_study_report(self, payload: dict) -> str | None:
        client = self._get_client()
        if client is None:
            return None

        response = client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a concise ASVAB-style study report with strengths, weaknesses, and next steps. "
                        "Keep it practical and motivational."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        return response.choices[0].message.content or None

