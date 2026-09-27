"""Unit tests for config/ai/render_config.py (the ai-gateway's LiteLLM config) and the
lab_hooks messages. Stdlib only:  python3 -m unittest discover -s v3/tests/ai

The contract checks (CONTRACT Phase 5, OQ-8):
* nothing enabled -> empty model list (no provider = no outbound AI call), clear message;
* hosted providers exist only with their key, and keys never appear in the rendered file;
* every enabled provider is reachable as `lab-default` and its own name; no retries;
* no LiteLLM setting that would make the gateway call a provider by itself.
"""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_AI = os.path.join(V3, "config", "ai")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render_config = _load("render_config", os.path.join(CONFIG_AI, "render_config.py"))

SECRET_A = "sk-ant-unit-test-not-a-real-key-0000000000"
SECRET_O = "sk-unit-test-not-a-real-key-1111111111"


def render(**env):
    return render_config.render({k: v for k, v in env.items()})


class NothingEnabled(unittest.TestCase):
    def test_empty_model_list_and_message(self):
        config, state = render()
        self.assertEqual(config["model_list"], [])
        self.assertFalse(state["configured"])
        self.assertEqual(state["providers"], [])
        self.assertEqual(state["not_configured_message"], "AI isn't configured; ask your lab admin.")

    def test_blank_values_do_not_enable(self):
        config, state = render(LAB_AI_LOCAL_URL="  ", LAB_AI_ANTHROPIC_API_KEY="", LAB_AI_OPENAI_API_KEY=" ",
                               LAB_AI_MOCK="false", LAB_AI_LOCAL_MODEL="qwen")
        self.assertEqual(config["model_list"], [])
        self.assertFalse(state["configured"])

    def test_no_self_initiated_provider_calls(self):
        config, _ = render()
        gs, ls = config["general_settings"], config["litellm_settings"]
        self.assertIs(gs["background_health_checks"], False)
        self.assertIs(gs["store_model_in_db"], False)
        self.assertIs(ls["telemetry"], False)
        self.assertEqual(ls["num_retries"], 0)
        self.assertEqual(config["router_settings"]["num_retries"], 0)
        self.assertNotIn("health_check_interval", gs)
        self.assertEqual(ls["callbacks"], ["lab_hooks.proxy_handler_instance"])


class Providers(unittest.TestCase):
    def test_local(self):
        config, state = render(LAB_AI_LOCAL_URL="http://host.docker.internal:9999/v1/", LAB_AI_LOCAL_MODEL="qwen27b")
        names = [m["model_name"] for m in config["model_list"]]
        self.assertEqual(names, ["lab-default", "local"])
        p = config["model_list"][1]["litellm_params"]
        self.assertEqual(p["model"], "openai/qwen27b")
        self.assertEqual(p["api_base"], "http://host.docker.internal:9999/v1")
        self.assertEqual(p["input_cost_per_token"], 0.0)
        self.assertEqual(state["default_provider"], "local")

    def test_local_default_model_and_api_key_ref(self):
        config, _ = render(LAB_AI_LOCAL_URL="http://h:8080/v1", LAB_AI_LOCAL_API_KEY="abc")
        p = config["model_list"][0]["litellm_params"]
        self.assertEqual(p["model"], "openai/local")
        self.assertEqual(p["api_key"], "os.environ/LAB_AI_LOCAL_API_KEY")

    def test_hosted_needs_key_and_key_is_a_reference(self):
        config, state = render(LAB_AI_ANTHROPIC_API_KEY=SECRET_A, LAB_AI_OPENAI_API_KEY=SECRET_O)
        text = json.dumps(config)
        self.assertNotIn(SECRET_A, text)
        self.assertNotIn(SECRET_O, text)
        by = {m["model_name"]: m["litellm_params"] for m in config["model_list"]}
        self.assertEqual(by["claude"]["api_key"], "os.environ/LAB_AI_ANTHROPIC_API_KEY")
        self.assertEqual(by["claude"]["model"], "anthropic/" + render_config.DEFAULT_ANTHROPIC_MODEL)
        self.assertEqual(by["gpt"]["api_key"], "os.environ/LAB_AI_OPENAI_API_KEY")
        self.assertEqual(state["providers"], ["anthropic", "openai"])
        self.assertEqual(state["default_provider"], "anthropic")

    def test_model_override(self):
        config, _ = render(LAB_AI_OPENAI_API_KEY=SECRET_O, LAB_AI_OPENAI_MODEL="gpt-x")
        self.assertEqual(config["model_list"][0]["litellm_params"]["model"], "openai/gpt-x")

    def test_default_order_local_before_hosted(self):
        _, state = render(LAB_AI_ANTHROPIC_API_KEY=SECRET_A, LAB_AI_LOCAL_URL="http://h/v1")
        self.assertEqual(state["default_provider"], "local")

    def test_mock_wins_in_test_installs(self):
        config, state = render(LAB_AI_MOCK="true", LAB_AI_LOCAL_URL="http://h:9999/v1")
        self.assertEqual(state["default_provider"], "mock")
        self.assertEqual(config["model_list"][0]["litellm_params"]["api_base"], render_config.DEFAULT_MOCK_URL)
        self.assertEqual(config["model_list"][0]["litellm_params"]["input_cost_per_token"], 1000 / 1e6)

    def test_explicit_default(self):
        _, state = render(LAB_AI_MOCK="true", LAB_AI_LOCAL_URL="http://h/v1", LAB_AI_DEFAULT_PROVIDER="local")
        self.assertEqual(state["default_provider"], "local")
        # A default that is not enabled falls back instead of failing the start.
        _, state = render(LAB_AI_LOCAL_URL="http://h/v1", LAB_AI_DEFAULT_PROVIDER="anthropic")
        self.assertEqual(state["default_provider"], "local")

    def test_invalid_values_fail_loudly(self):
        for env in ({"LAB_AI_LOCAL_URL": "ftp://h"}, {"LAB_AI_DEFAULT_PROVIDER": "bogus"},
                    {"LAB_AI_MOCK": "true", "LAB_AI_MOCK_COST_PER_MTOK": "cheap"},
                    {"LAB_AI_LOCAL_URL": "http://h", "LAB_AI_LOCAL_COST_PER_MTOK": "-1"}):
            with self.assertRaises(SystemExit, msg=env):
                render_config.render(env)

    def test_anthropic_messages_use_chat_completions(self):
        config, _ = render(LAB_AI_LOCAL_URL="http://h/v1")
        self.assertIs(config["litellm_settings"]["use_chat_completions_url_for_anthropic_messages"], True)


