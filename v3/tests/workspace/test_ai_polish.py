"""Unit tests for the Phase 6 AI polish in the workspace (CONTRACT Phase 6, 2b and 2c):
lakehouse/ai.py `clock_block` / `system_prompt` (the current date, time and time zone, with an
injected clock) and `ReplyShaper` (the model's planning and tool-use narration kept out of the
final answer). No Jupyter AI, no network, never a model call.

fixtures/agent_events_narration.json is a RECORDED event sequence: LangChain 1.4.2's
`create_agent(...).astream_events(..., version="v3")` (the workspace lock's versions) with
ChatLiteLLM against tests/ai/mock_llm scripted to send reasoning, narration with two tool-call
turns, then a final answer that itself starts with planning:
  step 0  reasoning "The user is asking about tables. I should call the tool."
          text "The user is asking which tables feed the dashboard. Let me look that up."
          tool call lookup
  step 1  text "Now let me check snapshots."  tool calls lookup, other
  step 2  text "The user wants the tables. I'll summarize.\n\nThe tables are **a** ..."

    python3 -m unittest discover -s v3/tests/workspace -p 'test_ai_polish.py' -v
"""
import datetime as dt
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(V3, "images", "workspace"))
sys.path.insert(0, HERE)

from lakehouse import ai  # noqa: E402
from test_lab_ai import Base  # noqa: E402

UTC = dt.timezone.utc
FIXTURE = os.path.join(HERE, "fixtures", "agent_events_narration.json")
FINAL = "The tables are **a** and **b**.\n\n```sql\nSELECT 1\n```\n\nLoaded today."


def events():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def shaped(evs, final=True):
    s = ai.ReplyShaper()
    for d in evs:
        s.feed(d)
    return s, s.render(final=final)


# ---------------------------------------------------------------------------- (b) the clock
class Clock(unittest.TestCase):
    NOW = dt.datetime(2026, 9, 27, 14, 5, tzinfo=UTC)

    def test_date_time_and_zone(self):
        b = ai.clock_block(self.NOW, env={"LAB_TZ": "America/New_York"})
        self.assertIn("Right now it is Sunday, 27 September 2026, 10:05 in the lab's time zone, "
                      "America/New_York (UTC-04:00).", b)
        self.assertIn("Today is 2026-09-27; yesterday was 2026-09-26.", b)

    def test_local_date_differs_from_utc(self):
        # 03:30 UTC on the 28th is still the 27th in New York.
        b = ai.clock_block(dt.datetime(2026, 9, 28, 3, 30, tzinfo=UTC), env={"LAB_TZ": "America/New_York"})
        self.assertIn("Sunday, 27 September 2026, 23:30", b)
        self.assertIn("Today is 2026-09-27; yesterday was 2026-09-26.", b)
        b = ai.clock_block(dt.datetime(2026, 9, 27, 23, 30, tzinfo=UTC), env={"LAB_TZ": "Asia/Tokyo"})
        self.assertIn("Monday, 28 September 2026, 08:30", b)
        self.assertIn("Asia/Tokyo (UTC+09:00)", b)
        self.assertIn("Today is 2026-09-28; yesterday was 2026-09-27.", b)

    def test_zone_sources(self):
        self.assertEqual(ai.lab_timezone({"LAB_TZ": "Europe/Berlin", "TZ": "Asia/Tokyo"})[1], "Europe/Berlin")
        self.assertEqual(ai.lab_timezone({"TZ": ":Asia/Tokyo"})[1], "Asia/Tokyo")   # hub sets TZ
        self.assertEqual(ai.lab_timezone({})[1], "UTC")
        for bad in ("Mars/Olympus", "../etc/passwd", "/etc/localtime", ""):
            self.assertEqual(ai.lab_timezone({"LAB_TZ": bad})[1], "UTC", bad)
        self.assertEqual(ai.lab_timezone({"LAB_TZ": "Nope/Zone", "TZ": "Europe/Paris"})[1], "Europe/Paris")
        b = ai.clock_block(self.NOW, env={})
        self.assertIn("14:05 in the lab's time zone, UTC (UTC+00:00)", b)

    def test_dst(self):
        winter = ai.clock_block(dt.datetime(2026, 1, 15, 12, 0, tzinfo=UTC), env={"LAB_TZ": "America/New_York"})
        self.assertIn("07:00 in the lab's time zone, America/New_York (UTC-05:00)", winter)

    def test_default_clock_is_now(self):
        b = ai.clock_block(env={"LAB_TZ": "UTC"})
        self.assertIn(f"Today is {dt.datetime.now(UTC):%Y-%m-%d}", b)


