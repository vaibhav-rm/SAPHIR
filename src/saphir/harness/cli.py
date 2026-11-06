"""Command line entry point: ``python -m saphir.harness <command>``.

Commands
--------
demo    two local agents over an in-process loopback (no model, no hardware)
serve   service side: advertise capabilities, execute inbound tasks
agent   initiator side: a local model plans and calls SAPHIR tools
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading

from ..agents import ReceptionistAgent, TaxiDispatch
from ..llm import OllamaBackend
from .agent import SaphirAgent
from .backends import (BackendError, OllamaChatBackend, OpenAICompatBackend,
                       PromptedToolsBackend, ScriptedBackend)
from .core import HarnessConfig, SaphirHarness
from .transport import (DEFAULT_TIMEOUT, FileTransport, LoopbackTransport,
                        TcpTransport, parse_hostport)

HANDLERS = {
    "hotel": lambda: ReceptionistAgent().handle_task,
    "taxi": lambda: TaxiDispatch().handle_task,
    "echo": lambda: (lambda task: {"ok": True, "echo": task}),
}


def _handler(name: str):
    try:
        return HANDLERS[name]()
    except KeyError:
        raise SystemExit(f"unknown handler {name!r}; choose from {sorted(HANDLERS)}")


def _file_transport(args):
    if not (args.inbox and args.peer_inbox):
        raise SystemExit("--file-dir needs --inbox and --peer-inbox")
    return FileTransport(args.file_dir, args.inbox, args.peer_inbox)


def _transport(args, side: str):
    if args.listen:
        if side != "serve":
            raise SystemExit("--listen is only valid for serve")
        host, port = parse_hostport(args.listen)
        print(f"[transport] waiting for a peer on {host}:{port}", flush=True)
        return TcpTransport.listen(host, port)
    if args.connect:
        if side != "agent":
            raise SystemExit("--connect is only valid for agent")
        host, port = parse_hostport(args.connect)
        print(f"[transport] connecting to {host}:{port}", flush=True)
        return TcpTransport.connect(host, port)
    if args.file_dir:
        return _file_transport(args)
    raise SystemExit("choose a transport: --listen / --connect / --file-dir")


def _make_harness(args, role: str, transport, offers=(), need=None) -> SaphirHarness:
    cfg = HarnessConfig(
        agent_id=args.agent,
        role=role,
        offers=tuple(offers),
        need=need,
        ontology=args.ontology,
        handler=_handler(args.handler) if role == "responder" and args.handler else None,
        audit_path=args.audit,
        transport=transport,
        did=args.did,
        timeout=args.timeout,
    )
    return SaphirHarness(cfg)


def _offers(value: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in value.split(",") if x.strip())


# ---- commands ----
def cmd_demo(args) -> int:
    ab, ba = LoopbackTransport.pair()
    responder = _make_harness(
        _ns(agent="hotel-bot", handler="hotel", offers="hotel.check,hotel.book",
            ontology="saphir-hotel-v1", audit=args.audit, did="did:key:zHotelBot",
            timeout=args.timeout),
        "responder", ab, offers=("hotel.check", "hotel.book"))
    caller = _make_harness(
        _ns(agent="caller-ai", handler=None, offers="", need="hotel.book",
            ontology="saphir-hotel-v1", audit=args.audit, did="did:key:zCaller",
            timeout=args.timeout),
        "initiator", ba, need="hotel.book")

    errors = []

    def serve():
        try:
            responder.pair()
            for _ in range(2):
                out = responder.serve_one(timeout=args.timeout)
                print(f"[serve] {json.dumps(out, default=str)}", flush=True)
        except Exception as e:  # report from the thread, fail the command
            errors.append(e)

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    backend = ScriptedBackend([
        {"tool": "saphir_pair", "args": {}},
        {"tool": "saphir_send_task",
         "args": {"intent": "hotel.check",
                  "slots": {"date": "2026-11-02", "room": "double", "nights": 2}}},
        {"tool": "saphir_send_task",
         "args": {"intent": "hotel.book",
                  "slots": {"date": "2026-11-02", "room": "double", "nights": 2,
                            "guests": 2, "name": "Vaibhav"}}},
        {"text": "Checked availability and booked the room over SAPHIR."},
    ])
    agent = SaphirAgent(backend, caller, outbound_intents=("hotel.check", "hotel.book"),
                        max_steps=8)
    run = agent.run("Book a double room for 2026-11-02, 2 nights, 2 guests.")
    t.join(timeout=args.timeout * 3)

    print("\n=== tool trace ===")
    for t_ in run.tool_trace:
        status = "ok" if t_["result"].get("ok") else "FAIL"
        print(f"[{status}] {t_['tool']} {json.dumps(t_['args'], default=str)}")
    print(f"\n[agent] {run.text}")
    print(f"[caller] {caller.status()['bytes_sent']}B sent, "
          f"{caller.status()['bytes_received']}B received")
    if caller.transcript():
        print("\n=== caller sidecar ===")
        print(caller.transcript())
    caller.close()
    responder.close()
    if errors:
        print(f"\n[demo] responder error: {errors[0]}", file=sys.stderr)
        return 1
    if not all(t_["result"].get("ok") for t_ in run.tool_trace):
        return 1
    print("\n[demo] OK")
    return 0


def cmd_serve(args) -> int:
    offers = _offers(args.offers)
    h = _make_harness(args, "responder", _transport(args, "serve"),
                      offers=offers)
    print(f"[serve] {args.agent} offering {offers or '(none advertised)'}", flush=True)
    h.pair()
    print(f"[serve] paired: {json.dumps(h.status(), default=str)}", flush=True)
    served = 0
    try:
        while args.count == 0 or served < args.count:
            try:
                out = h.serve_one(timeout=args.timeout)
            except Exception as e:
                print(f"[serve] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                break
            served += 1
            print(f"[serve] {json.dumps(out, default=str)}", flush=True)
            if out.get("closed") or out.get("rejected"):
                break
    except KeyboardInterrupt:
        pass
    h.close()
    return 0


def _backend(args):
    name = (args.backend or os.environ.get("SAPHIR_BACKEND") or "ollama").lower()
    model = args.model or os.environ.get("SAPHIR_MODEL") or "qwen2.5:1.5b"
    if name == "ollama":
        return OllamaChatBackend(model=model,
                                 host=args.host or os.environ.get("OLLAMA_HOST",
                                                                  "http://localhost:11434"))
    if name in ("openai", "openai-compatible", "llamacpp", "lmstudio"):
        base = (args.base_url or os.environ.get("SAPHIR_BASE_URL")
                or "http://localhost:8080/v1")
        return OpenAICompatBackend(model=model, base_url=base,
                                   api_key=args.api_key
                                   or os.environ.get("SAPHIR_API_KEY", ""))
    if name == "prompted":
        text = OllamaBackend(model=model,
                             host=args.host or os.environ.get("OLLAMA_HOST",
                                                              "http://localhost:11434"))
        return PromptedToolsBackend.from_llm(text)
    raise SystemExit(f"unknown backend {name!r}; choose ollama, openai, prompted")


def cmd_agent(args) -> int:
    try:
        transport = _transport(args, "agent")
    except OSError as e:
        print(f"[agent] cannot open transport: {e}", file=sys.stderr)
        return 2
    h = _make_harness(args, "initiator", transport, need=args.need)
    try:
        backend = _backend(args)
    except BackendError as e:
        print(f"[agent] cannot start backend: {e}", file=sys.stderr)
        return 2
    agent = SaphirAgent(backend, h, outbound_intents=(args.need,) if args.need else (),
                        max_steps=args.max_steps)
    try:
        run = agent.run(args.goal)
    except BackendError as e:
        print(f"[agent] model call failed: {e}", file=sys.stderr)
        return 2
    for t_ in run.tool_trace:
        status = "ok" if t_["result"].get("ok") else "FAIL"
        print(f"[{status}] {t_['tool']} {json.dumps(t_['args'], default=str)}",
              file=sys.stderr)
    print(run.text)
    return 0 if all(t_["result"].get("ok") for t_ in run.tool_trace) else 1


# ---- argument parsing ----
def _ns(**kw):
    base = dict(agent="saphir-agent", handler=None, offers="", need=None,
                ontology="saphir-hotel-v1", audit=None, did=None,
                timeout=DEFAULT_TIMEOUT)
    base.update(kw)
    return argparse.Namespace(**base)


def _add_transport(p):
    p.add_argument("--listen", help="HOST:PORT to accept one peer (serve)")
    p.add_argument("--connect", help="HOST:PORT of the service side (agent)")
    p.add_argument("--file-dir", help="shared directory transport")
    p.add_argument("--inbox", help="own inbox subdirectory (with --file-dir)")
    p.add_argument("--peer-inbox", help="peer inbox subdirectory (with --file-dir)")


def _add_common(p):
    p.add_argument("--agent", default="saphir-agent", help="local agent id")
    p.add_argument("--ontology", default="saphir-hotel-v1")
    p.add_argument("--audit", help="JSONL sidecar path")
    p.add_argument("--did", help="stable DID (enables resumption across runs)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m saphir.harness",
        description="Attach SAPHIR to a local AI agent.")
    sub = ap.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="in-process two-agent demo (no model)")
    demo.add_argument("--audit", help="JSONL sidecar path")
    demo.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    demo.set_defaults(func=cmd_demo)

    serve = sub.add_parser("serve", help="service side of a SAPHIR link")
    _add_common(serve)
    _add_transport(serve)
    serve.add_argument("--offers", default="hotel.check,hotel.book",
                       help="comma-separated intents this agent advertises")
    serve.add_argument("--handler", default="hotel", choices=sorted(HANDLERS))
    serve.add_argument("--count", type=int, default=0,
                       help="stop after N tasks (0 = until closed)")
    serve.set_defaults(func=cmd_serve)

    agent = sub.add_parser("agent", help="local model driving SAPHIR tools")
    _add_common(agent)
    _add_transport(agent)
    agent.add_argument("--goal", required=True)
    agent.add_argument("--need", default="hotel.book",
                       help="outbound intent for this run")
    agent.add_argument("--backend", default="ollama",
                       choices=["ollama", "openai", "prompted"])
    agent.add_argument("--model", help="model id (default qwen2.5:1.5b)")
    agent.add_argument("--host", help="Ollama host")
    agent.add_argument("--base-url", help="OpenAI-compatible base URL incl. /v1")
    agent.add_argument("--api-key", help="API key for the OpenAI-compatible server")
    agent.add_argument("--max-steps", type=int, default=8)
    agent.set_defaults(func=cmd_agent)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
