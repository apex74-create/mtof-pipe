# MTOF Proof — the house transport, proven over plain HTTP

**What was proven (Nov 21, 2026):** a real house payload was converted
to MTOF tokens at the origin, the token envelope was published to an
estate subdomain, an independent far-end process fetched it over
**plain HTTP — no HTTPS/TLS anywhere in the path** — un-converted it,
and the reassembled payload's SHA-256 matched the origin hash exactly,
byte for byte.

The owner's framing for the program: *"I'm making a new 443."* The
house transport is not a passenger on the HTTPS/TLS layer; it is the
intended successor to port 443's layer, with the security carried by
the token method itself. This proof is that layer bench-tested in the
open — which is why no TLS appears anywhere in the path.

## The run

- **Payload:** `afternoon-watch-processing-verdicts-2026-11-20.md`
  (Case 8 processing verdicts, a real estate file), 15,130 bytes
- **Origin SHA-256:** `3f431bc1ab46e18339356464703de249a1aa74a47f9f89a996c716e0504bfe6a`
- **Tokenized:** 15,130 tokens over 4 plex routes, enriched-JSON
  envelope of 121,956 bytes (8.06× — the known minimal-carrier cost)
- **The gap:** `http://pipe.apex-airsolutions.com/envelope.mtof.json`
  (CNAME → apex74-create.github.io, GitHub Pages repo
  `apex74-create/mtof-pipe`, `https_enforced: false`)
- **Far end SHA-256:** `3f431bc1ab46e18339356464703de249a1aa74a47f9f89a996c716e0504bfe6a`
- **Verdict: MATCH** — byte-identical (`cmp` clean)

## Files

- `sender.py` — origin end: payload → tokens → enriched-JSON envelope
- `receiver.py` — far end: independent code path; derives the token
  dictionary from the format definition alone, refuses any non-http
  URL, fetches the envelope, verifies per-plex stream hashes,
  reassembles, verifies the payload hash
- `publish_pipe.py` — publishes the envelope + CNAME + index to the
  pipe repo and enables Pages with the custom domain
- `pipe-index.html` — the pipe host's index page
- `run/` — send log, receive log, combined `proof-record.json`,
  sanitized transport evidence (cleartext `GET http://…` request line,
  HTTP/1.1 200, Server: GitHub.com), the envelope as sent and as fetched
- `far/` — the reassembled payload, as the far end produced it

## Honest scope

- Transit shape achieved: a **static token file published to the
  subdomain and fetched by the far end over http://** — GitHub Pages
  is static-only and cannot receive POSTs, so no live receiver
  endpoint was stood up. The fetch, the scheme, and the far-end
  reassembly are all real and logged.
- The format as defined (Nov 15, 2026): content converted to tokens,
  wrapped in enriched JSON, multiplexed across plex routes, flown
  across the gap, un-converted at the far end. The spec did **not**
  define, in writing: the coin logic (understood, not written — it
  stays not written in this build) or production token packing.
- The token dictionary is part of the published format definition —
  both ends derive it from the seed `MTOF/1`, the way both ends of
  any format hold its spec. Integrity in this proof is carried by
  per-plex stream hashes plus the payload SHA-256 in the envelope.
- Prior step on record: Nov 20, 2026 proved the same carrier flow
  across a local far-end gap (builds ledger §H). What is new here is
  the real network gap: an estate subdomain, a public host, and a
  far-end fetch over the open internet with no TLS in the path.
