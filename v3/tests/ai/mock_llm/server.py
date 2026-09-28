#!/usr/bin/env python3
"""Deterministic mock LLM for the lab's tests (CONTRACT Phase 5: every build and test uses a
mock model; no test ever sends inference to a real model). Python stdlib only, so it runs on
the bootstrap image (compose service `ai-mock`, profile `ai-mock`) or anywhere else:

    python3 server.py [--host 0.0.0.0] [--port 8000] [--scripts DIR]

OpenAI-compatible (what the gateway's `mock` and, in tests, `local` providers call):
  GET  /health                 {"status": "ok"}   (llama.cpp llama-server's shape)
  GET  /v1/models              one model, "mock-model"
  POST /v1/chat/completions    stream or not; text or scripted tool calls; usage always set
  POST /v1/embeddings          deterministic unit vectors (dimension 8)
Anthropic-compatible (in case a client is pointed straight at the mock):
  POST /v1/messages            stream or not; same scripts, Anthropic content blocks
Test controls (never used by the lab itself):
  GET  /_mock/requests         the last 200 requests received (JSON bodies), oldest first
  DELETE /_mock/requests       forget them
  PUT  /_mock/scripts/<name>   add or replace a script at runtime (body = the script JSON)
  GET  /_mock/scripts          script names

Behaviour, all deterministic (same request -> same response):
* A message containing the marker `#mock:<name>` selects the script `<name>` (from --scripts,
  default ./scripts next to this file, or added with PUT). Without a marker the reply is plain
  text: "mock reply <8 hex of sha256(last user text)>: <first 80 chars of it>".
* A script is {"steps": [step, ...]}. The step used is the number of assistant turns already
  in the conversation (0 for the first call), so a tool loop walks through the steps; past the
  end, the last step repeats. A step is one of
    {"content": "text"}
    {"tool_calls": [{"name": "tool", "arguments": {...}}, ...]}
    {"tool_calls_foreach": {"source": "tool:NAME", "path": "a.b[*].c",
                            "name": "tool", "arguments": {"x": "{{item}}"}}}
  A tool step may also carry "content": the model's narration sent WITH the tool calls
  (OpenAI: `content` next to `tool_calls`; Anthropic: a text block before the tool_use
  blocks), as real models do ("The user is asking... Let me look that up."). Any step may
  carry "reasoning": sent as `reasoning_content` (OpenAI shape, as llama.cpp llama-server
  and other local servers send a model's thinking); the Anthropic route ignores it.
  Strings in content/arguments may use placeholders:
    {{tool:NAME}}      the content of the LAST tool result for a call to NAME
    {{tool:NAME|path}} a value selected from that result (parsed as JSON) by `path`
    {{last_tool}}      the content of the last tool result
    {{tool_results}}   a JSON list of every tool result so far ({"name", "content"})
    {{item}}           (foreach only) the current element
  `path` is dotted keys with `[*]` for "every element" and `[N]` for an index.
* Usage: tokens = ceil(characters / 4) of the prompt (all message text) and of the reply, so
  a budget test can predict the cost.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "mock-model"
MARKER = re.compile(r"#mock:([A-Za-z0-9_.-]+)")
PLACEHOLDER = re.compile(r"\{\{\s*(tool_results|last_tool|item|tool:[A-Za-z0-9_.-]+(?:\|[^}]*)?)\s*\}\}")
_lock = threading.Lock()
REQUESTS = []
SCRIPTS = {}


# ------------------------------------------------------------------ message helpers
def text_of(content):
    """OpenAI or Anthropic message content -> plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else [content]:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") in ("text", "input_text", None) and "text" in block:
                parts.append(str(block["text"]))
            elif block.get("type") == "tool_result":
                parts.append(text_of(block.get("content")))
    return "\n".join(parts)


def normalize(body, api):
    """-> (messages as [{"role","text","tool_calls","tool_name"}], system text)."""
    msgs, system = [], ""
    if api == "anthropic":
        system = text_of(body.get("system"))
        id_to_name = {}
        for m in body.get("messages") or []:
            content = m.get("content")
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content or ""}]
            calls, results, texts = [], [], []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    id_to_name[b.get("id")] = b.get("name")
                    calls.append({"name": b.get("name")})
                elif b.get("type") == "tool_result":
                    results.append({"name": id_to_name.get(b.get("tool_use_id")), "text": text_of(b.get("content"))})
                elif b.get("type") == "text":
                    texts.append(str(b.get("text", "")))
            if m.get("role") == "assistant":
                msgs.append({"role": "assistant", "text": "\n".join(texts), "tool_calls": calls})
            else:
                for r in results:
                    msgs.append({"role": "tool", "text": r["text"], "tool_name": r["name"]})
                if texts or not results:
                    msgs.append({"role": m.get("role", "user"), "text": "\n".join(texts)})
    else:
        id_to_name = {}
        for m in body.get("messages") or []:
            role = m.get("role")
            if role == "system" or role == "developer":
                system += ("\n" if system else "") + text_of(m.get("content"))
                continue
            calls = []
            for c in m.get("tool_calls") or []:
                fn = c.get("function") or {}
                id_to_name[c.get("id")] = fn.get("name")
                calls.append({"name": fn.get("name")})
            entry = {"role": role, "text": text_of(m.get("content")), "tool_calls": calls}
            if role == "tool":
                entry["tool_name"] = m.get("name") or id_to_name.get(m.get("tool_call_id"))
            msgs.append(entry)
    return msgs, system


