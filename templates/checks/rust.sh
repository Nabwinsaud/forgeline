
# --- Rust: __DIR__ -------------------------------------------------------------
if has_area __AREA__; then
  pushd "__DIR__" >/dev/null
  step "rust (__DIR__): fmt · clippy · test"
  cargo fmt --all -- --check
  if cargo clippy --version >/dev/null 2>&1; then cargo clippy --all-targets -- -D warnings; fi
  cargo test --all
  popd >/dev/null
fi
