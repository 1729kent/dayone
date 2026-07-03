import json
import time
from typing import Callable

from pydantic import BaseModel

from dayone.common.config import settings


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, model: str, client=None):
        self.model = model
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(vertexai=True, project=settings.project_id,
                                        location=settings.genai_location)
        return self._client

    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def _generate(self, **kwargs):
        last = None
        for attempt in range(3):
            try:
                return self.client.models.generate_content(model=self.model, **kwargs)
            except Exception as e:  # noqa: BLE001 - リトライ対象を広く取り最後に集約
                last = e
                self._sleep(2**attempt)
        raise LLMError(f"LLM call failed after 3 attempts: {last}") from last

    def gen_json(self, prompt: str, schema: type[BaseModel], system: str | None = None) -> BaseModel:
        from google.genai import types

        resp = self._generate(
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                system_instruction=system,
            ),
        )
        try:
            return schema.model_validate_json(resp.text)
        except Exception as e:
            raise LLMError(f"schema parse failed: {e}: {resp.text[:500]}") from e

    def gen_text(self, prompt: str, system: str | None = None) -> str:
        from google.genai import types

        resp = self._generate(contents=prompt,
                              config=types.GenerateContentConfig(system_instruction=system))
        return resp.text or ""

    def chat_with_tools(self, system: str, user: str, tools: list,
                        on_call: Callable[[str, dict], str], max_calls: int = 12) -> str:
        """tools: list[types.FunctionDeclaration]。モデルが function_call を出す限り
        on_call(name, args)->str を実行して返送する。最終テキストを返す。"""
        from google.genai import types

        tool = types.Tool(function_declarations=tools)
        config = types.GenerateContentConfig(system_instruction=system, tools=[tool])
        contents: list = [types.Content(role="user", parts=[types.Part(text=user)])]
        text = ""
        for _ in range(max_calls):
            resp = self._generate(contents=contents, config=config)
            candidate = resp.candidates[0]
            calls = [p.function_call for p in (candidate.content.parts or []) if p.function_call]
            text = resp.text or text
            if not calls:
                return text
            contents.append(candidate.content)
            response_parts = []
            for fc in calls:
                result = on_call(fc.name, dict(fc.args or {}))
                response_parts.append(types.Part.from_function_response(
                    name=fc.name, response={"result": result}))
            contents.append(types.Content(role="user", parts=response_parts))
        return text


class FakeLLM:
    """テスト用: 応答を enqueue するだけ"""

    def __init__(self, json_responses: list | None = None, text_responses: list[str] | None = None):
        self.json_responses = list(json_responses or [])
        self.text_responses = list(text_responses or [])
        self.prompts: list[str] = []

    def gen_json(self, prompt: str, schema: type[BaseModel], system: str | None = None):
        self.prompts.append(prompt)
        return self.json_responses.pop(0)

    def gen_text(self, prompt: str, system: str | None = None) -> str:
        self.prompts.append(prompt)
        return self.text_responses.pop(0)


def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