def count_tokens(text):
    return max(1, math.ceil(len(text) / 4)) if text else 0


# ------------------------------------------------------------------ scripts
def select(path, value):
    """Tiny path language: a.b[*].c / a[0] -> list of matches."""
    cur = [value]
    for part in re.findall(r"[^.\[\]]+|\[\*\]|\[\d+\]", path or ""):
        nxt = []
        for v in cur:
            if part == "[*]":
                if isinstance(v, list):
                    nxt.extend(v)
            elif part.startswith("["):
                i = int(part[1:-1])
                if isinstance(v, list) and -len(v) <= i < len(v):
                    nxt.append(v[i])
            elif isinstance(v, dict) and part in v:
                nxt.append(v[part])
        cur = nxt
    return cur


def _as_json(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def tool_results(msgs):
    return [{"name": m.get("tool_name"), "content": m["text"]} for m in msgs if m["role"] == "tool"]


def fill(value, msgs, item=None):
    results = tool_results(msgs)

    def one(match):
        key = match.group(1)
        if key == "tool_results":
            return json.dumps(results, sort_keys=True)
        if key == "last_tool":
            return results[-1]["content"] if results else ""
        if key == "item":
            return item if isinstance(item, str) else json.dumps(item, sort_keys=True)
        name, _, path = key[len("tool:"):].partition("|")
        hit = [r for r in results if r["name"] == name]
        if not hit:
            return ""
        if not path:
            return hit[-1]["content"]
        found = select(path, _as_json(hit[-1]["content"]))
        if len(found) == 1:
            return found[0] if isinstance(found[0], str) else json.dumps(found[0], sort_keys=True)
        return json.dumps(found, sort_keys=True)

    if isinstance(value, str):
        # A value that is ONLY {{item}} keeps the item's type (a number stays a number).
        if item is not None and value.strip() == "{{item}}":
            return item
        return PLACEHOLDER.sub(one, value)
    if isinstance(value, list):
        return [fill(v, msgs, item) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, msgs, item) for k, v in value.items()}
    return value


def load_scripts(directory):
    if not directory or not os.path.isdir(directory):
        return
    for fn in sorted(os.listdir(directory)):
        if fn.endswith(".json"):
            with open(os.path.join(directory, fn)) as f:
                SCRIPTS[fn[:-5]] = json.load(f)


def plan(msgs, system):
    """-> ("text", str) or ("tools", [{"name", "arguments"}])."""
    kind, out, _extra = plan_full(msgs, system)
    return kind, out


def plan_full(msgs, system):
    """plan() plus the step's extras: {"content": narration sent with tool calls,
    "reasoning": thinking text}; both "" when the step has none."""
    extra = {"content": "", "reasoning": ""}
    kind, out, step = _plan_step(msgs, system)
    if step is not None:
        if kind == "tools" and isinstance(step.get("content"), str):
            extra["content"] = fill(step["content"], msgs)
        if isinstance(step.get("reasoning"), str):
            extra["reasoning"] = fill(step["reasoning"], msgs)
    return kind, out, extra


