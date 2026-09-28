"""Unit tests for the local model's quiet hours (CONTRACT Phase 6, AI polish (a)):
config/ai/render_config.py (parse, window test with an INJECTED clock, the state the gateway
reads) and the lab_hooks pre-call refusal. Stdlib only, no gateway, never a model call.

    python3 -m unittest discover -s v3/tests/ai -p 'test_quiet_hours.py' -v

Windows are wall-clock times in the configured zone: they cross midnight when start > end, and
they follow DST (America/New_York: 2026-03-08 02:00 -> 03:00, 2026-11-01 02:00 -> 01:00).
"""
import asyncio
import datetime as dt
import importlib.util
import os
import sys
import types
import unittest
from zoneinfo import ZoneInfo

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_AI = os.path.join(V3, "config", "ai")
UTC = dt.timezone.utc
NY = ZoneInfo("America/New_York")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = _load("render_config_qh", os.path.join(CONFIG_AI, "render_config.py"))


def ny(y, mo, d, h, mi, fold=0):
    """A New York wall-clock instant (aware)."""
    return dt.datetime(y, mo, d, h, mi, tzinfo=NY, fold=fold)


def until(now, spec, tz=NY):
    return rc.quiet_until(now, rc.parse_quiet_hours(spec), tz)


class Parse(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(rc.parse_quiet_hours("22:00-07:00"), (22 * 60, 7 * 60))
        self.assertEqual(rc.parse_quiet_hours("00:00-23:59"), (0, 23 * 60 + 59))
        self.assertEqual(rc.parse_quiet_hours(" 09:30-17:45 "), (570, 1065))

    def test_off(self):
        for spec in ("", "off", "OFF", "none", None, "  "):
            self.assertIsNone(rc.parse_quiet_hours(spec), spec)

    def test_invalid(self):
        for spec in ("7:00-22:00", "22:00", "24:00-07:00", "22:60-07:00", "22:00-07:00x",
                     "22.00-07.00", "22:00 - 07:00", "07:00-07:00", "ab:cd-ef:gh", "22:00-07:00;x"):
            with self.assertRaises(ValueError, msg=spec):
                rc.parse_quiet_hours(spec)

    def test_zone(self):
        self.assertEqual(str(rc.quiet_zone("America/New_York")), "America/New_York")
        self.assertEqual(str(rc.quiet_zone(":Europe/Berlin")), "Europe/Berlin")
        for bad in ("", "Mars/Olympus", "../../etc/passwd", "/etc/localtime", "America/New York"):
            with self.assertRaises(ValueError, msg=bad):
                rc.quiet_zone(bad)


class Window(unittest.TestCase):
    def test_same_day_window(self):
        self.assertIsNone(until(ny(2026, 9, 27, 8, 59), "09:00-17:00"))
        self.assertEqual(until(ny(2026, 9, 27, 9, 0), "09:00-17:00"), ny(2026, 9, 27, 17, 0))
        self.assertEqual(until(ny(2026, 9, 27, 16, 59), "09:00-17:00"), ny(2026, 9, 27, 17, 0))
        self.assertIsNone(until(ny(2026, 9, 27, 17, 0), "09:00-17:00"))     # end exclusive

    def test_across_midnight(self):
        spec = "22:00-07:00"
        self.assertIsNone(until(ny(2026, 9, 27, 21, 59), spec))
        self.assertEqual(until(ny(2026, 9, 27, 22, 0), spec), ny(2026, 9, 28, 7, 0))
        self.assertEqual(until(ny(2026, 9, 27, 23, 59), spec), ny(2026, 9, 28, 7, 0))
        self.assertEqual(until(ny(2026, 9, 28, 0, 0), spec), ny(2026, 9, 28, 7, 0))
        self.assertEqual(until(ny(2026, 9, 28, 6, 59), spec), ny(2026, 9, 28, 7, 0))
        self.assertIsNone(until(ny(2026, 9, 28, 7, 0), spec))
        self.assertIsNone(until(ny(2026, 9, 28, 12, 0), spec))

    def test_month_and_year_end(self):
        self.assertEqual(until(ny(2026, 12, 31, 23, 30), "22:00-07:00"), ny(2027, 1, 1, 7, 0))

    def test_now_in_any_zone(self):
        # 03:00 UTC is 23:00 in New York (EDT, UTC-4): inside 22:00-07:00 there.
        now = dt.datetime(2026, 9, 28, 3, 0, tzinfo=UTC)
        self.assertEqual(until(now, "22:00-07:00"), ny(2026, 9, 28, 7, 0))
        # ... and 05:00 in Berlin (CEST): inside 22:00-07:00 there too, but not inside 00:00-04:00.
        berlin = ZoneInfo("Europe/Berlin")
        self.assertIsNotNone(until(now, "22:00-07:00", berlin))
        self.assertIsNone(until(now, "00:00-04:00", berlin))

    def test_naive_clock_refused(self):
        with self.assertRaises(ValueError):
            until(dt.datetime(2026, 9, 27, 23, 0), "22:00-07:00")

    def test_off_is_never_quiet(self):
        self.assertIsNone(rc.quiet_until(ny(2026, 9, 27, 23, 0), None, NY))


class Dst(unittest.TestCase):
    """New York, 2026: spring forward on 03-08 (02:00 EST -> 03:00 EDT), fall back on 11-01
    (02:00 EDT -> 01:00 EST). The window is wall-clock, so it ends at 07:00 local both days."""

    def test_spring_forward_night_is_one_hour_shorter(self):
        start = ny(2026, 3, 7, 22, 0)                       # 22:00 EST = 03:00 UTC
        end = until(start, "22:00-07:00")
        self.assertEqual(end, ny(2026, 3, 8, 7, 0))         # 07:00 EDT = 11:00 UTC
        self.assertEqual(end.astimezone(UTC) - start.astimezone(UTC), dt.timedelta(hours=8))
        # Just after the jump (03:00 EDT = 07:00 UTC): still quiet, same end.
        self.assertEqual(until(dt.datetime(2026, 3, 8, 7, 0, tzinfo=UTC), "22:00-07:00"),
                         ny(2026, 3, 8, 7, 0))
        # 07:00 EDT (11:00 UTC) is the end; 10:59 UTC (06:59 EDT) is the last quiet minute.
        self.assertIsNone(until(dt.datetime(2026, 3, 8, 11, 0, tzinfo=UTC), "22:00-07:00"))
        self.assertIsNotNone(until(dt.datetime(2026, 3, 8, 10, 59, tzinfo=UTC), "22:00-07:00"))

    def test_fall_back_night_is_one_hour_longer(self):
        start = ny(2026, 10, 31, 22, 0)                     # 22:00 EDT = 02:00 UTC
        end = until(start, "22:00-07:00")
        self.assertEqual(end, ny(2026, 11, 1, 7, 0))        # 07:00 EST = 12:00 UTC
        self.assertEqual(end.astimezone(UTC) - start.astimezone(UTC), dt.timedelta(hours=10))
        self.assertIsNotNone(until(dt.datetime(2026, 11, 1, 11, 59, tzinfo=UTC), "22:00-07:00"))
        self.assertIsNone(until(dt.datetime(2026, 11, 1, 12, 0, tzinfo=UTC), "22:00-07:00"))

    def test_window_inside_the_skipped_hour(self):
        # 02:15-02:45 does not exist on 2026-03-08 in New York: that day is never quiet.
        for utc_minute in range(6 * 60, 8 * 60):            # 01:00 EST .. 04:00 EDT
            now = dt.datetime(2026, 3, 8, utc_minute // 60, utc_minute % 60, tzinfo=UTC)
            self.assertIsNone(until(now, "02:15-02:45"), now)
        # The day before, it is.
        self.assertIsNotNone(until(ny(2026, 3, 7, 2, 30), "02:15-02:45"))

    def test_start_in_the_skipped_hour(self):
        # 02:30-06:00 on the spring-forward day starts at the first wall-clock minute past
        # 02:30, which is 03:00 EDT.
        self.assertIsNone(until(dt.datetime(2026, 3, 8, 6, 59, tzinfo=UTC), "02:30-06:00"))  # 01:59 EST
        self.assertEqual(until(dt.datetime(2026, 3, 8, 7, 0, tzinfo=UTC), "02:30-06:00"),    # 03:00 EDT
                         ny(2026, 3, 8, 6, 0))

    def test_repeated_hour_is_quiet_both_times(self):
        # 01:00-02:00 on the fall-back day: 01:30 happens twice (EDT, then EST); both quiet.
        first = ny(2026, 11, 1, 1, 30, fold=0)
        second = ny(2026, 11, 1, 1, 30, fold=1)
        self.assertEqual(second.astimezone(UTC) - first.astimezone(UTC), dt.timedelta(hours=1))
        self.assertIsNotNone(until(first, "01:00-02:00"))
        self.assertIsNotNone(until(second, "01:00-02:00"))
        self.assertIsNone(until(ny(2026, 11, 1, 2, 0), "01:00-02:00"))

    def test_retry_after_counts_real_seconds_across_dst(self):
        state = {"quiet_hours": {"window": "22:00-07:00", "tz": "America/New_York"},
                 "local_models": ["local"]}
        # 01:00 EST on the spring-forward day -> 07:00 EDT is 5 real hours later, not 6.
        now = ny(2026, 3, 8, 1, 0)
        _msg, seconds = rc.quiet_refusal(state, "local", now)
        self.assertEqual(seconds, 5 * 3600)
        # 00:30 EDT on the fall-back day -> 07:00 EST is 7.5 real hours later.
        _msg, seconds = rc.quiet_refusal(state, "local", ny(2026, 11, 1, 0, 30))
        self.assertEqual(seconds, 7 * 3600 + 1800)


class State(unittest.TestCase):
    def test_default_off(self):
        _config, state = rc.render({"LAB_AI_LOCAL_URL": "http://h:8080/v1"})
        self.assertIsNone(state["quiet_hours"])
        self.assertEqual(state["local_models"], ["lab-default", "local"])

    def test_on_with_zone(self):
        _c, state = rc.render({"LAB_AI_LOCAL_URL": "http://h:8080/v1",
                               "LAB_AI_QUIET_HOURS": "22:00-07:00",
                               "LAB_AI_QUIET_TZ": "America/New_York"})
        self.assertEqual(state["quiet_hours"], {"window": "22:00-07:00", "tz": "America/New_York"})

    def test_zone_defaults_to_tz_then_utc(self):
        _c, s1 = rc.render({"LAB_AI_QUIET_HOURS": "22:00-07:00", "TZ": "Europe/Berlin"})
        self.assertEqual(s1["quiet_hours"]["tz"], "Europe/Berlin")
        _c, s2 = rc.render({"LAB_AI_QUIET_HOURS": "22:00-07:00"})
        self.assertEqual(s2["quiet_hours"]["tz"], "UTC")

    def test_off_values(self):
        for v in ("", "off"):
            _c, s = rc.render({"LAB_AI_QUIET_HOURS": v, "LAB_AI_QUIET_TZ": "Nowhere/Nope"})
            self.assertIsNone(s["quiet_hours"])

    def test_bad_settings_stop_the_gateway(self):
        for env in ({"LAB_AI_QUIET_HOURS": "10pm-7am"},
                    {"LAB_AI_QUIET_HOURS": "22:00-07:00", "LAB_AI_QUIET_TZ": "Mars/Olympus"}):
            with self.assertRaises(SystemExit, msg=env):
                rc.render(env)

    def test_local_models_follow_lab_default(self):
        env = {"LAB_AI_LOCAL_URL": "http://h:8080/v1", "LAB_AI_ANTHROPIC_API_KEY": "sk-ant-x" * 4}
        _c, s = rc.render(env)
        self.assertEqual(s["local_models"], ["lab-default", "local"])
        _c, s = rc.render(dict(env, LAB_AI_DEFAULT_PROVIDER="anthropic"))
        self.assertEqual(s["local_models"], ["local"])              # lab-default -> hosted
        _c, s = rc.render(dict(env, LAB_AI_MOCK="true"))
        self.assertEqual(s["local_models"], ["local"])              # lab-default -> mock
        _c, s = rc.render({"LAB_AI_MOCK": "true"})
        self.assertEqual(s["local_models"], [])                     # no local provider


class Refusal(unittest.TestCase):
    STATE = {"configured": True, "quiet_hours": {"window": "22:00-07:00", "tz": "America/New_York"},
             "local_models": ["lab-default", "local"]}

    def test_message_names_end_and_zone(self):
        msg, seconds = rc.quiet_refusal(self.STATE, "local", ny(2026, 9, 27, 23, 0))
        self.assertTrue(msg.startswith("The lab's local AI model is resting until 07:00 America/New_York"), msg)
        self.assertIn("quiet hours 22:00-07:00", msg)
        self.assertEqual(seconds, 8 * 3600)

    def test_lab_default_resolving_to_local_is_refused(self):
        self.assertIsNotNone(rc.quiet_refusal(self.STATE, "lab-default", ny(2026, 9, 27, 23, 0)))

    def test_hosted_and_mock_not_affected(self):
        for model in ("claude", "gpt", "mock", ""):
            self.assertIsNone(rc.quiet_refusal(self.STATE, model, ny(2026, 9, 27, 23, 0)), model)

    def test_outside_window_and_off(self):
        self.assertIsNone(rc.quiet_refusal(self.STATE, "local", ny(2026, 9, 27, 12, 0)))
        self.assertIsNone(rc.quiet_refusal(dict(self.STATE, quiet_hours=None), "local",
                                           ny(2026, 9, 27, 23, 0)))
        self.assertIsNone(rc.quiet_refusal({}, "local", ny(2026, 9, 27, 23, 0)))


class Hook(unittest.TestCase):
    """lab_hooks' pre-call hook with stand-ins for fastapi/litellm, and a fixed clock."""

    @classmethod
    def setUpClass(cls):
        fastapi = types.ModuleType("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code, detail=None, headers=None):
                super().__init__(detail)
                self.status_code, self.detail, self.headers = status_code, detail, headers

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
        cls.hooks = _load("lab_hooks_qh", os.path.join(CONFIG_AI, "lab_hooks.py"))

    def call(self, model, now, state=None):
        h = self.hooks.LabHooks()
        h.state = state or Refusal.STATE
        h.clock = lambda: now
        key = types.SimpleNamespace(user_id="alice", end_user_id=None)
        return asyncio.run(h.async_pre_call_hook(key, None, {"model": model}, "acompletion"))

    def test_default_clock_is_utc_now(self):
        t = self.hooks.LabHooks.clock()
        self.assertEqual(t.utcoffset(), dt.timedelta(0))
        self.assertLess(abs((t - dt.datetime.now(UTC)).total_seconds()), 5)

    def test_refused_before_routing(self):
        for model in ("local", "lab-default"):
            with self.assertRaises(self.HTTPException) as cm:
                self.call(model, ny(2026, 9, 28, 1, 0))
            e = cm.exception
            self.assertEqual(e.status_code, 503)
            self.assertEqual(e.detail["error"]["type"], "ai_quiet_hours")
            self.assertIn("resting until 07:00 America/New_York", e.detail["error"]["message"])
            self.assertEqual(e.headers, {"Retry-After": str(6 * 3600)})

    def test_passes_outside_and_for_hosted(self):
        self.assertEqual(self.call("local", ny(2026, 9, 28, 7, 0))["model"], "local")
        self.assertEqual(self.call("claude", ny(2026, 9, 28, 1, 0))["model"], "claude")

    def test_not_configured_still_wins(self):
        with self.assertRaises(self.HTTPException) as cm:
            self.call("local", ny(2026, 9, 28, 1, 0), state=dict(Refusal.STATE, configured=False))
        self.assertEqual(cm.exception.detail["error"]["type"], "ai_not_configured")


if __name__ == "__main__":
    unittest.main()
