"""HTTP transports; the API key comes only from the environment variable the model spec names, and a set stop event aborts a request in flight."""

import asyncio
import os

import httpx

from ..specs import ModelSpec

WINDOW_FIELDS = (
    "context_window",
    "context_length",
    "max_input_tokens",
    "max_context_length",
    "input_token_limit",
)


class CompletionHTTPError(RuntimeError):
    def __init__(self, response):
        self.response = response
        self.status_code = response.status_code
        super().__init__(f"Provider HTTP {self.status_code}")


class CompatibleClient:
    def __init__(self, spec, http_client=None):
        self.spec, self.http = spec, http_client

    def post(self, path, body, *, timeout=120, cancel=None, headers=None):
        key = os.getenv(self.spec.api_key_env)
        if not key:
            raise ValueError(f"Missing environment variable {self.spec.api_key_env}")
        url = self.spec.base_url + path
        arguments = {
            "json": body,
            "headers": {"Authorization": f"Bearer {key}", **(headers or {})},
            "timeout": timeout,
        }
        if isinstance(self.http, httpx.Client):
            response = self.http.post(url, **arguments)
        else:

            async def cancellable(client):
                task = asyncio.create_task(client.post(url, **arguments))
                while not task.done():
                    if cancel is not None and cancel.is_set():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        raise TimeoutError("Request cancelled")
                    await asyncio.wait({task}, timeout=0.1)
                return task.result()

            async def request():
                if self.http is not None:
                    return await cancellable(self.http)
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    return await cancellable(client)

            response = asyncio.run(asyncio.wait_for(request(), timeout))
        if not 200 <= response.status_code < 300:
            raise CompletionHTTPError(response)
        return response

    def complete(self, body, *, timeout=120, cancel=None):
        from ..provider import InvalidResponse

        response = self.post("/chat/completions", body, timeout=timeout, cancel=cancel)
        try:
            return response.json()
        except ValueError:
            raise InvalidResponse("Malformed completion response") from None

    def context_window(self):
        key = os.getenv(self.spec.api_key_env, "")
        headers = {"Authorization": f"Bearer {key}"}
        get = self.http.get if isinstance(self.http, httpx.Client) else httpx.get
        try:
            response = get(self.spec.base_url + "/models", headers=headers, timeout=20)
            listed = response.json()
        except Exception:
            return None
        rows = listed.get("data", []) if isinstance(listed, dict) else listed
        for row in rows if isinstance(rows, list) else ():
            if isinstance(row, dict) and self.spec.model in (row.get("id"), row.get("name")):
                return next((row[f] for f in WINDOW_FIELDS if isinstance(row.get(f), int)), None)
        return None

    def close(self):
        if isinstance(self.http, httpx.Client):
            self.http.close()


def create_client(spec: ModelSpec):
    if spec.provider == "typesafe":
        from .typesafe import TypesafeClient

        return TypesafeClient(spec)
    return CompatibleClient(spec)
