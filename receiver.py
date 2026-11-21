#!/usr/bin/env python3
"""receiver.py — MTOF far end (the unified standing transport system).

The ONE receiver of the house transport system. INDEPENDENT code path
from sender.py: this file shares no code with the sender. It derives
the same token dictionary from the format definition alone (the fixed
permutation seeded by "MTOF/1"), fetches the MTOF envelope from a URL,
and un-converts it.

The fetch is PLAIN HTTP BY DESIGN: the house method — not TLS — is
what carries the payload on the pipe. Any URL whose scheme is not
exactly "http" is refused before a byte moves, and a redirect off
http is refused after the fact.

The receiver holds nothing but the URL and the format. It records the
SHA-256 of the envelope bytes exactly as fetched (so the caller can
compare them against the envelope bytes as sent), verifies each
plex's token stream against the envelope's recorded stream hash,
reassembles the chunks in sequence, and verifies the result against
the envelope's recorded payload SHA-256 and size.

On any verification failure it still writes its log (match: false,
failure named) and exits 1, so a watching cycle can grade the failure
from the log instead of guessing from a crash.

Usage: receiver.py <http-url> <payload-out> <log-out.json>
Exit: 0 when the reassembled payload matches the envelope's record,
      1 on refusal or any verification failure (log still written
      whenever the envelope itself could be fetched and parsed).
"""

import hashlib
import json
import random
import sys
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

FORMAT = "MTOF"

_perm = list(range(256))
random.Random("MTOF/1").shuffle(_perm)
BYTE_OF_TOKEN = {f"T{v:03d}": b for b, v in enumerate(_perm)}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    url, payload_out, log_path = sys.argv[1], sys.argv[2], sys.argv[3]
    parsed = urlparse(url)
    if parsed.scheme != "http":
        sys.exit(f"REFUSED: scheme is {parsed.scheme!r}, the pipe runs on plain http only")

    log = {"end": "far end (receiver)", "transportUrl": url}
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"User-Agent": "mtof/1 receiver (standing transport)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        status = resp.status
        final_url = resp.geturl()
        server = resp.headers.get("Server")
        raw = resp.read()
    fetch_s = time.perf_counter() - t0
    if urlparse(final_url).scheme != "http":
        sys.exit(f"REFUSED: fetch was redirected off http to {final_url}")

    log.update({
        "timestampUtc": datetime.now(timezone.utc).isoformat(),
        "finalUrl": final_url,
        "scheme": urlparse(final_url).scheme,
        "httpStatus": status,
        "serverHeader": server,
        "envelopeBytesFetched": len(raw),
        "envelopeSha256": sha256_hex(raw),
        "fetchSeconds": round(fetch_s, 4),
        "match": False,
        "failure": None,
    })

    t1 = time.perf_counter()
    try:
        envelope = json.loads(raw)
        if envelope.get("format") != FORMAT:
            raise ValueError(f"format is {envelope.get('format')!r}, expected {FORMAT!r}")
        chunks = {}
        for plex in envelope["plexes"]:
            stream = " ".join(tok for c in plex["chunks"] for tok in c["tokens"])
            if sha256_hex(stream.encode()) != plex["tokenStreamSha256"]:
                raise ValueError(f"token stream hash mismatch on {plex['route']}")
            for c in plex["chunks"]:
                chunks[c["seq"]] = bytes(BYTE_OF_TOKEN[tok] for tok in c["tokens"])
        payload = b"".join(chunks[seq] for seq in sorted(chunks))
    except Exception as exc:  # envelope fetched but does not verify as MTOF
        log["failure"] = f"envelope verification failed: {exc}"
        with open(log_path, "w") as fh:
            json.dump(log, fh, indent=2)
        print(f"FAILED {url}: {log['failure']}")
        sys.exit(1)
    reassemble_s = time.perf_counter() - t1

    with open(payload_out, "wb") as fh:
        fh.write(payload)

    far_hash = sha256_hex(payload)
    origin_hash = envelope["payload"]["sha256"]
    match = far_hash == origin_hash and len(payload) == envelope["payload"]["sizeBytes"]
    log.update({
        "reassembleSeconds": round(reassemble_s, 4),
        "payloadName": envelope["payload"]["name"],
        "payloadBytes": len(payload),
        "originSha256FromEnvelope": origin_hash,
        "farEndSha256": far_hash,
        "match": match,
        "failure": None if match else "reassembled payload hash/size mismatch",
    })
    with open(log_path, "w") as fh:
        json.dump(log, fh, indent=2)
    print(f"RECEIVED {log['payloadName']}: {len(payload)} bytes over http, "
          f"far-end sha256 {far_hash}, MATCH={match}")
    if not match:
        sys.exit(1)


if __name__ == "__main__":
    main()