class PromptCarriesClock(Base):
    def test_system_prompt_has_the_clock(self):
        os.environ["LAB_TZ"] = "America/New_York"
        try:
            prompt, _ = ai.system_prompt(username="alice", now=Clock.NOW)
        finally:
            os.environ.pop("LAB_TZ", None)
        self.assertIn("<lab_clock>", prompt)
        self.assertIn("Sunday, 27 September 2026, 10:05", prompt)
        self.assertIn("America/New_York (UTC-04:00)", prompt)
        self.assertIn("yesterday was 2026-09-26", prompt)
        # After the lab context and safety rules, before the style rules.
        self.assertLess(prompt.index("<lab_context>"), prompt.index("<lab_clock>"))
        self.assertLess(prompt.index("<lab_clock>"), prompt.index("<response_style>"))

    def test_with_tutor_mode_too(self):
        self.write("analyst/A1-sql/probe.chat", "{}", root=os.path.join(self.home, "tracks"))
        prompt, module = ai.system_prompt(chat_dir=os.path.join(self.home, "tracks", "analyst", "A1-sql"),
                                          username="alice", now=Clock.NOW)
        self.assertIsNotNone(module)
        self.assertIn("<lab_tutor_mode", prompt)
        self.assertIn("<lab_clock>", prompt)

    def test_style_asks_for_answer_first(self):
        prompt, _ = ai.system_prompt(username="alice", now=Clock.NOW)
        self.assertIn("Begin the final answer with the answer itself", prompt)
        self.assertNotIn("When you use a tool,\nsay briefly what you looked up", prompt)


# ---------------------------------------------------------------------------- (c) narration
class RecordedAgentReply(unittest.TestCase):
    def test_final_answer_intact_and_first(self):
        _s, body = shaped(events())
        self.assertTrue(body.startswith(FINAL + "\n\n<details>"), body)
        answer, notes = _s.parts(final=True)
        self.assertEqual(answer, FINAL)

    def test_narration_and_reasoning_only_in_the_collapsed_steps(self):
        _s, body = shaped(events())
        answer_part, details = body.split("<details>", 1)
        for said in ("The user is asking which tables feed the dashboard. Let me look that up.",
                     "Now let me check snapshots.", "The user wants the tables. I'll summarize.",
                     "The user is asking about tables. I should call the tool."):
            self.assertNotIn(said, answer_part)
            self.assertIn(said, details)
        self.assertIn("<summary>How the assistant worked this out (3 tool calls)</summary>", details)
        self.assertIn("- used `lookup`\n- used `other`", details)
        self.assertIn("*Thinking:*\nThe user is asking about tables.", details)
        self.assertTrue(details.rstrip().endswith("</details>"))
        self.assertNotIn(" open", body.split(">", 1)[0] + details.split(">", 1)[0])

    def test_steps_in_order(self):
        _s, body = shaped(events())
        order = [body.index(x) for x in ("*Thinking:*", "Let me look that up.", "- used `lookup`",
                                         "Now let me check snapshots.", "- used `other`",
                                         "I'll summarize.")]
        self.assertEqual(order, sorted(order))

    def test_while_streaming(self):
        evs = events()
        # Up to the first tool call: the narration is streamed as the (live) answer.
        first_tool = next(i for i, d in enumerate(evs)
                          if d.get("event") == "content-block-start"
                          and (d.get("content") or {}).get("type") == "tool_call_chunk")
        s, body = shaped(evs[:first_tool], final=False)
        self.assertTrue(body.startswith("The user is asking which tables feed the dashboard."))
        self.assertFalse(s.working_on_tools())
        # Once it asks for a tool, the narration moves into the collapsed steps.
        s, body = shaped(evs[:first_tool + 1], final=False)
        self.assertTrue(s.working_on_tools())
        self.assertTrue(body.startswith("<details>"), body)
        # Mid-way through the last step, only its text so far is shown above the steps.
        last_start = max(i for i, d in enumerate(evs) if d.get("event") == "message-start")
        s, body = shaped(evs[:last_start + 3], final=False)
        self.assertFalse(s.working_on_tools())
        self.assertTrue(body.startswith("The user wants the tables."), body)   # not final yet

    def test_reasoning_only_status(self):
        evs = events()
        s = ai.ReplyShaper()
        for d in evs[:3]:                      # message-start, reasoning block start, delta
            s.feed(d)
        self.assertTrue(s.thinking())


