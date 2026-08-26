from __future__ import annotations

import json

import httpx

from app.config import get_settings


class AIService:
    """Small client for local or hosted providers with a compatible chat API."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.ai_available

    def _request(self, messages: list[dict], *, json_mode: bool = False) -> str | None:
        if not self.enabled:
            return None

        headers = {"Content-Type": "application/json"}
        if self.settings.ai_api_key.strip():
            headers["Authorization"] = f"Bearer {self.settings.ai_api_key.strip()}"

        body = {
            "model": self.settings.ai_model,
            "messages": messages,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            response = httpx.post(
                f"{self.settings.ai_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=body,
                timeout=45.0,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"].get("content")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            return None

    def explain_question(self, payload: dict) -> dict | None:
        content = self._request(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a careful ASVAB-style tutor. Return valid JSON with keys: "
                        "simple_explanation, quick_method, why_correct, wrong_answer_reasons, test_taking_tip."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
            json_mode=True,
        )
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    def generate_similar_questions(self, payload: dict) -> list[dict] | None:
        content = self._request(
            [
                {
                    "role": "system",
                    "content": (
                        "Generate ASVAB-style practice questions. Return JSON with an items array. "
                        "Each item needs question_text, choices, correct_answer, explanation, skill_tag, difficulty_level."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
            json_mode=True,
        )
        if not content:
            return None
        try:
            return json.loads(content).get("items", [])
        except (json.JSONDecodeError, AttributeError):
            return None

    def build_study_report(self, payload: dict) -> str | None:
        return self._request(
            [
                {
                    "role": "system",
                    "content": (
                        "Write a concise ASVAB-style study report with strengths, weaknesses, and next steps. "
                        "Keep it practical and motivational."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ]
        )
