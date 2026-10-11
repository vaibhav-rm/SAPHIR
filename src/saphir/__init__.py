"""SAPHIR: Secure Acoustic Pairing for Heterogeneous Inter-agent Rendezvous."""
from .protocol import (
    MsgType, HelloPayload, TaskPayload, Envelope,
    encode_envelope, decode_envelope,
    build_hello, build_task, PROTOCOL_VERSION,
    CODEC_IDS, CODEC_NAMES, MODE_AUDIO, MODE_HYBRID,
    normalize_codecs, normalize_selected,
)
from .crypto import EphemeralKeypair, SessionKeys, derive_session_keys
from .codec import compact_task, expand_task
from .session import SaphirSession, SessionState, HandshakeError
from .channel import (InMemoryChannel, LossyChannel, ChannelStats, ReliableLink, LinkStats,
                      BurstChannel, ChannelProfile, PROFILES)
from .audit import AuditLog
from .agents import CallerAgent, ReceptionistAgent, run_booking_dialogue
from .agents import TaxiDispatch, TAXI_TASKS, TAXI_FLEET

__version__ = "0.1.0"
__all__ = [
    "MsgType", "HelloPayload", "TaskPayload", "Envelope",
    "encode_envelope", "decode_envelope", "build_hello", "build_task",
    "PROTOCOL_VERSION", "CODEC_IDS", "CODEC_NAMES", "MODE_AUDIO", "MODE_HYBRID",
    "normalize_codecs", "normalize_selected", "EphemeralKeypair", "SessionKeys", "derive_session_keys",
    "SaphirSession", "SessionState", "HandshakeError",
    "compact_task", "expand_task",
    "InMemoryChannel", "LossyChannel", "ChannelStats",
    "ReliableLink", "LinkStats",
    "BurstChannel", "ChannelProfile", "PROFILES",
    "AuditLog", "CallerAgent", "ReceptionistAgent", "run_booking_dialogue",
    "TaxiDispatch", "TAXI_TASKS", "TAXI_FLEET",
]
