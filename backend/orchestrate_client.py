"""
Thin async client for calling watsonx Orchestrate agents.

Auth:  API key -> bearer token (cached until shortly before expiry).
Call:  POST {WO_INSTANCE}/v1/orchestrate/{agent_id}/chat/completions
       The response is streamed as server-sent events; content deltas are joined.
"""

from __future__ import annotations

import json
import os
import time

import httpx

DEFAULT_AUTH_URL = "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token"
IBM_CLOUD_IAM_URL = "https://iam.cloud.ibm.com/identity/token"


class OrchestrateError(Exception):
    pass


class OrchestrateClient:
    def __init__(
        self,
        instance_url: str,
        api_key: str,
        auth_url: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not instance_url or not api_key:
            raise OrchestrateError("WO_INSTANCE and WO_API_KEY must be set")
        self.instance_url = instance_url.rstrip("/")
        self.api_key = api_key
        self.auth_url = auth_url or DEFAULT_AUTH_URL
        self.timeout = timeout
        self._transport = transport
        self._token: str | None = None
        self._token_expiry = 0.0

    @classmethod
    def from_env(cls, transport: httpx.AsyncBaseTransport | None = None) -> "OrchestrateClient":
        return cls(
            instance_url=os.environ.get("WO_INSTANCE", ""),
            api_key=os.environ.get("WO_API_KEY", ""),
            auth_url=os.environ.get("WO_AUTH_URL") or None,
            timeout=float(os.environ.get("WO_TIMEOUT", "60")),
            transport=transport,
        )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self._transport)

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 120:
            return self._token
        async with self._client() as client:
            if "iam.cloud.ibm.com" in self.auth_url:
                resp = await client.post(
                    self.auth_url,
                    data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self.api_key},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            else:
                resp = await client.post(self.auth_url, json={"apikey": self.api_key})
        if resp.status_code != 200:
            raise OrchestrateError(f"token request failed: HTTP {resp.status_code}")
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            raise OrchestrateError("token response had no token")
        self._token = token
        expires_in = data.get("expires_in")
        self._token_expiry = time.time() + (float(expires_in) if expires_in else 3600.0)
        return token

    async def chat(self, agent_id: str, content: str) -> str:
        """Send one user message to an agent and return the full reply text."""
        if not agent_id:
            raise OrchestrateError("agent id not configured")
        token = await self._get_token()
        url = f"{self.instance_url}/v1/orchestrate/{agent_id}/chat/completions"
        body = {"messages": [{"role": "user", "content": content}]}
        async with self._client() as client:
            resp = await client.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if resp.status_code == 401:
            self._token = None
        if resp.status_code != 200:
            raise OrchestrateError(f"agent call failed: HTTP {resp.status_code}")
        return parse_reply(resp.text)


def parse_reply(raw: str) -> str:
    """Join SSE content deltas; fall back to a plain JSON chat-completion body."""
    chunks: list[str] = []
    final: str | None = None  # full text from a completed-message event
    saw_sse = False
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        saw_sse = True
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        for choice in event.get("choices", []) or []:
            delta = (choice.get("delta") or {}).get("content")
            if delta:
                chunks.append(delta)
            elif (choice.get("message") or {}).get("content"):
                # Orchestrate repeats the whole reply in a final event; use it only if no deltas arrived.
                final = choice["message"]["content"]
    if saw_sse:
        return "".join(chunks) or final or ""
    try:
        body = json.loads(raw)
        return body["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return raw
