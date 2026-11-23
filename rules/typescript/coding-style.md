# TypeScript coding style

- `strict: true`. `tsc --noEmit`, ESLint and Prettier pass with the repo's config.
- No `any`. Use `unknown` at boundaries and narrow it. No `@ts-ignore`; `@ts-expect-error` only
  with a reason.
- No non-null assertions (`!`) to silence the compiler; handle the `undefined` case.
- Type function parameters and exported return types explicitly.
- Prefer `type` unions and discriminated unions for variants over boolean flag soup.
- Prefer `const`; never `var`. Avoid mutation of shared objects and arrays.
- Use `===`; no implicit coercion tricks.
- Validate external data (API responses, env, storage, URL params) with a schema (e.g. zod)
  before trusting its type.
- `async`/`await` over raw promise chains; every promise is awaited, returned, or explicitly
  handled. No floating promises.
- Throw `Error` subclasses, never strings. Do not swallow errors in empty `catch` blocks.
- Named exports over default exports unless the framework requires a default.
- Imports use the repo's path aliases; no deep relative chains like `../../../../`.
- Keep modules focused; no `utils.ts` dumping ground.
- Use the repo's package manager and lockfile; do not mix npm, pnpm and yarn.
- No `console.log` left in committed code; use the repo's logger.
- Dates: use the repo's date library or `Intl`; store and send UTC ISO strings.
- Money: integer minor units or a decimal library, never floating point arithmetic.
