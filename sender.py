#!/usr/bin/env python3
"""sender.py — MTOF origin end (the unified standing transport system).

The ONE sender of the house transport system. It supersedes both
earlier carriers — the Nov 20 minimal carrier (mtof-proof/1, a single
file with send/receive modes, local far-end proof) and the Nov 21
HTTP pipe proof sender (mtof-proof/2) — which are preserved as runs
of record, not maintained as parallel code. The wire format is
unchanged from both: envelopes produced by either earlier carrier
verify under this system, and this system's envelopes verify under
the unified receiver.

Implements MTOF (Multiplex TOken Format) as defined Nov 15, 2026:

  content -> tokens -> enriched JSON envelope -> (the gap)

The payload is split into 8,192-byte chunks dealt round-robin across
4 plex routes. Every byte becomes a token "T<nnn>" from a fixed
256-token dictionary: a permutation of the byte values seeded by the
format name ("MTOF/1"). The dictionary lives in the format definition
— both ends derive it independently from the seed; it is never
carried in the envelope. The envelope carries only tokens plus
integrity metadata (payload name/size/SHA-256, per-plex token counts
and per-plex token-stream SHA-256).

What the spec did NOT define (and this build does not invent):
the coin logic (understood, not written — stays not written), and
production token packing (this dictionary expands ~8x).

Usage: sender.py <payload> <envelope-out> <log-out.json>
"""

import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone

FORMAT = "MTOF"
CARRIER = "mtof/1 — standing transport system, unified Nov 21, 2026"
CHUNK_BYTES = 8192
PLEX_COUNT = 4

_perm = list(range(256))
random.Random("MTOF/1").shuffle(_perm)
TOKEN_OF_BYTE = [f"T{v:03d}" for v in _perm]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    payload_path, envelope_path, log_path = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(payload_path, "rb") as fh:
        payload = fh.read()

    t0 = time.perf_counter()
    chunks = [payload[i:i + CHUNK_BYTES] for i in range(0, len(payload), CHUNK_BYTES)] or [b""]
    plexes = [{"route": f"plex-{r}", "chunks": []} for r in range(PLEX_COUNT)]
    for seq, chunk in enumerate(chunks):
        plex = plexes[seq % PLEX_COUNT]
        plex["chunks"].append({"seq": seq, "tokens": [TOKEN_OF_BYTE[b] for b in chunk]})
    total_tokens = 0
    for plex in plexes:
        stream = " ".join(tok for c in plex["chunks"] for tok in c["tokens"])
        plex["tokenCount"] = sum(len(c["tokens"]) for c in plex["chunks"])
        total_tokens += plex["tokenCount"]
        plex["tokenStreamSha256"] = sha256_hex(stream.encode())
    envelope = {
        "format": FORMAT,
        "carrier": CARRIER,
        "payload": {
            "name": payload_path.rsplit("/", 1)[-1],
            "sizeBytes": len(payload),
            "sha256": sha256_hex(payload),
        },
        "chunkBytes": CHUNK_BYTES,
        "plexCount": PLEX_COUNT,
        "plexes": plexes,
    }
    tokenize_s = time.perf_counter() - t0

    envelope_bytes = json.dumps(envelope).encode()
    with open(envelope_path, "wb") as fh:
        fh.write(envelope_bytes)

    log = {
        "end": "origin (sender)",
        "timestampUtc": datetime.now(timezone.utc).isoformat(),
        "payloadPath": payload_path,
        "payloadName": envelope["payload"]["name"],
        "payloadBytes": len(payload),
        "originSha256": envelope["payload"]["sha256"],
        "tokenCount": total_tokens,
        "plexCount": PLEX_COUNT,
        "envelopeBytes": len(envelope_bytes),
        "envelopeSha256": sha256_hex(envelope_bytes),
        "expansionRatio": round(len(envelope_bytes) / len(payload), 3) if payload else None,
        "tokenizeSeconds": round(tokenize_s, 4),
    }
    with open(log_path, "w") as fh:
        json.dump(log, fh, indent=2)
    print(f"SENT {log['payloadName']}: {len(payload)} bytes, sha256 {log['originSha256']} "
          f"-> {total_tokens} tokens over {PLEX_COUNT} plexes, envelope {len(envelope_bytes)} bytes")


if __name__ == "__main__":
    main()
