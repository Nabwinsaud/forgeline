# React

- Function components with typed props; no class components in new code.
- Follow the Rules of Hooks; `eslint-plugin-react-hooks` passes with no disables.
- Server data lives in the query cache (TanStack Query or the repo's equivalent), not in
  `useState` copies.
- Derive values during render; do not sync derived state with `useEffect`.
- `useEffect` only for real side effects that sync with something outside React; clean up
  subscriptions, timers and requests.
- Every data view handles loading, empty, error and success states explicitly.
- Disable submit while a mutation is pending; keep user input on failure.
- Show server validation errors next to the matching fields.
- Lists use stable ids as `key`, never array index for dynamic lists.
- Semantic elements: `button` for actions, `a` for navigation, `label` for every input.
- No clickable `div`/`span`; interactive elements are keyboard reachable with visible focus.
- Dialogs trap focus, close on Escape, and return focus on close.
- Images have meaningful `alt` or `alt=""` when decorative.
- No `dangerouslySetInnerHTML` with untrusted content unless sanitized.
- Only `VITE_`-prefixed env vars reach the client, and they are public: no secrets.
- Lazy-load large routes; virtualize long lists.
- Use `memo`/`useMemo`/`useCallback` only for measured problems.
- Keep components small; extract hooks for data and logic, components for markup.
- Put URL-worthy state (filters, tabs, pagination) in the URL.
