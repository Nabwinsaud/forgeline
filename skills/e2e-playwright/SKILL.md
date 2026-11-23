---
name: e2e-playwright
description: Writing and running Playwright end-to-end tests for factory jobs - one journey per acceptance criterion, role and label selectors, web-first assertions instead of sleeps, fixtures and test data, local stack up/down, traces and screenshots on failure, flake handling, and targeting a deployed URL through a baseURL env var. Use when adding or running e2e tests.
---

# E2E with Playwright

E2E tests prove that acceptance criteria work through the real UI and API together. They are
expensive, so write few, focused journeys - one per user-facing criterion - and leave edge cases
to unit and integration tests.

## Journeys from the spec

For each UI-facing AC, write one test named after it:

```ts
test("AC3: user with no invoices sees empty state and can start one", async ({ page }) => {
  await page.goto("/invoices");
  await expect(page.getByRole("heading", { name: "No invoices yet" })).toBeVisible();
  await page.getByRole("button", { name: "Create invoice" }).click();
  await expect(page).toHaveURL(/\/invoices\/new$/);
});
```

- Test the journey a user takes, start to observable result.
- Assert on what the user sees (text, URL, enabled state), plus the API response when the AC is
  about data.
- Do not re-test every validation rule end to end.

## Selectors

Priority:
1. `getByRole(role, { name })`
2. `getByLabel` for form fields
3. `getByText` for static content
4. `getByTestId` only when nothing accessible fits (add `data-testid` to the component)

Never CSS chains (`.btn-primary > span`), XPath, or nth-child. If a role selector cannot find an
element, the UI probably has an accessibility gap - fix the component.

## No sleeps

- Never `page.waitForTimeout`. Use web-first assertions that retry: `await expect(locator).toBeVisible()`.
- Wait for network when it matters: `await page.waitForResponse(r => r.url().includes("/api/orders") && r.ok())`.
- Actions auto-wait for actionability; do not add manual waits before `click`.

## Fixtures and test data

```ts
// e2e/fixtures.ts
export const test = base.extend<{ seededUser: User }>({
  seededUser: async ({ request }, use) => {
    const user = await createTestUser(request, { role: "member" });  // via API or seed endpoint
    await use(user);
    await deleteTestUser(request, user.id);
  },
});
```

- Each test creates its own data with unique values (`order-${crypto.randomUUID()}`); never rely
  on data from another test.
- Create data through the API or a seed script, not by clicking through setup screens.
- Log in once per worker with `storageState` and reuse it.
- Use only test accounts defined by the domain harness. Never real user credentials.

## Config

```ts
// playwright.config.ts
export default defineConfig({
  testDir: "e2e",
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true,
  },
});
```

## Local stack

1. Start dependencies the domain harness defines (e.g. `docker compose up -d db api`).
2. Apply migrations and seed test data.
3. Run `npx playwright test` (or a single file / `-g "AC3"` while iterating).
4. Tear down: `docker compose down -v` so the next run is clean.

Always tear down, even after failures. Do not leave containers or ports bound in the worktree.

## Deployed environments

QA stages run the same suite against dev/stg:

```bash
E2E_BASE_URL=https://dev.example.internal npx playwright test --grep @smoke
```

- Only dev/stg URLs from the job context. **Never production.**
- Tests that mutate data must be safe there: unique names, cleanup, test accounts only.
- Tag the critical subset `@smoke` for quick post-deploy runs.

## Failures and artifacts

- On failure, open the trace (`npx playwright show-trace test-results/.../trace.zip`) before
  changing anything. It shows DOM, network and console at each step.
- Report failing test name, assertion message, and artifact paths in the result.
- Check the browser console and failed network requests - many "UI" failures are API 500s.

## Flakes

A test that fails and then passes on retry is a bug - in the test or in the app.

1. Reproduce: `npx playwright test e2e/orders.spec.ts --repeat-each=20`.
2. Common causes: shared data between tests, asserting before data loads, animations, time
   zones, ordering assumptions in lists, racing a debounce.
3. Fix the cause. If it is an app race condition, that is a real finding - report it.
4. Never "fix" a flake with a sleep, a longer timeout, or by deleting the assertion.
5. Quarantining (`test.fixme`) requires a reason and a follow-up note; never quarantine a test
   that covers the current job's criteria.

## Checklist

- [ ] One test per UI-facing AC, named with the AC id.
- [ ] Role/label selectors; no CSS/XPath; no sleeps.
- [ ] Tests isolated with their own data and cleanup.
- [ ] Passes locally 3 runs in a row (`--repeat-each=3`).
- [ ] baseURL from env; works against a deployed dev URL.
- [ ] Stack torn down after the run.
