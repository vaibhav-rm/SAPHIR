"""SAPHIR harness: attach the protocol to any local AI runtime.

Three integration levels:

1. ``SaphirHarness`` + ``Transport``: pair and exchange tasks in your own code.
2. ``ToolBridge``: hand ``specs()`` to a model that supports function calling.
3. ``SaphirAgent``: a ready-made tool-calling loop over Ollama, an
   OpenAI-compatible server, or any text model via ``PromptedToolsBackend``.

See ``docs/HARNESS.md`` and ``python -m saphir.harness --help``.
"""
from .agent import AgentRun, SaphirAgent
from .backends import (BackendError, ChatBackend, ModelTurn, OllamaChatBackend,
                       OpenAICompatBackend, PromptedToolsBackend, ScriptedBackend,
                       ToolCall)
from .core import (HarnessConfig, HarnessError, HarnessTimeout, INITIATOR,
                   RESPONDER, ROLES, SaphirHarness)
from .tools import MAX_SLOTS_JSON, ToolBridge
from .transport import (DEFAULT_TIMEOUT, FileTransport, LoopbackTransport,
                        TcpTransport, Transport, TransportError, parse_hostport)

__all__ = [
    "SaphirHarness", "HarnessConfig", "HarnessError", "HarnessTimeout",
    "INITIATOR", "RESPONDER", "ROLES",
    "ToolBridge", "MAX_SLOTS_JSON",
    "SaphirAgent", "AgentRun",
    "ChatBackend", "ModelTurn", "ToolCall", "BackendError",
    "OllamaChatBackend", "OpenAICompatBackend", "PromptedToolsBackend",
    "ScriptedBackend",
    "Transport", "TransportError", "LoopbackTransport", "FileTransport",
    "TcpTransport", "parse_hostport", "DEFAULT_TIMEOUT",
]