class Files(unittest.TestCase):
    def test_main_writes_json_config_and_state(self):
        with tempfile.TemporaryDirectory() as d:
            old = dict(os.environ)
            try:
                for k in list(os.environ):
                    if k.startswith("LAB_AI_"):
                        del os.environ[k]
                os.environ["LAB_AI_MOCK"] = "true"
                render_config.main(["render_config.py", d])
            finally:
                os.environ.clear()
                os.environ.update(old)
            with open(os.path.join(d, "config.yaml")) as f:
                config = json.load(f)  # JSON is YAML: LiteLLM reads it as its config
            with open(os.path.join(d, "state.json")) as f:
                state = json.load(f)
        self.assertEqual(state["models"], ["lab-default", "mock"])
        self.assertEqual(config["general_settings"]["master_key"], "os.environ/LITELLM_MASTER_KEY")


class Hooks(unittest.TestCase):
    """lab_hooks.py with stand-ins for fastapi/litellm (not installed in CI's lint job)."""

    @classmethod
    def setUpClass(cls):
        fastapi = types.ModuleType("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code, detail=None):
                super().__init__(detail)
                self.status_code, self.detail = status_code, detail

        fastapi.HTTPException = HTTPException
        custom = types.ModuleType("litellm.integrations.custom_logger")

        class CustomLogger:
            def __init__(self, *a, **k):
                pass

        custom.CustomLogger = CustomLogger
        for name, mod in (("fastapi", fastapi), ("litellm", types.ModuleType("litellm")),
                          ("litellm.integrations", types.ModuleType("litellm.integrations")),
                          ("litellm.integrations.custom_logger", custom)):
            sys.modules.setdefault(name, mod)
        cls.HTTPException = sys.modules["fastapi"].HTTPException
        cls.hooks = _load("lab_hooks", os.path.join(CONFIG_AI, "lab_hooks.py"))

    def run_async(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_not_configured_refuses_before_routing(self):
        h = self.hooks.LabHooks()
        h.state = {"configured": False}
        with self.assertRaises(self.HTTPException) as cm:
            self.run_async(h.async_pre_call_hook(None, None, {"model": "lab-default"}, "completion"))
        self.assertEqual(cm.exception.status_code, 503)
        self.assertEqual(cm.exception.detail["error"]["message"], "AI isn't configured; ask your lab admin.")

    def test_configured_passes_data_through(self):
        h = self.hooks.LabHooks()
        h.state = {"configured": True}
        data = {"model": "lab-default"}
        self.assertIs(self.run_async(h.async_pre_call_hook(None, None, data, "completion")), data)

    def test_budget_message(self):
        h = self.hooks.LabHooks()
        exc = Exception("ExceededBudget: User=alice over budget. Spend=5.25, Budget=5.0")
        out = self.run_async(h.async_post_call_failure_hook({}, exc, None))
        self.assertEqual(out.status_code, 400)
        self.assertIn("Your AI budget for this period is used up", out.detail)
        self.assertIn("5.25 of your 5.00 USD", out.detail)
        self.assertIsNone(self.run_async(h.async_post_call_failure_hook({}, Exception("other"), None)))

    def test_budget_error_by_type(self):
        e = Exception("x")
        e.type = "budget_exceeded"
        self.assertTrue(self.hooks.is_budget_error(e))
        self.assertIn("used up", self.hooks.budget_message(e))


if __name__ == "__main__":
    unittest.main()
