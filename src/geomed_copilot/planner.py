from __future__ import annotations

import json
import os
from typing import Protocol
import urllib.request



class PlannerModel(Protocol):
    def complete(self, prompt: str) -> str: ...


class OpenAICompatiblePlannerModel:
    """Small provider adapter; compatible with local vLLM and hosted chat APIs."""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 10.0) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        return self.complete_with_metadata(prompt)[0]

    def complete_with_metadata(self, prompt: str) -> tuple[str, dict]:
        body = json.dumps({
            "model": self.model,
            "temperature": 0,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }).encode()
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            value = json.loads(response.read())
        usage = value.get('usage') or {}
        return str(value["choices"][0]["message"]["content"]), {
            'prompt_tokens': usage.get('prompt_tokens'),
            'completion_tokens': usage.get('completion_tokens'),
        }


class OllamaPlannerModel:
    """Ollama adapter with an explicit, bounded generation profile."""

    def __init__(self, base_url: str, model: str, timeout: float = 30.0,
                 *, max_tokens: int = 256, json_mode: bool = True, thinking: bool = False, seed: int = 917) -> None:
        if type(max_tokens) is not int or not 1 <= max_tokens <= 8192:
            raise ValueError('invalid generation token budget')
        self.url = base_url.rstrip("/") + "/api/chat"
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        if thinking and json_mode:
            raise ValueError("thinking requires SQL text output")
        self.json_mode = json_mode
        self.thinking = thinking
        self.seed = seed

    def complete(self, prompt: str) -> str:
        return self.complete_with_metadata(prompt)[0]

    def complete_with_metadata(self, prompt: str) -> tuple[str, dict]:
        payload = {
            "model": self.model,
            "stream": False,
            "think": self.thinking,
            "options": {"temperature": 0, "num_predict": self.max_tokens},
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.thinking:
            payload['options'].update(temperature=0.6, top_p=0.95, top_k=20, min_p=0, num_ctx=16384, seed=self.seed)
        if self.json_mode:
            payload['format'] = 'json'
        body = json.dumps(payload).encode()
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            value = json.loads(response.read())
        metadata = {
            "prompt_tokens": value.get("prompt_eval_count"),
            "completion_tokens": value.get("eval_count"),
            "total_duration_ns": value.get("total_duration"),
            "done_reason": value.get("done_reason"),
        }
        return str(value["message"]["content"]), metadata
