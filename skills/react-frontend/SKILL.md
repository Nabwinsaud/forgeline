---
name: react-frontend
description: React + Vite + TypeScript patterns for factory frontend work - component and state structure, server state with a query cache, every UI state (loading, empty, error, success), forms and validation, accessibility, VITE_ env vars, and behavior-focused tests with Vitest and React Testing Library. Use when building or reviewing React UI.
---

# React frontend

Match the repo's existing component library, folder structure, data layer and styling. These
defaults apply where it is silent.

## Structure

```
src/
  features/orders/       OrdersPage.tsx, OrderForm.tsx, api.ts, hooks.ts, *.test.tsx
  components/            shared presentational components
  lib/                   http client, formatting, env
  routes.tsx
```

- Feature folders own their screens, hooks and API calls.
- Components are functions with typed props. No `any`. Prefer union types for variants.
- Keep components small: data hook at the top, early returns for states, then markup.

## State: pick the smallest home

| State | Where |
|---|---|
| Server data (lists, records) | Query cache (TanStack Query or the repo's equivalent) |
| URL-worthy (filters, page, tab) | Search params |
| Form input | Form library or local state |
| UI-only (open/closed) | `useState` in the nearest owner |
| Truly global (current user, theme) | Context, sparingly |

Do not copy server data into `useState`. Do not use `useEffect` to derive values - compute them
during render.

## Data fetching

```ts
// features/orders/hooks.ts
export function useOrders(params: { status?: string }) {
  return useQuery({
    queryKey: ["orders", params],
    queryFn: ({ signal }) => api.listOrders(params, { signal }),
  });
}

export function useCreateOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createOrder,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });
}
```

- Query keys include every input. Pass `signal` so stale requests cancel.
- Parse/validate responses at the boundary (zod or typed client) for anything critical.
- No fetching in `useEffect` when a query hook exists in the repo.

## Every UI state

Each data-driven view handles four states explicitly:

```tsx
export function OrdersPage() {
  const { data, isPending, isError, refetch } = useOrders({});
  if (isPending) return <Spinner label="Loading orders" />;
  if (isError) return <ErrorState message="Could not load orders." onRetry={refetch} />;
  if (data.items.length === 0) return <EmptyState title="No orders yet" />;
  return <OrderTable orders={data.items} />;
}
```

Also: disabled/pending state on submit buttons, permission-denied view, and partial failure for
mutations (show the error, keep user input).

## Forms

- Controlled inputs or the repo's form library (react-hook-form + zod is a good default).
- Validate on the client for UX; the server is still the authority - show server field errors
  (`details[]` from the API error body) next to the right fields.
- Every input has a visible `<label>`; errors linked via `aria-describedby`.
- Prevent double submit: disable while pending.

## Accessibility

- Use semantic elements: `button` for actions, `a` for navigation, headings in order, lists, tables.
- No click handlers on `div`s. If you must, it needs a role, tabIndex and key handling - so use a button.
- Images: meaningful `alt`, or `alt=""` for decoration.
- Dialogs: focus moves in on open, is trapped, returns on close; Esc closes.
- Announce async results (`role="status"` / `aria-live="polite"`) for toasts and inline errors.
- Color is never the only signal; check contrast.

## Environment variables

- Only `VITE_`-prefixed vars reach the client, read via `import.meta.env.VITE_API_URL`.
- Everything in the bundle is public. **No secrets, ever** - no API keys with write access,
  no tokens, no service credentials. Those stay on the server.
- Centralize env access in `lib/env.ts` with validation and types.

## Security

- No `dangerouslySetInnerHTML` with user data unless sanitized (DOMPurify).
- Validate URLs from data before using them in `href` (block `javascript:`).
- Auth tokens: prefer httpOnly cookies set by the server over localStorage.

## Performance basics

- Keys are stable ids, never array index for reorderable lists.
- Lazy-load routes (`React.lazy`) for large screens.
- Virtualize long lists (hundreds+ rows).
- Memoize (`useMemo`, `memo`) only after you see a real cost; do not sprinkle it.
- Avoid creating new objects in props of memoized children in hot paths.

## Testing (Vitest + React Testing Library)

Test what the user sees and does, not internal state or hook calls.

```tsx
it("shows server validation error for quantity", async () => {
  server.use(http.post("/api/orders", () =>
    HttpResponse.json({ error: { code: "invalid_quantity",
      details: [{ field: "quantity", issue: "must be >= 1" }] } }, { status: 422 })));
  const user = userEvent.setup();
  renderWithProviders(<OrderForm />);

  await user.type(screen.getByLabelText(/quantity/i), "0");
  await user.click(screen.getByRole("button", { name: /place order/i }));

  expect(await screen.findByText(/must be >= 1/i)).toBeInTheDocument();
});
```

- Query by role, label, text - in that order. `data-testid` is a last resort.
- `userEvent` over `fireEvent`. `findBy*` for async; no manual timeouts.
- Mock the network (MSW), not your own hooks or components.
- Cover each UI state: loading, empty, error, success.
- Commands: `npx vitest run`, `npx tsc --noEmit`, `npx eslint .`, `npm run build`.
