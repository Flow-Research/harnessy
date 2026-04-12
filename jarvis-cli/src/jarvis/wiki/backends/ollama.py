"""Local Ollama backend — POST to the Ollama REST API via httpx."""

from __future__ import annotations

from jarvis.wiki.backends.base import WikiBackend


class OllamaBackend(WikiBackend):
    """Local Ollama models via the REST API at http://localhost:11434."""

    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
    ) -> None:
        super().__init__()
        self.model = model
        self.base_url = base_url

    def run(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        import httpx

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "system": system_prompt,
                "prompt": user_prompt,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
                "stream": False,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        body = response.json()
        self.record_usage(
            operation,
            int(body.get("prompt_eval_count", 0) or 0),
            int(body.get("eval_count", 0) or 0),
        )
        return str(body["response"])
