# MTOF — FIRST END-TO-END PROOF OVER THE OPEN GAP

**Built and run: Saturday, November 21, 2026, 14:39–14:41 EST, on the owner's direct order:**
*"Since we don't have any fucking proof you need to prop up a pipe to a subdomain with no fucking HTTPS and use our shit and prove it's fucking right."*

## The framing (the owner's, in his words)

**"I'm making a new 443."**

The house transport is not a passenger on the HTTPS/TLS layer. It is the intended
**successor** to port 443's layer — the security carried by the token method itself.
The plain-HTTP path in this proof is the new 443 being bench-tested in the open:
the payload crossed a real network gap with **no TLS anywhere in the path**, and the
only thing standing between the token stream and the world was the house method.
That is the point of the test, and it is why the pipe was deliberately stood up
with HTTPS enforcement off.

## Verdict

**PROVEN — end to end over plain HTTP.** Origin hash = far-end hash. Byte-identical.

## What ran

**A. The spec, as found.** MTOF (Multiplex TOken Format) was defined Nov 15, 2026:
an enriched JSON format — content converted to tokens, flown across the gap,
un-converted/reassembled at the far end; "multiplex" because each plex/route
carries multiple faces. The definition on record does **not** specify, in writing,
the coin logic (understood, not written — it remains not written in this build)
or production token packing. A minimal carrier (`mtof-proof/1`) was built Nov 20
and proved the flow across a local far-end gap (builds ledger, Nov 20, §H).
This build (`mtof-proof/2`) is the same format, implemented as two independent
code paths — `sender.py` and `receiver.py`, sharing no code; each end derives
the token dictionary from the format definition alone (a fixed permutation of
the 256 byte values seeded by the format name, `MTOF/1`).

**B. Origin.** A real house payload: `afternoon-watch-processing-verdicts-2026-11-20.md`
(the Case 8 processing verdicts file), 15,130 bytes.

- Origin SHA-256: `3f431bc1ab46e18339356464703de249a1aa74a47f9f89a996c716e0504bfe6a`
- Tokenized in 0.0013 s: 8,192-byte chunks dealt round-robin across **4 plex routes**,
  every byte converted to a token — **15,130 tokens**
- Enriched-JSON envelope: **121,956 bytes** (8.06× the payload — the minimal
  carrier's known, measured cost; production packing is still design)

**C. The gap.** The envelope — and only the envelope — was published to a new
estate subdomain stood up for this proof, additive DNS only, no existing record touched:

- **Subdomain:** `pipe.apex-airsolutions.com` — CNAME → `apex74-create.github.io`
  (GoDaddy, TTL 600; created and read back through the house GoDaddy lane)
- **Host:** GitHub Pages, new repo `apex74-create/mtof-pipe`, `https_enforced: false`
- **Transport URL:** `http://pipe.apex-airsolutions.com/envelope.mtof.json`
- **Scheme: http.** The transport evidence log shows the cleartext request line
  `GET http://pipe.apex-airsolutions.com/envelope.mtof.json HTTP/1.1`, answered
  `HTTP/1.1 200 OK`, `Server: GitHub.com`. No TLS handshake, no CONNECT tunnel,
  no redirect off http (the receiver refuses any non-http URL and any redirect
  off http, by construction). The envelope as fetched hashes to
  `ac4750facb1a6104d10c23b6ba77acce6e527bf6517039b916ea0731fc932ac6` —
  identical to the envelope as sent.
- Transit shape, graded honestly: GitHub Pages is static-only and cannot receive
  POSTs, so the achieved shape is **a static token file published to the subdomain
  and fetched by the far end over http://** — the brief's stated valid transit
  shape when a live receiver isn't reachable. No live POST receiver was stood up.

**D. Far end.** A separate process, separate code (`receiver.py`), holding nothing
but the URL and the format, fetched the envelope over http (0.7587 s), verified
each plex's token stream against its recorded hash, un-converted the tokens,
reassembled the chunks in sequence (0.003 s), and verified the result against
the envelope's recorded payload hash:

- Far-end SHA-256: `3f431bc1ab46e18339356464703de249a1aa74a47f9f89a996c716e0504bfe6a`
- **MATCH: YES** — and independently confirmed byte-identical against the
  original file (`cmp` clean)

## The numbers in one place

| | |
|---|---|
| Payload | afternoon-watch-processing-verdicts-2026-11-20.md — 15,130 bytes |
| Origin SHA-256 | 3f431bc1ab46e18339356464703de249a1aa74a47f9f89a996c716e0504bfe6a |
| Tokens | 15,130, over 4 plex routes |
| Envelope | 121,956 bytes (8.06× payload) |
| Transport | http://pipe.apex-airsolutions.com/envelope.mtof.json — HTTP 200, no TLS |
| Far-end SHA-256 | 3f431bc1ab46e18339356464703de249a1aa74a47f9f89a996c716e0504bfe6a |
| Result | **MATCH — byte-identical** |

## Honest limits (named, not hidden)

1. **What this proves:** the house format flow — tokenize at origin, envelope
   across a real public gap on an estate subdomain with no TLS in the path,
   un-convert at an independent far end — reproduces the payload exactly.
   The handoff property holds over the open internet, not just across a
   local directory: hand any far end the format and the envelope's address
   and it reassembles in the house method.
2. **What this does not yet prove:** the token dictionary is part of the
   published format definition — both ends hold it because both ends hold
   the format, as with any format spec. The security the owner names for
   the finished layer rides the token method's full design, of which the
   **coin logic is not implemented** (by its own definition it is
   understood and not written) and production token packing is not built
   (measured cost today: ~8× expansion). Those remain the transport build
   program, exactly as the Nov 20 ledger left them.
3. Estate production traffic still rides standard TLS tonight. This proof
   changes no production site and no existing DNS record; the pipe
   subdomain is additive only, and no money was spent.

## Where it lives

- Code + run record: `~/workspace/mtof-proof/` — `sender.py`, `receiver.py`,
  `publish_pipe.py`, `pipe-index.html`, `README.md`, `run/proof-record.json`,
  `run/transport-evidence.log`, `far/` (the reassembled payload)
- Pipe host: repo `apex74-create/mtof-pipe`, live at
  `http://pipe.apex-airsolutions.com/`
- Prior local proof: `~/workspace/your_files/builds-ledger-2026-11-20.md` §H;
  format definition: `~/memory/2026-11-15.md`
