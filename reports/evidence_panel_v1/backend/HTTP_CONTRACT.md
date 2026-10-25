# Evidence panel HTTP extension

This adds two read-only POST routes to the existing loopback editor server.
The underlying [context adapter](../../backend_context_v1/INTERFACE.md),
[deterministic preview/explanation contract](../../copilot_contract_v1/README.md),
frozen LG model and project API remain unchanged. There is no language-model
provider, natural-language parser, action executor, optimizer or new job type.

The panel's three local assets are explicit static allowlist routes:
`/evidence-panel.mjs`, `/evidence-state.mjs` and `/evidence.css`. Modules use
`text/javascript`, the stylesheet uses `text/css`, and existing self-only
script/style CSP, `nosniff` and no-store headers remain in force. Arbitrary file
paths and traversal variants do not become routes.

## Routes

| Route | Exact request fields | Result |
|---|---|---|
| `POST /api/evidence/context` | `variant_id`, `run_id`, `component_id`, `limit` | Existing `build_context` success/error envelope. Use null `run_id` for configuration only. |
| `POST /api/evidence/request` | `operation`, `context`, `arguments` | Existing `handle_request` envelope. `context` is the **entire successful envelope** returned by the first route. |

Context selection is explicit, for example:

```json
{"variant_id":"A0","run_id":null,"component_id":"rail_p_1","limit":32}
```

The context route does not accept a project path, operation name or implicit
variant. The server supplies its working project. `limit` remains 1–256, and
unknown components are rejected. The returned schema is
`voltforge.evidence_context/1`, with a content ID, revision/run/snapshot bindings,
exact source references, units, bounded saved samples and backend coverage.

The second route permits exactly:

- `operation: "explain"`, `arguments: {}`.
- `operation: "preview_edit"`, `arguments: {"edit": <existing supported edit>}`.

No `apply_edit`, `approve`, `run`, export, thermal or optimization operation can
be executed through these routes. The existing manual inspector apply/run routes
remain separate. A successful preview has `applied: false`,
`simulation_started: false` and `predicted_effect: null`. Its
`status: "approval_required"` is an existing review label, not an executable
approval token or a new approval endpoint.

## Browser request example

This code uses the implemented shapes directly. It retrieves the server's
session token, obtains fresh configuration evidence and previews one declared
hypothetical input. It never applies the input or starts a simulation.

```javascript
const session = await fetch('/api/session').then(response => response.json());
async function postEvidence(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Voltforge-Token': session.result.token
    },
    body: JSON.stringify(body)
  });
  const envelope = await response.json();
  if (!response.ok || envelope.status !== 'ok') {
    throw new Error(envelope.error?.message || 'Evidence request failed');
  }
  return envelope;
}
const context = await postEvidence('/api/evidence/context', {
  variant_id: 'A0', run_id: null, component_id: 'rail_p_1', limit: 32
});
const explanation = await postEvidence('/api/evidence/request', {
  operation: 'explain', context, arguments: {}
});
const preview = await postEvidence('/api/evidence/request', {
  operation: 'preview_edit', context,
  arguments: {edit: {
    target: 'connection', id: 'rail_p_1', property: 'resistance',
    value: 0.0005, unit: 'ohm', classification: 'assumed',
    source: 'Hypothetical connection input; physical resistance unmeasured'
  }}
});
```

To explain a saved run, select its actual run ID and correct variant explicitly.
Do not substitute the latest global run. The success envelopes are forwarded
unchanged; the [generated context responses](../../backend_context_v1/examples)
show the full schema and exact values from their declared software fixtures.
The HTTP integration tests compare actual responses against the same public
backend operations, including saved samples and coverage.

## Consistency, limits and errors

Both routes use the existing Host/Origin/session-token checks, no-store response
headers and loopback-only binding. Requests require JSON; duplicate object keys
at any depth, nonfinite constants and excessively nested JSON are rejected.
Valid legacy editor requests retain their existing envelope and behavior.
For rejected-session POSTs, the server discards a declared body of at most 1 MiB
with a one-second read timeout before returning 403. It never parses or executes
that body. This prevents an unread request body from causing a Windows connection
reset that hides the structured rejection from the browser.

The evidence request route accepts at most 1 MiB of request bytes so a complete
context can be submitted. The context route and existing editor routes retain
their 128 KiB body limit. The context adapter's independent 512 KiB result limit
still applies; it never silently discards selected-run coverage.