class PlainReply(unittest.TestCase):
    """A reply with no tools, reasoning or planning is shown exactly as before (check 18 and
    ai_chat_probe expect the mock's "mock reply ..." verbatim)."""

    def events(self, text, reasoning=""):
        evs = [{"event": "message-start", "role": "ai", "id": "m1"}]
        if reasoning:
            evs += [{"event": "content-block-start", "index": 0, "content": {"type": "reasoning", "reasoning": ""}},
                    {"event": "content-block-delta", "index": 0, "delta": {"type": "reasoning-delta", "reasoning": reasoning}}]
        evs += [{"event": "content-block-start", "index": 1, "content": {"type": "text", "text": ""}}]
        evs += [{"event": "content-block-delta", "index": 1, "delta": {"type": "text-delta", "text": text[i:i + 7]}}
                for i in range(0, len(text), 7)]
        evs += [{"event": "message-finish", "metadata": {"finish_reason": "stop"}}]
        return evs

    def test_unchanged(self):
        text = "mock reply 1a2b3c4d: Why can't I create a table in samples?"
        _s, body = shaped(self.events(text))
        self.assertEqual(body, text)

    def test_markdown_answer_untouched(self):
        text = "## Tables\n\n- a\n- b\n\n```sql\nSELECT * FROM t\n```\n"
        _s, body = shaped(self.events(text))
        self.assertEqual(body, text)

    def test_reasoning_collapsed(self):
        _s, body = shaped(self.events("42.", reasoning="Let me think about the question."))
        self.assertTrue(body.startswith("42.\n\n<details>"))
        self.assertIn("*Thinking:*\nLet me think about the question.", body)
        self.assertIn("(notes)", body)

    def test_inline_think_tags(self):
        # Servers without a reasoning parser put <think>...</think> into the text.
        _s, body = shaped(self.events("<think>The user is asking X. Let me answer.</think>\n\nX is 42."))
        self.assertTrue(body.startswith("X is 42.\n\n<details>"), body)
        self.assertIn("The user is asking X. Let me answer.", body.split("<details>")[1])

    def test_unterminated_think_while_streaming(self):
        _s, body = shaped(self.events("<think>still thinking"), final=False)
        self.assertTrue(body.startswith("<details>"), body)
        self.assertNotIn("still thinking", body.split("<details>")[0])


class LeadingNarration(unittest.TestCase):
    def split(self, text):
        return ai.split_leading_narration(text)

    def test_strips_planning_paragraphs(self):
        lead, rest = self.split("The user is asking about X. Let me summarize.\n\nX is 42.")
        self.assertEqual((lead, rest), ("The user is asking about X. Let me summarize.", "X is 42."))
        lead, rest = self.split("Okay, so the user wants Y.\n\nI'll list them.\n\n- a\n- b")
        self.assertEqual(lead, "Okay, so the user wants Y.\n\nI'll list them.")
        self.assertEqual(rest, "- a\n- b")

    def test_keeps_answers(self):
        for text in (
            "The user is asking about X.",                                  # nothing left after
            "X is 42.\n\nLet me know if you need more.",                    # not leading
            "I'll need the table name: which one do you mean?",             # one paragraph
            "Let me explain:\n\n```sql\nSELECT 1\n```",                     # 'explain' is content
            "The users table has 3 rows.\n\nMore below.",                   # 'users', not 'user is'
            "Iceberg keeps snapshots.\n\nI'll show you how.",
        ):
            self.assertEqual(self.split(text), ("", text), text)

    def test_no_code_or_lists_in_narration(self):
        text = "Let me run:\n```sql\nSELECT 1\n```\n\nDone."
        self.assertEqual(self.split(text), ("", text))
        text = "I'll check:\n- a\n- b\n\nDone."
        self.assertEqual(self.split(text), ("", text))

    def test_long_paragraph_is_content(self):
        text = "I'll " + "explain this in detail " * 30 + "\n\nEnd."
        self.assertEqual(self.split(text), ("", text))


