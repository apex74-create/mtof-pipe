#!/usr/bin/env python3
"""cycle.py — one standing cycle of the house transport (MTOF).

Run by the GitHub Actions workflow in this repo every 30 minutes, and
runnable by hand from the system's local home. One cycle:

  1. RESTING CHECK — fetch the envelope currently resting on the pipe
     over plain http and compare its hash against the hash the log
     recorded as published last cycle. A silent change to a resting
     envelope is itself a finding (TAMPERED) on this cycle's entry.
  2. BUILD — assemble a fresh heartbeat payload: cycle number, UTC
     timestamp, and a rotating 512-byte slice of real house content
     from corpus/ (the slice offset advances with the cycle number).
  3. TOKENIZE — run the unified sender (separate process).
  4. PUBLISH — put the envelope on the pipe subdomain through the
     GitHub Contents API (this repo only; the credential used can
     touch nothing else).
  5. CONVERGE + RECEIVE — wait until the pipe serves the new envelope
     over plain http, then run the unified receiver (separate
     process, independent code path) against the plain URL.
  6. GRADE — exactly one of:
       PASS        envelope bytes as fetched == as published, and
                   the reassembled payload hash == origin hash.
       INTERRUPTED a leg of the transport failed: publish failed,
                   the host/subdomain did not answer, the new envelope
                   never converged into service, or the receiver was
                   served a stale envelope. The failed leg is named.
       TAMPERED    bytes changed in transit or at rest: fetched
                   envelope bytes differ from published bytes, a plex
                   stream or the payload fails verification, or the
                   resting check found last cycle's envelope altered.
     The graded entry is appended to transport-log.json and the log
     (JSON + rendered HTML) is published back to the pipe, where it
     is served as the pipe's own public diary. TAMPERED and
     INTERRUPTED entries are never overwritten or removed; on a
     TAMPERED grade the as-sent and as-fetched envelopes are also
     preserved under cycles/ as evidence.

Auth: inside GitHub Actions the workflow's own GITHUB_TOKEN is used
(repo-scoped by construction — it cannot touch any other repo or
record). Outside Actions, the house GitHub connector's surrogate
credential is used, as in the first proof's publish step.

Usage: cycle.py [--no-publish-log]   (the flag exists for debugging;
a normal cycle always publishes its log entry, failures included)
"""

import base64
import hashlib
import html
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = "apex74-create/mtof-pipe"
API = "https://api.github.com"
PIPE_BASE = "http://pipe.apex-airsolutions.com"
ENVELOPE_NAME = "envelope.mtof.json"
ENVELOPE_URL = f"{PIPE_BASE}/{ENVELOPE_NAME}"
LOG_JSON = "transport-log.json"
LOG_HTML = "transport-log.html"
SLICE_BYTES = 512
CONVERGE_TIMEOUT_S = 600
CONVERGE_POLL_S = 10
RECEIVER_RETRY_S = 90

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runner_name() -> str:
    return "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local-vm"


# ---------------------------------------------------------------- API

def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    else:
        from dynamic_credentials import add_surrogate_to_request
        add_surrogate_to_request(req, "custom.github", allowed_hosts=["api.github.com"])
    try:
        with urllib.request.build_opener().open(req, timeout=60) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]


def put_file(name, content: bytes, message):
    status, existing = api("GET", f"/repos/{REPO}/contents/{name}?ref=main")
    body = {"message": message,
            "content": base64.b64encode(content).decode(),
            "branch": "main"}
    if status == 200 and isinstance(existing, dict) and existing.get("sha"):
        body["sha"] = existing["sha"]
    status, resp = api("PUT", f"/repos/{REPO}/contents/{name}", body)
    if status not in (200, 201):
        raise RuntimeError(f"PUT {name} failed: HTTP {status}: {resp}")
    return status


