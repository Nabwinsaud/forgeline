
# --- Node / TypeScript: __DIR__ ------------------------------------------------
if has_area __AREA__; then
  pushd "__DIR__" >/dev/null
  if [ -f pnpm-lock.yaml ]; then PM="pnpm"; pnpm install --frozen-lockfile
  elif [ -f yarn.lock ]; then PM="yarn"; yarn install --frozen-lockfile
  elif [ -f bun.lockb ] || [ -f bun.lock ]; then PM="bun"; bun install --frozen-lockfile
  else PM="npm"; npm ci --no-audit --no-fund; fi
  step "node (__DIR__): typecheck · lint · test · build"
  if [ -f tsconfig.json ]; then npx --no-install tsc --noEmit; fi
  $PM run lint --if-present 2>/dev/null || $PM run lint
  if grep -q '"test"' package.json; then CI=1 $PM test; fi
  if grep -q '"build"' package.json; then $PM run build; fi
  popd >/dev/null
fi
