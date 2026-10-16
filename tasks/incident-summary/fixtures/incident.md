# Incident 2026-09-14: checkout errors

- 13:02 UTC: alerts fire, checkout API returns 502 for about 60% of requests.
- 13:10: on-call finds the TLS certificate for payments-gw.internal expired at 13:00.
- 13:31: new certificate issued and deployed; errors drop.
- 13:49: error rate back to normal. Total customer impact: 47 minutes.
- About 3,100 checkout attempts failed. No payments were double-charged.
- Root cause: the certificate was issued manually in 2025 and was not in the auto-renewal system.
- Follow-ups agreed: move payments-gw cert to auto-renewal (owner: Priya, due 2026-09-30);
  add an alert 14 days before any certificate expires (owner: Tom, due 2026-10-07).