def commit_files(files, message):
    """Commit several files as ONE commit via the Git trees API.

    The pipe host rebuilds on every push, serially; one commit for the
    whole log update (JSON + HTML + any evidence) keeps a cycle to two
    host builds total — the envelope push and this one. (The first
    standing cycle graded INTERRUPTED at the converge leg because a
    13-commit deploy burst had the host's build queue backed up for
    minutes; this is the fix, along with the longer converge window.)
    """
    for attempt in (1, 2):
        status, ref = api("GET", f"/repos/{REPO}/git/ref/heads/main")
        head_sha = ref["object"]["sha"]
        status, head = api("GET", f"/repos/{REPO}/git/commits/{head_sha}")
        entries = []
        for name, content in files:
            status, blob = api("POST", f"/repos/{REPO}/git/blobs",
                               {"content": base64.b64encode(content).decode(),
                                "encoding": "base64"})
            if status != 201:
                raise RuntimeError(f"blob for {name}: HTTP {status}: {blob}")
            entries.append({"path": name, "mode": "100644",
                            "type": "blob", "sha": blob["sha"]})
        status, tree = api("POST", f"/repos/{REPO}/git/trees",
                           {"base_tree": head["tree"]["sha"], "tree": entries})
        if status != 201:
            raise RuntimeError(f"tree: HTTP {status}: {tree}")
        status, commit = api("POST", f"/repos/{REPO}/git/commits",
                             {"message": message, "tree": tree["sha"],
                              "parents": [head_sha]})
        if status != 201:
            raise RuntimeError(f"commit: HTTP {status}: {commit}")
        status, resp = api("PATCH", f"/repos/{REPO}/git/refs/heads/main",
                           {"sha": commit["sha"]})
        if status == 200:
            return commit["sha"]
        if attempt == 2:
            raise RuntimeError(f"ref update: HTTP {status}: {resp}")
    return None


# ---------------------------------------------------------------- log

def load_log() -> dict:
    path = HERE / LOG_JSON
    if path.exists():
        return json.loads(path.read_text())
    return {"system": "MTOF standing transport", "cycles": []}


