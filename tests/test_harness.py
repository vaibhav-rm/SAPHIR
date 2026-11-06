import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "src")
from saphir.harness import (FileTransport, HarnessConfig, LoopbackTransport,
                            OllamaChatBackend, OpenAICompatBackend,
                            PromptedToolsBackend, ScriptedBackend, SaphirAgent,
                            SaphirHarness, TcpTransport, ToolBridge)
from saphir.agents import ReceptionistAgent


def make_pair(handler=None, offers=("hotel.check", "hotel.book"), need="hotel.book",
              timeout=2.0, dids=("did:key:zCaller", "did:key:zServer"),
              audit_path=None):
    ab, ba = LoopbackTransport.pair()
    caller = SaphirHarness(HarnessConfig(
        "caller", role="initiator", need=need, transport=ab, timeout=timeout,
        did=dids[0], audit_path=audit_path))
    server = SaphirHarness(HarnessConfig(
        "server", role="responder", offers=offers, transport=ba, timeout=timeout,
        did=dids[1], handler=handler or ReceptionistAgent().handle_task,
        audit_path=audit_path))
    return caller, server


def in_thread(fn, *args):
    box = {}

    def run():
        try:
            box["value"] = fn(*args)
        except Exception as e:  # surfaced by the assertion below
            box["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, box


def test_loopback_roundtrip_and_audit(tmp_path):
    audit = tmp_path / "audit.jsonl"
    caller, server = make_pair(audit_path=str(audit))

    t, box = in_thread(lambda: (server.pair(), server.serve_one()))
    caller.pair()
    out = caller.send_task("hotel.book", {"date": "2026-11-02", "room": "double",
                                          "nights": 1, "name": "V"})
    t.join(timeout=5)
    assert "error" not in box, box
    assert out["ok"] is True
    assert out["result"]["confirmation"].startswith("HB-")
    assert caller.status()["state"] == "ESTABLISHED"
    assert caller.status()["peer"]["did"] == "did:key:zServer"
    assert caller.status()["bytes_sent"] > 0
    lines = audit.read_text().strip().splitlines()
    assert any(json.loads(x)["type"] == "TASK" for x in lines)
    assert caller.transcript().count("TASK") >= 1


def test_send_task_auto_pairs():
    caller, server = make_pair()
    t, box = in_thread(lambda: (server.pair(), server.serve_one()))
    out = caller.send_task("hotel.check", {"date": "2026-11-02", "room": "double",
                                           "nights": 2})
    t.join(timeout=5)
    assert "error" not in box, box
    assert out["ok"] is True and out["result"]["price"] == 120
    assert caller.is_paired


def test_refuses_intent_outside_advertised_capabilities():
    calls = []
    caller, server = make_pair(
        handler=lambda task: calls.append(task) or {"ok": True},
        offers=("hotel.check",))
    t, box = in_thread(lambda: (server.pair(), server.serve_one()))
    out = caller.send_task("taxi.book", {"from": "A", "to": "B"})
    t.join(timeout=5)
    assert "error" not in box, box
    assert out["ok"] is False
    assert out["error"]["code"] == "no-capability"
    assert calls == []


def test_handler_exception_becomes_error_result():
    def boom(task):
        raise RuntimeError("inventory offline")

    caller, server = make_pair(handler=boom)
    t, box = in_thread(lambda: (server.pair(), server.serve_one()))
    out = caller.send_task("hotel.check", {"date": "2026-11-02", "room": "double"})
    t.join(timeout=5)
    assert "error" not in box, box
    assert out["ok"] is True and out["result"]["ok"] is False
    assert "inventory offline" in out["result"]["error"]


def test_harness_emits_bye():
    caller, server = make_pair()
    t, box = in_thread(lambda: (server.pair(), server.serve_one()))
    caller.pair()
    caller.close()
    t.join(timeout=5)
    assert "error" not in box, box
    assert box["value"][1]["closed"] is True


def test_tool_bridge_cap_and_unknown_tool():
    caller, _ = make_pair()
    bridge = ToolBridge(caller, outbound_intents=("hotel.book",))
    big = bridge.call("saphir_send_task",
                      {"intent": "hotel.book", "slots": {"name": "x" * 200}})
    assert big["ok"] is False and "200B" in big["error"]
    unknown = bridge.call("saphir_launch_missiles", {})
    assert unknown["ok"] is False
    assert "saphir_pair" in unknown["available"]


def test_tool_bridge_status_schema():
    caller, _ = make_pair()
    bridge = ToolBridge(caller)
    names = [s["function"]["name"] for s in bridge.specs()]
    assert names == ["saphir_status", "saphir_pair", "saphir_send_task",
                     "saphir_serve", "saphir_audit", "saphir_close"]
    status = bridge.call("saphir_status", {})
    assert status["ok"] is True and status["state"] == "IDLE"


def test_agent_loop_scripted_end_to_end():
    caller, server = make_pair()
    t, box = in_thread(lambda: (server.pair(), server.serve_one(),
                                server.serve_one()))
    backend = ScriptedBackend([
        {"tool": "saphir_pair", "args": {}},
        {"tool": "saphir_send_task",
         "args": {"intent": "hotel.check",
                  "slots": {"date": "2026-11-02", "room": "double", "nights": 1}}},
        {"tool": "saphir_send_task",
         "args": {"intent": "hotel.book",
                  "slots": {"date": "2026-11-02", "room": "double", "nights": 1,
                            "name": "V"}}},
        {"text": "done"},
    ])
    agent = SaphirAgent(backend, caller, outbound_intents=("hotel.check", "hotel.book"))
    run = agent.run("book a room")
    t.join(timeout=5)
    assert "error" not in box, box
    assert run.text == "done"
    assert [x["tool"] for x in run.tool_trace] == [
        "saphir_pair", "saphir_send_task", "saphir_send_task"]
    assert all(x["result"]["ok"] for x in run.tool_trace)
    tool_messages = [m for m in run.messages if m["role"] == "tool"]
    assert len(tool_messages) == 3
    assert json.loads(tool_messages[1]["content"])["result"]["price"] == 120


def test_agent_respects_step_limit():
    caller, _ = make_pair()
    backend = ScriptedBackend([{"tool": "saphir_status", "args": {}}] * 3)
    agent = SaphirAgent(backend, caller, max_steps=3)
    run = agent.run("loop forever")
    assert "limit reached" in run.text
    assert len(run.tool_trace) == 3


def test_prompted_backend_parses_tool_then_final():
    caller, _ = make_pair()
    replies = ['{"tool": "saphir_status", "args": {}}',
               '{"final": "link is idle"}']
    backend = PromptedToolsBackend(lambda system, user: replies.pop(0))
    run = SaphirAgent(backend, caller).run("what is the link state?")
    assert run.text == "link is idle"
    assert run.tool_trace[0]["tool"] == "saphir_status"
    assert run.tool_trace[0]["result"]["state"] == "IDLE"


def test_prompted_backend_injects_tool_schema():
    seen = {}

    def complete(system, user):
        seen["system"] = system
        return '{"final": "ok"}'

    backend = PromptedToolsBackend(complete)
    backend.chat([{"role": "system", "content": "be brief"},
                  {"role": "user", "content": "hi"}],
                 tools=[{"type": "function", "function": {
                     "name": "saphir_status", "description": "link state"}}])
    assert "be brief" in seen["system"]
    assert "saphir_status" in seen["system"]
    assert '{"tool"' in seen["system"]


def test_openai_backend_parses_tool_calls():
    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["Content-Length"])
            captured["body"] = json.loads(self.rfile.read(n))
            body = json.dumps({"choices": [{"message": {
                "content": None,
                "tool_calls": [{"id": "call_1", "type": "function",
                                "function": {"name": "saphir_pair",
                                             "arguments": "{}"}}]}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.handle_request, daemon=True)
    t.start()
    backend = OpenAICompatBackend("test-model",
                                  base_url=f"http://127.0.0.1:{srv.server_port}/v1")
    turn = backend.chat([{"role": "user", "content": "pair"}],
                        tools=[{"type": "function", "function": {"name": "saphir_pair"}}])
    t.join(timeout=5)
    srv.server_close()
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["tools"][0]["function"]["name"] == "saphir_pair"
    assert turn.tool_calls[0].name == "saphir_pair"
    assert turn.tool_calls[0].arguments == {}


def test_openai_backend_strips_ollama_only_fields():
    msgs = OpenAICompatBackend._messages([
        {"role": "tool", "tool_call_id": "c1", "name": "saphir_status",
         "content": "{}"},
        {"role": "user", "content": "hi"},
    ])
    assert msgs[0] == {"role": "tool", "content": "{}", "tool_call_id": "c1"}


def test_ollama_message_conversion():
    msgs = OllamaChatBackend._messages([
        {"role": "assistant", "content": "",
         "tool_calls": [{"id": "c1", "type": "function",
                         "function": {"name": "saphir_pair",
                                      "arguments": "{}"}}]},
        {"role": "tool", "name": "saphir_pair", "content": "{\"ok\": true}"},
    ])
    assert msgs[0]["tool_calls"][0]["function"]["arguments"] == {}
    assert msgs[1]["tool_name"] == "saphir_pair"


def test_tcp_transport_framing():
    a, b = socket.socketpair()
    ta, tb = TcpTransport(a), TcpTransport(b)
    frame = b"\x00\x00\x00\x05hello"
    ta.send(frame)
    assert tb.recv(timeout=2) == frame
    tb.send(frame + b"x")
    assert ta.recv(timeout=2) == frame
    ta.close()
    tb.close()


def test_tcp_listen_connect():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    t, box = in_thread(TcpTransport.listen, "127.0.0.1", port)
    client = None
    for _ in range(100):
        try:
            client = TcpTransport.connect("127.0.0.1", port, timeout=2)
            break
        except OSError:
            time.sleep(0.02)
    t.join(timeout=5)
    assert client is not None and "error" not in box, box
    server = box["value"]
    ping = b"\x00\x00\x00\x04ping"
    pong = b"\x00\x00\x00\x04pong"
    client.send(ping)
    assert server.recv(timeout=2) == ping
    server.send(pong)
    assert client.recv(timeout=2) == pong
    client.close()
    server.close()


def test_file_transport(tmp_path):
    a = FileTransport(tmp_path, "a", "b")
    b = FileTransport(tmp_path, "b", "a")
    a.send(b"one")
    assert b.recv(timeout=2) == b"one"
    b.send(b"two")
    assert a.recv(timeout=2) == b"two"
    assert a.recv(timeout=0.05) is None


def test_resumption_is_abbreviated(tmp_path):
    caller, server = make_pair(dids=("did:key:zStableCaller", "did:key:zStableServer"))
    t, box = in_thread(lambda: (server.pair(), server.serve_one()))
    first = caller.pair()
    caller.send_task("hotel.check", {"date": "2026-11-02", "room": "double"})
    t.join(timeout=5)
    assert "error" not in box, box

    # Fresh sessions, same stable DIDs + ticket stores: HELLO/WELCOME only.
    caller._new_session()
    server._new_session()
    t2, box2 = in_thread(lambda: (server.pair(), server.serve_one()))
    caller.pair()
    out = caller.send_task("hotel.check", {"date": "2026-11-02", "room": "double"})
    t2.join(timeout=5)
    assert "error" not in box2, box2
    assert out["ok"] is True
    assert caller.state == "ESTABLISHED"
