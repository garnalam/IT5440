"""Ollama native /api/chat adapter for local GPU runs (IT5440 addition).

Why not openai_compat: Ollama's OpenAI-compatible /v1 endpoint ignores
"think": false for thinking models (e.g. qwen3.5), so the model burns its
output budget thinking and returns empty content. The native API honours it
(proven pattern from it5440-5kh-local-runs). num_ctx must also be set
explicitly: Ollama's default window is small and long prompts are silently
truncated, which would fake a "missing evidence" failure.
"""

import os
import time

from ccbench.providers.base import Provider, Response
from ccbench.providers.http import classify_http, post_json


class OllamaNativeProvider(Provider):
    name = "ollama_native"
    supports = {"temperature": True, "seed": True, "usage": True, "cost": False}

    def __init__(self, model, base_url=None, num_ctx=32768, think=None, keep_alive="30m", **kw):
        super().__init__(model, **kw)
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")).rstrip("/")
        self.num_ctx = int(num_ctx)
        self.think = think
        self.keep_alive = keep_alive

    def effective_params(self):
        p = super().effective_params()
        p.update({"num_ctx": self.num_ctx, "think": self.think, "base_url": self.base_url})
        return p

    def _call(self, system, prompt, max_tokens, meta):
        options = {"temperature": self.temperature, "num_predict": max_tokens, "num_ctx": self.num_ctx}
        if self.seed is not None:
            options["seed"] = self.seed
        payload = {"model": self.model, "stream": False, "keep_alive": self.keep_alive,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                   "options": options}
        if self.think is not None:
            payload["think"] = bool(self.think)
        t0 = time.monotonic()
        status, body = post_json(self.base_url + "/api/chat", payload, {}, self.timeout)
        latency = time.monotonic() - t0
        if status != 200 or "message" not in body:
            return Response(error=str(body)[:500], error_kind=classify_http(status, body), latency_s=latency)
        msg = body.get("message") or {}
        extra = {"done_reason": body.get("done_reason"),
                 "thinking_chars": len(msg.get("thinking") or ""),
                 "num_ctx": self.num_ctx,
                 "load_duration_ms": round((body.get("load_duration") or 0) / 1e6),
                 "prompt_eval_duration_ms": round((body.get("prompt_eval_duration") or 0) / 1e6),
                 "eval_duration_ms": round((body.get("eval_duration") or 0) / 1e6)}
        return Response(text=msg.get("content") or "", model_id=body.get("model", self.model),
                        input_tokens=body.get("prompt_eval_count"), output_tokens=body.get("eval_count"),
                        cost_usd=0.0, cost_source="local GPU (no API cost)", latency_s=latency, extra=extra)