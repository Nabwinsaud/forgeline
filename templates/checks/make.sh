
# --- Make: __DIR__ -------------------------------------------------------------
# No language marker found, but the repo has its own Makefile targets. Forgeline uses them as-is.
if has_area __AREA__; then
  pushd "__DIR__" >/dev/null
  step "make (__DIR__): __TARGETS__"
  make __TARGETS__
  popd >/dev/null
fi
