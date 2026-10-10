# Backup demo video (2 min, screen recording) — record after the Voroa deploy

Record at 1080p, no music; voice-over lines in quotes. If the live demo fails, play this.

| t | Screen | Voice-over |
|---|---|---|
| 0:00 | Web app landing page | "AuditPilot audits the business, not the spreadsheet. Every agent connects through one MCP server holding only a token." |
| 0:10 | Claude Code with the **auditor** token: call `create_sales_order` | "The auditor's agent can't even see client tools; when it tries, the server refuses and logs it." |
| 0:25 | Claude Code with the **client** token: invoice dated 31 Mar, dispatch 2 Apr; `upload_sales_register` with one edited amount | "As the client we plant a cut-off error and doctor the register." |
| 0:45 | Auditor: `reconcile_register_to_system` → `run_analytics` | "Every sale is tested, not 30. The doctored row and the cut-off error surface with plain-language reasons." |
| 1:00 | Web app → Investigation Explorer → Network View, then Timeline | "AuditGraph follows the money: here's a related customer and a circular flow, and the full paper trail of one sale." |
| 1:20 | Client `amend_record` on the LR date → auditor `check_for_changes` | "A change after testing names the field, old and new values, who did it, and the stale sample." |
| 1:35 | Partner page: confirm a finding, sign off | "Only a human partner decides and signs; the AI only proposes." |
| 1:50 | Open the workpaper xlsx + run `python scripts/verify_trail.py` | "The workpaper, memo and hash-chained trail are verifiable offline." |
