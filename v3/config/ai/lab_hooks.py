"""LiteLLM proxy hooks for the lab (a CustomLogger callback: an open-source LiteLLM feature).

Loaded by the gateway through `litellm_settings.callbacks: [lab_hooks.proxy_handler_instance]`
(render_config.py). Two jobs, both about giving users a clear message instead of a stack of
provider jargon:

1. No provider enabled -> every model call is refused BEFORE routing with
   "AI isn't configured; ask your lab admin." (HTTP 503, type `ai_not_configured`). The model
   list is empty then, so there is also nothing to route to (no outbound AI call).
2. A user past their budget -> LiteLLM's "ExceededBudget: User=... over budget. Spend=...,
   Budget=..." becomes a plain sentence with the numbers (HTTP 400, same status as LiteLLM's).

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


class LabHooks(CustomLogger):
    def __init__(self):
        super().__init__()
        self.state = _load_state()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if not self.state.get("configured"):
            raise HTTPException(status_code=503, detail={
                "error": {"message": NOT_CONFIGURED, "type": "ai_not_configured", "code": 503}})
        return data

    async def async_post_call_failure_hook(self, request_data, original_exception,
                                           user_api_key_dict, traceback_str=None):
        if is_budget_error(original_exception):
            # A plain-string detail: the auth path puts `detail` into the error message as is.
            return HTTPException(status_code=400, detail=budget_message(original_exception))
        return None


proxy_handler_instance = LabHooks()