class Robustness(unittest.TestCase):
    def test_fences_cannot_break_out(self):
        evs = [{"event": "message-start", "role": "ai", "id": "m1"},
               {"event": "content-block-delta", "index": 0,
                "delta": {"type": "text-delta", "text": "Let me run ```sql\nSELECT 1 </details> <details open>"}},
               {"event": "content-block-start", "index": 1,
                "content": {"type": "tool_call_chunk", "id": "c1", "name": "trino_query", "args": ""}},
               {"event": "message-finish", "metadata": {"finish_reason": "tool_calls"}},
               {"event": "message-start", "role": "ai", "id": "m2"},
               {"event": "content-block-delta", "index": 0, "delta": {"type": "text-delta", "text": "Done."}}]
        _s, body = shaped(evs)
        details = body.split("<details>", 1)[1]
        self.assertEqual(details.count("</details>"), 1)
        self.assertEqual(details.count("```") % 2, 0)
        self.assertTrue(body.startswith("Done.\n\n<details>"))

    def test_no_answer_expands_the_steps(self):
        evs = [{"event": "message-start", "role": "ai", "id": "m1"},
               {"event": "content-block-delta", "index": 0, "delta": {"type": "text-delta", "text": "Let me look."}},
               {"event": "content-block-finish", "index": 1,
                "content": {"type": "tool_call", "id": "c1", "name": "catalog_list", "args": {}}},
               {"event": "message-finish", "metadata": {"finish_reason": "tool_calls"}}]
        _s, body = shaped(evs, final=True)
        self.assertTrue(body.startswith("<details open>"), body)
        self.assertIn("- used `catalog_list`", body)

    def test_tool_names_sanitized_and_deduplicated(self):
        s = ai.ReplyShaper()
        s.feed({"event": "message-start", "role": "ai", "id": "m1"})
        s.feed({"event": "content-block-start", "index": 0,
                "content": {"type": "tool_call_chunk", "id": "c1", "name": "evil`<b>name", "args": ""}})
        s.feed({"event": "content-block-delta", "index": 0, "delta": {"type": "block-delta", "fields": {
            "type": "tool_call_chunk", "id": "c1", "name": "evil`<b>name", "args": "{}"}}})
        s.feed({"event": "content-block-finish", "index": 0,
                "content": {"type": "tool_call", "id": "c1", "name": "evil`<b>name", "args": {}}})
        s.feed({"event": "message-finish", "metadata": {"finish_reason": "tool_calls"},
                "additional_kwargs": {"tool_calls": [{"id": "c1", "function": {"name": "evil`<b>name"}}]}})
        body = s.render(final=True)
        self.assertEqual(body.count("- used `"), 1)
        self.assertIn("- used `evilbname`", body)

    def test_text_only_in_block_finish(self):
        s = ai.ReplyShaper()
        s.feed({"event": "message-start", "role": "ai", "id": "m1"})
        s.feed({"event": "content-block-finish", "index": 0, "content": {"type": "text", "text": "Hello."}})
        self.assertEqual(s.render(final=True), "Hello.")

    def test_message_objects(self):
        """Older LangChain shapes: message objects (growing snapshots or deltas)."""
        def msg(mid, content, tool_calls=None, kind="ai"):
            return types.SimpleNamespace(id=mid, content=content, tool_calls=tool_calls or [], type=kind)
        s = ai.ReplyShaper()
        s.feed(msg("a", "The user is asking. Let me check."))
        s.feed(msg("a", "The user is asking. Let me check.", [{"id": "c1", "name": "catalog_list"}]))
        s.feed(msg("t", "tool output", kind="tool"))
        s.feed(msg("b", "Tables: "))
        s.feed(msg("b", "Tables: a, b."))
        s.feed(msg("b", " Loaded today."))
        body = s.render(final=True)
        self.assertTrue(body.startswith("Tables: a, b. Loaded today.\n\n<details>"), body)
        self.assertNotIn("tool output", body)


class FriendlyQuietHours(unittest.TestCase):
    MSG = ("The lab's local AI model is resting until 07:00 America/New_York (quiet hours "
           "22:00-07:00). Please try again after that; your lab admin can change this with "
           "'./lab ai quiet-hours'.")

    def test_wrapped_litellm_error(self):
        raw = ("Error: litellm.ServiceUnavailableError: OpenAIException - {\"error\":{\"message\":\""
               + self.MSG + "\",\"type\":\"ai_quiet_hours\",\"param\":null,\"code\":\"503\"}}")
        self.assertEqual(ai.friendly_error(raw), self.MSG)

    def test_escaped_apostrophe(self):
        raw = "Error: " + self.MSG.replace("lab's", "lab\\'s")
        self.assertEqual(ai.friendly_error(raw), self.MSG)

    def test_type_only(self):
        out = ai.friendly_error("Error: 503 ai_quiet_hours")
        self.assertTrue(out.startswith("The lab's local AI model is resting (quiet hours)."))

    def test_other_errors_unchanged(self):
        self.assertEqual(ai.friendly_error("Error: something else"), "Error: something else")


if __name__ == "__main__":
    unittest.main()