def _plan_step(msgs, system):
    """-> (kind, out, the scripted step or None)."""
    everything = "\n".join([system] + [m["text"] for m in msgs])
    marker = MARKER.search(everything)
    if marker:
        script = SCRIPTS.get(marker.group(1))
        if script is None:
            return "text", f"mock: unknown script {marker.group(1)!r}", None
        steps = script.get("steps") or [{"content": ""}]
        turn = sum(1 for m in msgs if m["role"] == "assistant")
        step = steps[min(turn, len(steps) - 1)]
        if "tool_calls_foreach" in step:
            spec = step["tool_calls_foreach"]
            src = spec.get("source", "last_tool")
            if src.startswith("tool:"):
                hit = [r for r in tool_results(msgs) if r["name"] == src[5:]]
                data = _as_json(hit[-1]["content"]) if hit else None
            else:
                res = tool_results(msgs)
                data = _as_json(res[-1]["content"]) if res else None
            items = select(spec.get("path", ""), data) if data is not None else []
            calls = [{"name": spec["name"], "arguments": fill(spec.get("arguments", {}), msgs, it)} for it in items]
            if calls:
                return "tools", calls, step
            return "text", fill(step.get("empty_content", "mock: nothing to call"), msgs), step
        if "tool_calls" in step:
            return "tools", [{"name": c["name"], "arguments": fill(c.get("arguments", {}), msgs)}
                             for c in step["tool_calls"]], step
        return "text", fill(step.get("content", ""), msgs), step
    last_user = next((m["text"] for m in reversed(msgs) if m["role"] == "user"), "")
    digest = hashlib.sha256(last_user.encode()).hexdigest()[:8]
    return "text", f"mock reply {digest}: {last_user[:80]}", None


