"""LiteLLM proxy hooks for the lab (a CustomLogger callback: an open-source LiteLLM feature).

Loaded by the gateway through `litellm_settings.callbacks: [lab_hooks.proxy_handler_instance]`
(render_config.py). Three jobs:

1. No provider enabled -> every model call is refused BEFORE routing with
   "AI isn't configured; ask your lab admin." (HTTP 503, type `ai_not_configured`). The model
   list is empty then, so there is also nothing to route to (no outbound AI call).
2. A user past their budget -> LiteLLM's "ExceededBudget: User=... over budget. Spend=...,
   Budget=..." becomes a plain sentence with the numbers (HTTP 400, same status as LiteLLM's).
3. Attribution: the end user of every call is the KEY'S OWN user. LiteLLM takes the "end
   user" from the request body (`user`, or customer-id headers, which the AI front door
   drops) and records it in the spend logs; a user could name anyone there. The pre-call hook
   OVERWRITES the body's `user` and the end-user id in the request metadata with the key's
   user_id (key without a user, i.e. the admin: removed), so spend logs attribute correctly.

The state (configured or not) comes from state.json, written next to this file by
render_config.py at container start.
"""
import json
import os
import re

from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger

_HERE = os.path.dirname(os.path.abspath(__file__))
NOT_CONFIGURED = "AI isn't configured; ask your lab admin."
_SPEND = re.compile(r"(?:Spend=|Current cost:\s*)([0-9.eE+-]+)")
_BUDGET = re.compile(r"(?:Budget=|Max budget:\s*)([0-9.eE+-]+)")


def _load_state():
    try:
        with open(os.path.join(_HERE, "state.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"configured": False}


def _money(raw):
    try:
        return f"{float(raw):.2f}"
    except (TypeError, ValueError):
        return "?"


def is_budget_error(exc):
    """LiteLLM raises BudgetExceededError / ProxyException(type=budget_exceeded)."""
    if type(exc).__name__ == "BudgetExceededError":
        return True
    if str(getattr(exc, "type", "") or "") == "budget_exceeded":
        return True
    text = str(getattr(exc, "message", "") or exc)
    return "ExceededBudget" in text or "Budget has been exceeded" in text


def budget_message(exc):
    text = str(getattr(exc, "message", "") or exc)
    s, b = _SPEND.search(text), _BUDGET.search(text)
    used = (f" You have used {_money(s.group(1))} of your {_money(b.group(1))} USD AI budget."
            if s and b else "")
    return ("Your AI budget for this period is used up." + used +
            " It resets at the start of the next budget period; ask your lab admin if you need more.")


def attribute_to_key_owner(data, user_api_key_dict):
    """The request's end user := the key's own user_id, whatever the caller sent. LiteLLM
    puts the end user into the request metadata (`metadata` or, on /v1/messages,
    `litellm_metadata`) as `user_api_key_end_user_id`, which the spend log records."""
    owner = getattr(user_api_key_dict, "user_id", None) or None
    if owner:
        data["user"] = owner
    else:
        data.pop("user", None)
    user_api_key_dict.end_user_id = owner
    for slot in ("metadata", "litellm_metadata"):
        meta = data.get(slot)
        if not isinstance(meta, dict):
            continue
        meta["user_api_key_end_user_id"] = owner
        auth = meta.get("user_api_key_auth")
        if auth is not None and hasattr(auth, "end_user_id"):
            auth.end_user_id = owner
    return data


class LabHooks(CustomLogger):
    def __init__(self):
        super().__init__()
        self.state = _load_state()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if not self.state.get("configured"):
            raise HTTPException(status_code=503, detail={
                "error": {"message": NOT_CONFIGURED, "type": "ai_not_configured", "code": 503}})
        return attribute_to_key_owner(data, user_api_key_dict)

    async def async_post_call_failure_hook(self, request_data, original_exception,
                                           user_api_key_dict, traceback_str=None):
        if is_budget_error(original_exception):
            # A plain-string detail: the auth path puts `detail` into the error message as is.
            return HTTPException(status_code=400, detail=budget_message(original_exception))
        return None


proxy_handler_instance = LabHooks()