def render_html(log: dict) -> str:
    rows = []
    for c in reversed(log["cycles"]):
        grade = c.get("grade", "?")
        color = {"PASS": "#1a7f37", "INTERRUPTED": "#b45309", "TAMPERED": "#b91c1c"}.get(grade, "#555")
        rows.append(
            "<tr>"
            f"<td>{c['cycle']}</td>"
            f"<td>{html.escape(str(c.get('startedUtc', '')))}</td>"
            f"<td style='color:{color};font-weight:bold'>{html.escape(grade)}</td>"
            f"<td>{html.escape(str(c.get('detail', '')))}</td>"
            f"<td><code>{html.escape(str(c.get('payloadSha256') or '')[:16])}…</code></td>"
            f"<td><code>{html.escape(str(c.get('envelopeSha256AsPublished') or '')[:16])}…</code></td>"
            "</tr>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>MTOF Standing Transport — Log</title></head>
<body>
<h1>MTOF Standing Transport — the pipe's diary</h1>
<p>This subdomain is the transit host of the house transport
(MTOF — Multiplex TOken Format, Apex Air Solutions). A standing cycle
runs every {log.get('cadenceMinutes', 30)} minutes: a fresh heartbeat
payload is tokenized at the origin, published here as
<a href="envelope.mtof.json">envelope.mtof.json</a>, fetched back over
plain HTTP by an independent receiver, un-converted, and hash-verified.
Every cycle's grade is appended to this log and never rewritten.</p>
<p>Grades: <b>PASS</b> — bytes arrived exactly as sent and the payload
reassembled hash-identical. <b>INTERRUPTED</b> — a leg of the transport
failed (the failed leg is named). <b>TAMPERED</b> — bytes changed in
transit or at rest.</p>
<p>Machine-readable log: <a href="transport-log.json">transport-log.json</a>.
Current envelope: <a href="envelope.mtof.json">envelope.mtof.json</a>.</p>
<table border="1" cellspacing="0" cellpadding="6">
<tr><th>Cycle</th><th>Started (UTC)</th><th>Grade</th><th>Detail</th>
<th>Payload SHA-256</th><th>Envelope SHA-256 (as published)</th></tr>
{''.join(rows)}
</table>
</body>
</html>
"""


def publish_log(log: dict, extra_files=None):
    (HERE / LOG_JSON).write_text(json.dumps(log, indent=2))
    (HERE / LOG_HTML).write_text(render_html(log))
    last = log["cycles"][-1]
    files = [(LOG_JSON, (HERE / LOG_JSON).read_bytes()),
             (LOG_HTML, (HERE / LOG_HTML).read_bytes())]
    for name, content, _message in (extra_files or []):
        files.append((name, content))
    commit_files(files, f"transport log: cycle {last['cycle']} {last['grade']}")


# ---------------------------------------------------------------- http

def fetch(url: str, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "mtof/1 cycle watch"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


# ---------------------------------------------------------------- cycle

def build_payload(cycle_no: int, started: str) -> bytes:
    corpus = b""
    for path in sorted((HERE / "corpus").glob("*.md")):
        corpus += path.read_bytes() + b"\n"
    offset = (cycle_no * SLICE_BYTES) % len(corpus)
    slice_bytes = (corpus[offset:] + corpus[:offset])[:SLICE_BYTES]
    header = (
        "MTOF STANDING TRANSPORT — HEARTBEAT\n"
        f"cycle: {cycle_no}\n"
        f"timestampUtc: {started}\n"
        "system: mtof/1 standing transport, pipe.apex-airsolutions.com\n"
        f"content: rotating slice of the house corpus, offset {offset}, "
        f"{SLICE_BYTES} bytes, unedited\n"
        "--- slice begins ---\n"
    ).encode()
    footer = b"\n--- slice ends ---\n"
    return header + slice_bytes + footer


def main() -> int:
    started = now_utc()
    log = load_log()
    cycles = log.setdefault("cycles", [])
    cycle_no = (cycles[-1]["cycle"] + 1) if cycles else 1
    entry = {
        "cycle": cycle_no,
        "runner": runner_name(),
        "startedUtc": started,
        "publishedUtc": None,
        "fetchedUtc": None,
        "payloadName": None,
        "payloadBytes": None,
        "payloadSha256": None,
        "envelopeBytes": None,
        "envelopeSha256AsPublished": None,
        "envelopeSha256AsFetched": None,
        "farEndSha256": None,
        "httpStatus": None,
        "restingEnvelopeCheck": {"result": "not-run"},
        "grade": None,
        "detail": "",
    }
    evidence = []          # (repo path, bytes, message) for TAMPERED cycles
    workdir = Path(tempfile.mkdtemp(prefix=f"mtof-cycle-{cycle_no}-"))

    # ---- 1. resting check -------------------------------------------
    prior = cycles[-1] if cycles else None
    if prior and prior.get("envelopeSha256AsPublished"):
        check = {"result": "unknown", "priorCycle": prior["cycle"],
                 "expectedSha256": prior["envelopeSha256AsPublished"]}
        try:
            status, raw = fetch(ENVELOPE_URL)
            check["httpStatus"] = status
            check["fetchedSha256"] = sha256_hex(raw)
            check["result"] = "match" if check["fetchedSha256"] == check["expectedSha256"] else "CHANGED"
        except Exception as exc:
            check["result"] = "unreachable"
            check["error"] = str(exc)[:200]
        entry["restingEnvelopeCheck"] = check
    else:
        entry["restingEnvelopeCheck"] = {"result": "no-prior-cycle"}

    # ---- 2+3. build + tokenize --------------------------------------
    payload = build_payload(cycle_no, started)
    payload_name = f"heartbeat-cycle-{cycle_no:04d}.txt"
    payload_path = workdir / payload_name
    payload_path.write_bytes(payload)
    entry["payloadName"] = payload_name
    entry["payloadBytes"] = len(payload)
    entry["payloadSha256"] = sha256_hex(payload)
    envelope_path = workdir / ENVELOPE_NAME
    send_log_path = workdir / "send-log.json"
    proc = subprocess.run(
        [sys.executable, str(HERE / "sender.py"), str(payload_path),
         str(envelope_path), str(send_log_path)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        entry["grade"] = "INTERRUPTED"
        entry["detail"] = f"tokenize leg failed at origin: {proc.stderr.strip()[:200]}"
        cycles.append(entry)
        publish_log(log)
        print(json.dumps(entry, indent=2))
        return 0
    send_log = json.loads(send_log_path.read_text())
    envelope_bytes = envelope_path.read_bytes()
    entry["envelopeBytes"] = len(envelope_bytes)
    entry["envelopeSha256AsPublished"] = send_log["envelopeSha256"]

    # ---- 4. publish ---------------------------------------------------
    try:
        put_file(ENVELOPE_NAME, envelope_bytes,
                 f"mtof cycle {cycle_no}: heartbeat envelope")
        entry["publishedUtc"] = now_utc()
    except Exception as exc:
        entry["grade"] = "INTERRUPTED"
        entry["detail"] = f"publish leg failed: {str(exc)[:200]}"
        cycles.append(entry)
        publish_log(log)
        print(json.dumps(entry, indent=2))
        return 0

    # ---- 5. converge + receive ---------------------------------------
    converged = False
    fetch_error = None
    last_poll_bytes = None
    deadline = time.time() + CONVERGE_TIMEOUT_S
    while time.time() < deadline:
        try:
            status, raw = fetch(f"{ENVELOPE_URL}?c={cycle_no}")
            last_poll_bytes = raw
            try:
                served = json.loads(raw)
                if served.get("payload", {}).get("name") == payload_name:
                    converged = True
                    break
            except Exception:
                pass  # served bytes are not (yet) our envelope; keep waiting
        except Exception as exc:
            fetch_error = str(exc)[:200]
        time.sleep(CONVERGE_POLL_S)

    if not converged:
        entry["grade"] = "INTERRUPTED"
        if fetch_error and last_poll_bytes is None:
            entry["detail"] = (f"fetch leg failed: pipe did not answer over http "
                               f"({fetch_error})")
        else:
            entry["detail"] = ("publish-converge leg failed: pipe answered but never "
                               f"served cycle {cycle_no}'s envelope within "
                               f"{CONVERGE_TIMEOUT_S}s")
        cycles.append(entry)
        publish_log(log)
        print(json.dumps(entry, indent=2))
        return 0

    # Independent receiver, retried briefly against cache lag: a stale
    # envelope served to the receiver is an interruption, not tampering.
    receive_log = None
    stale = False
    r_deadline = time.time() + RECEIVER_RETRY_S
    while True:
        recv_log_path = workdir / "receive-log.json"
        if recv_log_path.exists():
            recv_log_path.unlink()
        proc = subprocess.run(
            [sys.executable, str(HERE / "receiver.py"), ENVELOPE_URL,
             str(workdir / "far-payload.bin"), str(recv_log_path)],
            capture_output=True, text=True)
        if recv_log_path.exists():
            receive_log = json.loads(recv_log_path.read_text())
            stale = (receive_log.get("payloadName") not in (None, payload_name))
            if not stale:
                break
        if time.time() >= r_deadline:
            break
        time.sleep(10)

    if receive_log is None:
        entry["grade"] = "INTERRUPTED"
        entry["detail"] = f"receive leg failed: receiver produced no log ({proc.stderr.strip()[:160]})"
        cycles.append(entry)
        publish_log(log)
        print(json.dumps(entry, indent=2))
        return 0
    if stale:
        entry["grade"] = "INTERRUPTED"
        entry["detail"] = ("fetch leg served a stale envelope to the receiver "
                           f"(got {receive_log.get('payloadName')}, expected {payload_name})")
        entry["envelopeSha256AsFetched"] = receive_log.get("envelopeSha256")
        cycles.append(entry)
        publish_log(log)
        print(json.dumps(entry, indent=2))
        return 0

    entry["fetchedUtc"] = receive_log.get("timestampUtc")
    entry["httpStatus"] = receive_log.get("httpStatus")
    entry["envelopeSha256AsFetched"] = receive_log.get("envelopeSha256")
    entry["farEndSha256"] = receive_log.get("farEndSha256")

    # ---- 6. grade ------------------------------------------------------
    tamper_reasons = []
    if entry["restingEnvelopeCheck"].get("result") == "CHANGED":
        tamper_reasons.append(
            f"resting envelope of cycle {entry['restingEnvelopeCheck']['priorCycle']} "
            "was altered at rest (fetched hash != hash recorded as published)")
    if entry["envelopeSha256AsFetched"] != entry["envelopeSha256AsPublished"]:
        tamper_reasons.append("envelope bytes as fetched differ from bytes as published")
    if receive_log.get("failure"):
        tamper_reasons.append(f"receiver verification failed: {receive_log['failure']}")
    if not receive_log.get("match"):
        tamper_reasons.append("reassembled payload hash != origin hash")

    if tamper_reasons:
        entry["grade"] = "TAMPERED"
        entry["detail"] = "; ".join(tamper_reasons)
        evidence.append((f"cycles/cycle-{cycle_no:04d}-as-sent.mtof.json",
                         envelope_bytes, f"tamper evidence: cycle {cycle_no} as-sent envelope"))
        if last_poll_bytes is not None:
            evidence.append((f"cycles/cycle-{cycle_no:04d}-as-fetched.mtof.json",
                             last_poll_bytes, f"tamper evidence: cycle {cycle_no} as-fetched envelope"))
    else:
        entry["grade"] = "PASS"
        entry["detail"] = ("envelope byte-identical in transit; payload reassembled "
                            "hash-identical at the far end over plain http")

    cycles.append(entry)
    publish_log(log, extra_files=evidence)
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
