# n8n workflows (sponsor: n8n) — build guide (≈20 min total once the login arrives)

The app already emits signed events: set `N8N_WEBHOOK_URL` (+ `N8N_SECRET`) in `.env` and every `REGISTER_UPLOADED`,
`SAMPLES_SELECTED`, `EVIDENCE_RECEIVED`, `STALE_DETECTED`, `INTEGRITY_ALERT`, `RISK_ESCALATED`, `READY_FOR_REVIEW`,
`SIGNED_OFF` event is POSTed as `{id, kind, engagement_id, payload, at}` with header
`X-AuditPilot-Signature: sha256=<HMAC-SHA256(body, N8N_SECRET)>`. n8n talks back through the **MCP Client** node with the
**orchestrator** token (`orc_…` from the judge card), which may only call: `whoami`, `get_engagement_status`,
`list_evidence_requests`, `run_analytics`, `test_sample`, `check_for_changes`, `verify_integrity`,
`list_audit_items(kind=events)`. The audit never depends on n8n (`PIPELINE_MODE=inline`).

## Shared setup
1. **Credential "AuditPilot orchestrator"**: type *Bearer Auth*, token = the `orc_…` token.
2. **MCP Client node settings** (reuse in every workflow): Server Transport = *HTTP Streamable*; MCP Endpoint URL =
   `https://<voroa-host>/mcp`; Authentication = *Bearer* → the credential above; Input Mode = *JSON*.
3. **Webhook entry** (one webhook for all events is simplest): *Webhook* node, POST, path `auditpilot`, Options → *Raw
   Body* on. Copy its production URL into `N8N_WEBHOOK_URL`.
4. **Signature check**: *Crypto* node → HMAC, SHA256, secret = `N8N_SECRET`, value = `{{$binary.data}}` (raw body) →
   *IF* node: `sha256={{$json.data}}` equals `{{$('Webhook').item.json.headers['x-auditpilot-signature']}}`; false
   branch → stop. Then a *Switch* on `{{$json.body.kind}}` routes to W1–W3.

## W1 · Register uploaded → notify the auditor
Switch output `REGISTER_UPLOADED` → MCP Client: tool `get_engagement_status`, JSON `{}` → *Gmail/Telegram* message:
"Register received: {{rows}} rows · D0 differences {{risk_hits_by_detector.D0}} · next: {{next_steps[0].tool}}".

## W2 · Samples selected → evidence request to the client (+ reminders)
Switch `SAMPLES_SELECTED` → MCP Client `list_evidence_requests` `{"status": "OPEN", "limit": 100}` → *Gmail* to the
client's accounts contact with the table (sample_ref, doc_kind, about_doc_no, due_on) and the client-portal link
`https://<voroa-host>:8501` → *Wait* 5 min (demo; 1 day in real life) → MCP Client `list_evidence_requests`
`{"status": "OPEN"}` → *IF* items not empty → reminder email; after 2 reminders → email the partner.

## W3 · Evidence received → test the sample
Switch `EVIDENCE_RECEIVED` → MCP Client `list_audit_items` `{"kind": "samples", "limit": 100}` → pick the sample whose
request matches `payload.request_id` (*Code* node) → MCP Client `test_sample` `{"run_id": "…", "sample_no": n}` →
*IF* `exceptions` not empty → alert the auditor with the codes.

## W4 · Continuous monitoring (every 15 min)
*Schedule Trigger* 15 min → MCP Client `run_analytics` `{"incremental": true}` → MCP Client `check_for_changes` `{}` →
MCP Client `verify_integrity` `{}` → *IF* new hits, any stale sample, or integrity not ok → digest to the auditor;
`INTEGRITY_ALERT` / `STALE_DETECTED` / `RISK_ESCALATED` events from the webhook alert immediately.

## Demo tip
Keep **Executions** open on a second screen: each live audit step shows up as a green run (sponsor visibility).
Export the finished workflows (… → Download) into this folder as `W1.json` … `W4.json` and commit them.
