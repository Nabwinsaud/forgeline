---
name: qa-exploratory
description: How to validate a merged change in a deployed dev or stg environment - verify each acceptance criterion with evidence, run short exploratory charters around the change, spot regressions, use only harness test accounts, never production, and report pass or fail with repro steps. Use when running the QA stage after deploy.
---

# QA on a deployed environment

The code is merged and deployed. Unit tests and reviewers already passed it. Your job is to find
what they could not: config differences, real data shapes, integration with other services,
browser behavior, and regressions next to the change.

## Hard rules

- **Never production.** Use only the env URL in the job context (dev or stg). If the URL looks
  like production (no dev/stg marker, real customer domain), stop and return `needs_human`.
- **Only test accounts and test data** listed in the domain harness. Never create accounts with
  real emails, never use personal credentials, never pay with real cards.
- **Read-only on code.** You do not fix anything. You report.
- Do not run load tests, security exploits or destructive bulk operations on shared environments.
- Clean up data you created when the harness says how.

## 1. Confirm the deploy

Before testing, check the environment runs the merged commit:
- `GET /version` (or the domain's equivalent) shows the merge sha from the job context.
- If it does not after a reasonable wait, return `needs_human` - testing old code proves nothing.

## 2. Verify every acceptance criterion

For each AC in the spec, execute it as a user would and record evidence:

| AC | How | Evidence |
|---|---|---|
| API criterion | `curl` / HTTP client with a test token | method, path, status, relevant response fields, request id |
| UI criterion | browser automation | screenshot of the result state, URL, visible text |
| Data criterion | API read-back or admin view | ids and values observed |

```bash
curl -s -o /tmp/r.json -w '%{http_code}\n' -X POST "$ENV_URL/api/orders" \
  -H "Authorization: Bearer $QA_TOKEN" -H 'Content-Type: application/json' \
  -d '{"sku":"QA-SKU-1","quantity":0}'
# expect 422, error.code == invalid_quantity
```

A criterion passes only with evidence. "Looked fine" is not evidence.

## 3. Exploratory charters (5-10 minutes)

Pick the charters relevant to the change and spend a few minutes on each:

- **Adjacent features** - screens and endpoints that share data or components with the change.
  Does the list still load? Does the old flow still work?
- **Navigation** - back button, refresh mid-flow, deep link directly to the new page, open in a
  new tab, logout/login and return.
- **Bad input** - empty, whitespace, very long strings, unicode/emoji, negative numbers,
  duplicate submit (double click), pasted values.
- **Slow or failing network** - throttle to slow 3G; do loading states appear? Does a failed
  request show an error and keep user input?
- **Permissions** - repeat key actions as a lower-privilege test account and as a different
  tenant. Expect 403/404, not data.
- **State** - empty account vs account with lots of data; items in each status.
- **Viewport** - narrow mobile width for UI changes.
- **Console and network** - JS errors, 4xx/5xx in the network tab, CORS errors, mixed content.

## 4. Regression spotting

- Run the domain smoke suite against the env if one exists
  (`E2E_BASE_URL=$ENV_URL npx playwright test --grep @smoke`).
- Something broken near the change counts, even if no AC mentions it.
- Before blaming this change, check whether the same behavior exists on the previous deploy or
  in another env; note it either way. Pre-existing issues are reported as notes, not failures.

## 5. Report

Status:
- `pass` - every AC verified with evidence, no regression found.
- `fail` - an AC fails or a regression caused by this change is found.
- `needs_human` - env down, wrong version deployed, missing test accounts, or URL looks like prod.

Every failure needs repro steps someone else can follow:

```json
{
  "env": "stg",
  "criteria": [
    {"id": "AC1", "result": "pass", "evidence": "POST /api/orders -> 201, id=ord_9f2, req=7c1a"},
    {"id": "AC4", "result": "fail", "evidence": "quantity=0 -> 201 instead of 422, id=ord_9f3"}
  ],
  "exploratory_notes": "Checked list page, back/refresh on form, member vs admin, slow 3G.",
  "findings": [{
    "severity": "blocking",
    "title": "Zero quantity accepted on stg",
    "steps": ["Log in as qa-member@test", "Open /orders/new", "Enter SKU QA-SKU-1, qty 0", "Submit"],
    "expected": "Inline error 'Quantity must be at least 1', no order created",
    "actual": "Order ord_9f3 created with total 0",
    "evidence": "screenshot qa/ac4.png, request id 9b2e"
  }]
}
```

Be specific: account used, exact input, exact URL, what you saw, what you expected. Redact
tokens and any personal data from evidence.