def call_id(i, name, turn):
    return "call_" + hashlib.sha256(f"{turn}:{i}:{name}".encode()).hexdigest()[:16]


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "lab-mock-llm/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # one short line per request on stderr
        sys.stderr.write("[mock-llm] %s %s\n" % (self.command, self.path))

    def _json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw) if raw else {}
        except ValueError:
            return None

    def _sse_start(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def _sse(self, obj, event=None):
        line = (f"event: {event}\n" if event else "") + "data: " + (obj if isinstance(obj, str) else json.dumps(obj)) + "\n\n"
        self.wfile.write(line.encode())
        self.wfile.flush()

    def do_GET(self):
        if self.path == "/health":
            return self._json(200, {"status": "ok"})
        if self.path in ("/v1/models", "/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": MODEL, "object": "model", "created": 0, "owned_by": "lab-mock"}]})
        if self.path == "/_mock/requests":
            with _lock:
                return self._json(200, list(REQUESTS))
        if self.path == "/_mock/scripts":
            return self._json(200, sorted(SCRIPTS))
        return self._json(404, {"error": {"message": "not found", "type": "not_found"}})

    def do_DELETE(self):
        if self.path == "/_mock/requests":
            with _lock:
                REQUESTS.clear()
            return self._json(200, {"cleared": True})
        return self._json(404, {"error": {"message": "not found"}})

    def do_PUT(self):
        m = re.fullmatch(r"/_mock/scripts/([A-Za-z0-9_.-]+)", self.path)
        body = self._body()
        if not m or not isinstance(body, dict):
            return self._json(400, {"error": {"message": "PUT /_mock/scripts/<name> with a JSON script"}})
        SCRIPTS[m.group(1)] = body
        return self._json(200, {"stored": m.group(1)})

    def do_POST(self):
        body = self._body()
        if body is None:
            return self._json(400, {"error": {"message": "invalid JSON", "type": "invalid_request_error"}})
        path = self.path.split("?", 1)[0]
        with _lock:
            REQUESTS.append({"path": path, "time": time.time(), "body": body})
            del REQUESTS[:-200]
        if path in ("/v1/chat/completions", "/chat/completions"):
            return self.chat(body)
        if path in ("/v1/messages", "/messages"):
            return self.messages(body)
        if path in ("/v1/embeddings", "/embeddings"):
            return self.embeddings(body)
        return self._json(404, {"error": {"message": "not found", "type": "not_found"}})

    # ---------------------------------------------------------------- OpenAI chat
    def chat(self, body):
        msgs, system = normalize(body, "openai")
        kind, out, extra = plan_full(msgs, system)
        turn = sum(1 for m in msgs if m["role"] == "assistant")
        prompt_t = count_tokens(system + "".join(m["text"] for m in msgs))
        rid = "chatcmpl-" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]
        narration, reasoning = extra["content"], extra["reasoning"]
        if kind == "tools":
            calls = [{"id": call_id(i, c["name"], turn), "type": "function",
                      "function": {"name": c["name"], "arguments": json.dumps(c["arguments"], sort_keys=True)}}
                     for i, c in enumerate(out)]
            message = {"role": "assistant", "content": narration or None, "tool_calls": calls}
            finish = "tool_calls"
            comp_t = count_tokens(narration + "".join(c["function"]["arguments"] for c in calls))
        else:
            message = {"role": "assistant", "content": out}
            finish = "stop"
            comp_t = count_tokens(out)
        if reasoning:
            message["reasoning_content"] = reasoning
            comp_t += count_tokens(reasoning)
        usage = {"prompt_tokens": prompt_t, "completion_tokens": comp_t, "total_tokens": prompt_t + comp_t}
        base = {"id": rid, "created": 0, "model": body.get("model") or MODEL}
        if not body.get("stream"):
            return self._json(200, dict(base, object="chat.completion", usage=usage, choices=[
                {"index": 0, "message": message, "finish_reason": finish}]))
        self._sse_start()
        chunk = dict(base, object="chat.completion.chunk")

        def pieces(text):
            return [text[i:i + 40] for i in range(0, len(text), 40)]

        self._sse(dict(chunk, choices=[{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]))
        for piece in pieces(reasoning):
            self._sse(dict(chunk, choices=[{"index": 0, "delta": {"reasoning_content": piece}, "finish_reason": None}]))
        if kind == "tools":
            for piece in pieces(narration):
                self._sse(dict(chunk, choices=[{"index": 0, "delta": {"content": piece}, "finish_reason": None}]))
            for i, c in enumerate(message["tool_calls"]):
                self._sse(dict(chunk, choices=[{"index": 0, "finish_reason": None, "delta": {"tool_calls": [
                    {"index": i, "id": c["id"], "type": "function",
                     "function": {"name": c["function"]["name"], "arguments": c["function"]["arguments"]}}]}}]))
        else:
            for piece in pieces(out) or [""]:
                self._sse(dict(chunk, choices=[{"index": 0, "delta": {"content": piece}, "finish_reason": None}]))
        self._sse(dict(chunk, choices=[{"index": 0, "delta": {}, "finish_reason": finish}]))
        if (body.get("stream_options") or {}).get("include_usage"):
            self._sse(dict(chunk, choices=[], usage=usage))
        self._sse("[DONE]")

    # ---------------------------------------------------------------- Anthropic messages
    def messages(self, body):
        msgs, system = normalize(body, "anthropic")
        kind, out, extra = plan_full(msgs, system)
        turn = sum(1 for m in msgs if m["role"] == "assistant")
        in_t = count_tokens(system + "".join(m["text"] for m in msgs))
        if kind == "tools":
            content = [{"type": "tool_use", "id": "toolu_" + call_id(i, c["name"], turn)[5:], "name": c["name"],
                        "input": c["arguments"]} for i, c in enumerate(out)]
            stop = "tool_use"
            out_t = count_tokens(extra["content"] + "".join(json.dumps(c["input"]) for c in content))
            if extra["content"]:
                content.insert(0, {"type": "text", "text": extra["content"]})
        else:
            content = [{"type": "text", "text": out}]
            stop = "end_turn"
            out_t = count_tokens(out)
        mid = "msg_" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]
        msg = {"id": mid, "type": "message", "role": "assistant", "model": body.get("model") or MODEL,
               "content": content, "stop_reason": stop, "stop_sequence": None,
               "usage": {"input_tokens": in_t, "output_tokens": out_t}}
        if not body.get("stream"):
            return self._json(200, msg)
        self._sse_start()
        self._sse({"type": "message_start", "message": dict(msg, content=[], stop_reason=None,
                                                            usage={"input_tokens": in_t, "output_tokens": 0})},
                  "message_start")
        for i, block in enumerate(content):
            if block["type"] == "text":
                self._sse({"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}},
                          "content_block_start")
                self._sse({"type": "content_block_delta", "index": i,
                           "delta": {"type": "text_delta", "text": block["text"]}}, "content_block_delta")
            else:
                self._sse({"type": "content_block_start", "index": i, "content_block": dict(block, input={})},
                          "content_block_start")
                self._sse({"type": "content_block_delta", "index": i,
                           "delta": {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}},
                          "content_block_delta")
            self._sse({"type": "content_block_stop", "index": i}, "content_block_stop")
        self._sse({"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                   "usage": {"output_tokens": out_t}}, "message_delta")
        self._sse({"type": "message_stop"}, "message_stop")

    # ---------------------------------------------------------------- embeddings
    def embeddings(self, body):
        inputs = body.get("input")
        inputs = inputs if isinstance(inputs, list) else [inputs]
        data = []
        for i, text in enumerate(inputs):
            h = hashlib.sha256(str(text).encode()).digest()
            vec = [(b - 127.5) / 127.5 for b in h[:8]]
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            data.append({"object": "embedding", "index": i, "embedding": [v / norm for v in vec]})
        t = sum(count_tokens(str(x)) for x in inputs)
        return self._json(200, {"object": "list", "model": body.get("model") or MODEL, "data": data,
                                "usage": {"prompt_tokens": t, "total_tokens": t}})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--scripts", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
    args = ap.parse_args(argv)
    load_scripts(args.scripts)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    print(f"[mock-llm] listening on {args.host}:{args.port}; scripts: {', '.join(sorted(SCRIPTS)) or '-'}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
