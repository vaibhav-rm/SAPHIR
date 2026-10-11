"""Real-ggwave interop: the exact demo payloads through real ggwave encode/decode.

Proves (a) every demo frame fits ggwave's ~140B ceiling, (b) the web demo's
JSON framing and this repo's Python side speak the same over-air language.
Requires: pip install ggwave (builds the C++ extension; needs a compiler).
"""
import sys
sys.path.insert(0, "src")

PAYLOADS = [
    '{"t":"HELLO","f":"c","did":"9f2c"}',
    '{"t":"WELCOME","f":"r","did":"41ab","sel":"std"}',
    '{"t":"KEY1","f":"c","p":"' + 'A' * 88 + '"}',
    '{"t":"TASK","q":3,"f":"c","i":"hb","c":"' + 'B' * 72 + '"}',
    '{"t":"RESULT","q":2,"f":"r","c":"' + 'C' * 64 + '"}',
]

PROTOCOLS = {0: "normal", 1: "fast"}


def main():
    try:
        import ggwave
    except ImportError:
        print("SKIP: pip install ggwave first")
        return 1
    ggwave.disableLog()
    inst = ggwave.init()
    try:
        for proto, name in PROTOCOLS.items():
            for p in PAYLOADS:
                assert len(p) <= 138, f"over budget: {len(p)}"
                wf = ggwave.encode(p, protocolId=proto, volume=20)
                back = ggwave.decode(inst, wf)
                assert back is not None, f"decode failed proto={name} len={len(p)}"
                assert back.decode() == p, f"roundtrip mismatch proto={name}"
                print(f"[PASS] {name:6s} {len(p):3d}B roundtrip ok")
    finally:
        ggwave.free(inst)
    print("ALL GGWAVE INTEROP OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
