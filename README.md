# MTOF Standing Transport — the house transport, assembled into one system

**What this is.** The house transport (MTOF — Multiplex TOken Format,
defined Nov 15, 2026) assembled from all its pieces into a single
standing system, on the owner's order of Nov 21, 2026: *"Put all my
pieces together in one system — an end-to-end transport. Then just
stay transport and see if it gets interrupted. If you leave a pipe
open, someone's going to come and check it."*

**Home.** This repository — `apex74-create/mtof-pipe`, served at
**http://pipe.apex-airsolutions.com** (GitHub Pages,
`https_enforced: false` — plain HTTP by design; the token method,
not TLS, is the layer). A local mirror of the system lives at
`~/workspace/mtof-transport/`.

## The pipeline (one sender, one receiver)

```
origin payload → sender.py (tokenize, MTOF) → envelope.mtof.json
  published to pipe.apex-airsolutions.com → receiver.py fetches it
  over plain http:// (independent code path) → un-convert →
  SHA-256 verify → grade appended to the transport log
```

- `sender.py` — the one origin end. Supersedes the Nov 20 minimal
  carrier (`mtof-proof/1`) and the Nov 21 proof sender (`mtof-proof/2`);
  the wire format is identical to both, so every earlier envelope
  still verifies.
- `receiver.py` — the one far end. Shares no code with the sender;
  derives the token dictionary from the format definition alone,
  refuses any non-http URL, records the fetched envelope's hash,
  verifies per-plex stream hashes and the payload hash.
- `cycle.py` — one standing cycle: resting-envelope check, heartbeat
  payload build (cycle # + UTC timestamp + a rotating 512-byte slice
  of the real house corpus in `corpus/`), tokenize, publish, converge,
  receive, grade, and publish the log.
- `.github/workflows/transport-cycle.yml` — runs `cycle.py` every
  **30 minutes** (and on manual dispatch), with the repo's own
  `GITHUB_TOKEN` scoped to `contents: write` on this repo only.

## The watch

Every cycle grades exactly one of:

- **PASS** — envelope bytes as fetched identical to bytes as
  published; reassembled payload hash identical to origin hash.
- **INTERRUPTED** — a leg of the transport failed: publish, fetch
  (host/subdomain down), publish-converge, or a stale envelope served
  to the receiver. The failed leg is named in the entry.
- **TAMPERED** — bytes changed in transit or at rest: fetched
  envelope ≠ published envelope, a stream/payload verification
  failure, or the resting check found a previous cycle's envelope
  altered on the host. As-sent and as-fetched envelopes are preserved
  under `cycles/` as evidence.

The diary is public and append-only:
**http://pipe.apex-airsolutions.com/transport-log.html** (readable) ·
**http://pipe.apex-airsolutions.com/transport-log.json** (machine).
Each entry records the envelope's as-published hash, so a silent
change to a resting envelope is caught by the next cycle's resting
check. TAMPERED and INTERRUPTED entries are never overwritten.

## Runs of record

- **Cycle 0** — the one-shot first proof (Nov 21, 2026): the Case 8
  verdicts file crossed the open gap over plain HTTP and reassembled
  byte-identical, SHA-256 `3f431bc1…bfe6a`. Envelope and proof record
  archived in `runs/first-proof-2026-11-21/`; report:
  `mtof-first-proof-2026-11-21.md`.
- Before it: the Nov 20 minimal carrier proved the same flow across a
  local far-end gap (builds ledger, Nov 20, §H), and the format was
  defined Nov 15, 2026 (`mtof-ham-transport-package-2026-11-15.md`).

## Honest limits

- Transit shape: a static token envelope published to the subdomain
  and fetched over http:// — GitHub Pages is static-only and cannot
  receive POSTs. The fetch, the scheme, and the far-end reassembly
  are real and logged every cycle.
- The token dictionary is part of the published format definition;
  both ends hold it because both ends hold the format. The **coin
  logic is not implemented** — by its own definition it is understood
  and not written, and it stays that way here. Production token
  packing is not built; this dictionary's measured cost is ~8×
  expansion.
- Estate production traffic still rides standard TLS. This system is
  the transport standing on its own pipe, watched — the build program
  that wires it into estate pipes is separate and later.