| HTTP status | Envelope meaning |
|---|---|
| 200 | Operation handled. Inspect nested execution/freshness; a failed or historical simulation is still a successfully returned piece of evidence. |
| 400 | Invalid/unsupported request, ambiguous JSON, invalid pagination, unknown output, unsupported execution operation or HTTP body-size rejection. |
| 403 | Session token, Host or Origin rejected. |
| 404 | Referenced variant/resource not found. |
| 409 | Active job, external writer lock, stale/forged context or artifact integrity failure. |
| 413 | Context adapter cannot return complete evidence within its context-size bound. |

The existing server gate is held for evidence collection and explanation/preview.
An active simulation/export job produces a conflict. Manual edits and new jobs
cannot start through this server halfway through those calls. The adapters also
detect the external project writer lock and changed project-index reads.
This remains a single-user local tool, not a multi-user transactional service.

Before explaining or validating a proposal, the deterministic contract rebuilds
the entire context and compares the content. A client that fabricates a numeric
value and recomputes its hash still receives `stale_context`. Refresh after a
physics edit or changed run selection. Pure visual layout changes do not change
physics or invalidate otherwise identical evidence context.

There is one HTTP-only transport bridge for browser JSON numbers. Python emits
some numbers as `1.0`, while browser `JSON.parse` / `JSON.stringify` emits `1`.
The frozen Python copilot contract compares canonical Python JSON, so passing
browser serialization directly would incorrectly reject unchanged evidence.
The server now rebuilds authoritative context and recursively compares the
**whole submitted success envelope**, including its original `context_id`:

- Object keys, array order, strings, booleans and null must match exactly.
- An integer/float spelling difference is allowed only for exactly equal finite
  numeric values. There is no tolerance or rounding of changed measurements.
- Booleans never equal numeric zero/one. Integral magnitudes above JavaScript's
  safe integer limit, 9,007,199,254,740,991, are rejected even if both sides match.
- Any changed hash, value, field, array item or binding remains a stale-context
  error. A matching hash by itself is never sufficient.

Only after this complete comparison does the HTTP adapter substitute its freshly
rebuilt context into the original, unchanged `handle_request`, which independently
checks freshness again. Submitted values never become authoritative evidence.
This normalizes transport representation only; it does not rescale data, alter
models, change numeric precision, or weaken the frozen Python contract.

Missing requirements remain null or `requirement not configured`. Failed runs
retain their exact failure and partial record. Inherited runs remain outdated
for their new variant. Measured, fitted, assumed and simulated values keep their
existing classifications. A 200 HTTP response does not mean experimental module
acceptance; that remains **awaiting suitable measurements**.

## Verification and preservation

Run from the repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q tests/test_editor_evidence.py tests/test_editor_server.py --junitxml=tmp/evidence_panel_backend_fresh.xml
```

The new tests exercise actual loopback requests against disposable projects with
copied frozen LG reference artifacts, including a short actual solver run and a
deliberate failed run. They verify exact API values, units, requirements and
coverage; forged/stale contexts; inherited/failed semantics; no mutation during
explain/preview; busy/external-writer conflicts; gate serialization against a
manual editor edit; unavailable executor operations; session security; strict
JSON; body limits; and existing editor behavior. No raw or unused characterization
record is read. Static checks verify the three actual panel assets, MIME/CSP
headers, exact bytes and rejection of traversal/unmapped paths. Results are in
[tests.junit.xml](tests.junit.xml) and
[verification.json](verification.json).

The first static-extension rerun
exposed two intermittent Windows connection resets on early Origin rejection
(including an unchanged legacy case). Its failed receipt is retained as
[tests_static_initial.junit.xml](tests_static_initial.junit.xml). The bounded
discard fix above was then applied and the complete suite rerun successfully.
The earlier 37-test passing receipt is also retained as
[tests_before_static.junit.xml](tests_before_static.junit.xml).
The subsequent 38-test passing receipt is retained as
[tests_before_browser_bridge.junit.xml](tests_before_browser_bridge.junit.xml).
Actual browser testing then identified the integer/float serialization issue
above. The final suite adds real Node `JSON.parse` / `JSON.stringify` roundtrip
requests for explanations and previews, plus boolean/numeric substitution,
adjacent-float tampering, hash tampering and unsafe-integer rejection. Node is
needed for these development checks, not for serving the editor. The final test
count and result are recorded in the current verification receipt.

The original server bytes are retained at
[previous/scripts/run_editor.py](../previous/scripts/run_editor.py), with the
root sprint's [preservation map](../preservation_map.json). Previous receipts are
not edited to disguise the changed server; the new release verifies the old
server through that explicit mapping. No file under `src/voltforge`, frozen
model, dependency specification or previous context/copilot implementation was
modified by this extension.
