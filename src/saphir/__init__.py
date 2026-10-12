"""SAPHIR: Secure Acoustic Pairing for Heterogeneous Inter-agent Rendezvous."""
from .protocol import (
    MsgType, HelloPayload, TaskPayload, Envelope,
    encode_envelope, decode_envelope,
    build_hello, build_task, PROTOCOL_VERSION,
    CODEC_IDS, CODEC_NAMES, MODE_AUDIO, MODE_HYBRID,
    normalize_codecs, normalize_selected,
)
from .crypto import EphemeralKeypair, SessionKeys, derive_session_keys, exchange, keys_from_shared
from .codec import compact_task, expand_task
from .caps import BloomFilter, match, offered_bitmask, INTENT_IDS, INTENT_NAMES
from .resume import TicketStore, Ticket, ticket_id, ticket_from_shared, resumed_keys
from .llm import (LLMBackend, MockBackend, OllamaBackend, AgentCaller,
                  AgentReceptionist, extract_json, coerce_plan)
from .session import SaphirSession, SessionState, HandshakeError
from .channel import (InMemoryChannel, LossyChannel, ChannelStats, ReliableLink, LinkStats,
                      BurstChannel, ChannelProfile, PROFILES)
from .link import LocalLink, LinkError
from .audit import AuditLog
from .agents import CallerAgent, ReceptionistAgent, run_booking_dialogue
from .agents import TaxiDispatch, TAXI_TASKS, TAXI_FLEET

__version__ = "0.1.0"
__all__ = [
    "MsgType", "HelloPayload", "TaskPayload", "Envelope",
    "encode_envelope", "decode_envelope", "build_hello", "build_task",
    "PROTOCOL_VERSION", "CODEC_IDS", "CODEC_NAMES", "MODE_AUDIO", "MODE_HYBRID",
    "normalize_codecs", "normalize_selected",     "EphemeralKeypair", "SessionKeys", "derive_session_keys",
    "exchange", "keys_from_shared",
    "SaphirSession", "SessionState", "HandshakeError",
    "compact_task", "expand_task",
    "BloomFilter", "match", "offered_bitmask", "INTENT_IDS", "INTENT_NAMES",
    "TicketStore", "Ticket", "ticket_id", "ticket_from_shared", "resumed_keys",
    "LLMBackend", "MockBackend", "OllamaBackend", "AgentCaller",
    "AgentReceptionist", "extract_json", "coerce_plan",
    "InMemoryChannel", "LossyChannel", "ChannelStats",
    "ReliableLink", "LinkStats",
    "BurstChannel", "ChannelProfile", "PROFILES",
    "LocalLink", "LinkError",
    "AuditLog", "CallerAgent", "ReceptionistAgent", "run_booking_dialogue",
    "TaxiDispatch", "TAXI_TASKS", "TAXI_FLEET",
]
