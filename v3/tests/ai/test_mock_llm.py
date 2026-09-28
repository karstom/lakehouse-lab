"""Unit tests for the mock LLM (tests/ai/mock_llm/server.py), over a real socket. Stdlib only:
    python3 -m unittest discover -s v3/tests/ai
"""
import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "mock_llm"))
import server as mock  # noqa: E402


class MockLLM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mock.load_scripts(os.path.join(HERE, "mock_llm", "scripts"))
        mock.Handler.log_message = lambda *a: None
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), mock.Handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, method, path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            text = r.read().decode()
            return text if raw else json.loads(text)

    def chat(self, messages, **kw):
        return self.call("POST", "/v1/chat/completions", dict({"model": "mock-model", "messages": messages}, **kw))

    def test_metadata(self):
        self.assertEqual(self.call("GET", "/health"), {"status": "ok"})
        self.assertEqual(self.call("GET", "/v1/models")["data"][0]["id"], "mock-model")

    def test_plain_reply_is_deterministic_with_usage(self):
        a = self.chat([{"role": "user", "content": "hello"}])
        b = self.chat([{"role": "user", "content": "hello"}])
        self.assertEqual(a, b)
        self.assertTrue(a["choices"][0]["message"]["content"].startswith("mock reply "))
        self.assertGreater(a["usage"]["total_tokens"], 0)

    def test_scripted_tool_loop(self):
        msgs = [{"role": "user", "content": "#mock:tool-loop-example which tables?"}]
        r1 = self.chat(msgs)["choices"][0]
        self.assertEqual(r1["finish_reason"], "tool_calls")
        call = r1["message"]["tool_calls"][0]
        self.assertEqual(call["function"]["name"], "catalog_list")
        self.assertEqual(json.loads(call["function"]["arguments"]), {"namespace": "analytics"})
        msgs += [r1["message"], {"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps({"tables": ["fct_orders", "dim_customers"]})}]
        r2 = self.chat(msgs)["choices"][0]
        calls = r2["message"]["tool_calls"]
        self.assertEqual([json.loads(c["function"]["arguments"])["table"] for c in calls], ["fct_orders", "dim_customers"])
        msgs.append(r2["message"])
        for c, t in zip(calls, ("2026-09-26T01:00:00Z", "2026-09-26T02:00:00Z")):
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps({"committed_at": t})})
        r3 = self.chat(msgs)["choices"][0]
        text = r3["message"]["content"]
        self.assertEqual(r3["finish_reason"], "stop")
        self.assertIn('["fct_orders", "dim_customers"]', text)
        self.assertIn("2026-09-26T02:00:00Z", text)

    def test_stream_with_usage(self):
        text = self.call("POST", "/v1/chat/completions", {"model": "m", "stream": True, "stream_options": {"include_usage": True},
                                                          "messages": [{"role": "user", "content": "hi"}]}, raw=True)
        events = [line[6:] for line in text.splitlines() if line.startswith("data: ")]
        self.assertEqual(events[-1], "[DONE]")
        chunks = [json.loads(e) for e in events[:-1]]
        content = "".join((c["choices"][0]["delta"].get("content") or "") for c in chunks if c["choices"])
        self.assertTrue(content.startswith("mock reply "))
        self.assertIn("usage", chunks[-1])

    def test_anthropic_messages(self):
        r = self.call("POST", "/v1/messages", {"model": "m", "max_tokens": 10, "system": "#mock:tool-loop-example",
                                               "messages": [{"role": "user", "content": "go"}]})
        self.assertEqual(r["stop_reason"], "tool_use")
        self.assertEqual(r["content"][0]["name"], "catalog_list")
        text = self.call("POST", "/v1/messages", {"model": "m", "max_tokens": 10, "stream": True,
                                                  "messages": [{"role": "user", "content": "hi"}]}, raw=True)
        self.assertIn("event: message_stop", text)

    def test_embeddings(self):
        r = self.call("POST", "/v1/embeddings", {"model": "m", "input": ["a", "b"]})
        self.assertEqual(len(r["data"]), 2)
        self.assertEqual(len(r["data"][0]["embedding"]), 8)

    def test_request_log_and_runtime_scripts(self):
        self.call("DELETE", "/_mock/requests")
        self.call("PUT", "/_mock/scripts/runtime-x", {"steps": [{"content": "from runtime"}]})
        r = self.chat([{"role": "system", "content": "tutor #mock:runtime-x"}, {"role": "user", "content": "q"}])
        self.assertEqual(r["choices"][0]["message"]["content"], "from runtime")
        log = self.call("GET", "/_mock/requests")
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["body"]["messages"][0]["content"], "tutor #mock:runtime-x")

    def test_narration_and_reasoning(self):
        """Phase 6: a tool step may carry the model's narration ("content") and any step its
        reasoning ("reasoning", sent as reasoning_content like llama-server)."""
        self.call("PUT", "/_mock/scripts/narr", {"steps": [
            {"reasoning": "The user is asking. I should look.", "content": "Let me look that up.",
             "tool_calls": [{"name": "catalog_list", "arguments": {}}]},
            {"content": "Answer."}]})
        first = self.chat([{"role": "user", "content": "q #mock:narr"}])
        msg = first["choices"][0]["message"]
        self.assertEqual(msg["content"], "Let me look that up.")
        self.assertEqual(msg["reasoning_content"], "The user is asking. I should look.")
        self.assertEqual(msg["tool_calls"][0]["function"]["name"], "catalog_list")
        self.assertEqual(first["choices"][0]["finish_reason"], "tool_calls")
        raw = self.call("POST", "/v1/chat/completions", {"model": "mock-model", "stream": True,
                        "messages": [{"role": "user", "content": "q #mock:narr"}]}, raw=True)
        deltas = [json.loads(line[6:])["choices"][0]["delta"] for line in raw.splitlines()
                  if line.startswith("data: {") and json.loads(line[6:])["choices"]]
        kinds = [next(k for k in ("reasoning_content", "content", "tool_calls") if d.get(k))
                 for d in deltas if any(d.get(k) for k in ("reasoning_content", "content", "tool_calls"))]
        self.assertEqual(kinds[0], "reasoning_content")
        self.assertEqual(kinds[-1], "tool_calls")
        self.assertEqual("".join(d.get("content") or "" for d in deltas), "Let me look that up.")
        second = self.chat([{"role": "user", "content": "q #mock:narr"},
                            dict(msg, role="assistant"),
                            {"role": "tool", "tool_call_id": msg["tool_calls"][0]["id"], "content": "[]"}])
        self.assertEqual(second["choices"][0]["message"]["content"], "Answer.")
        self.assertNotIn("reasoning_content", second["choices"][0]["message"])
        # Anthropic shape: the narration is a text block before the tool_use block.
        a = self.call("POST", "/v1/messages", {"model": "mock-model", "max_tokens": 10,
                      "messages": [{"role": "user", "content": "q #mock:narr"}]})
        self.assertEqual([b["type"] for b in a["content"]], ["text", "tool_use"])
        self.assertEqual(a["content"][0]["text"], "Let me look that up.")

    def test_select(self):
        self.assertEqual(mock.select("a[*].b", {"a": [{"b": 1}, {"b": 2}]}), [1, 2])
        self.assertEqual(mock.select("a[1]", {"a": [5, 6]}), [6])
        self.assertEqual(mock.select("missing", {"a": 1}), [])


if __name__ == "__main__":
    unittest.main()
