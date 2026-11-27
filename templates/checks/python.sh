
# --- Python: __DIR__ -----------------------------------------------------------
if has_area __AREA__; then
  pushd "__DIR__" >/dev/null
  step "python (__DIR__): lint · types · test"
  if have uv && [ -f uv.lock ]; then RUN="uv run"; uv sync --frozen; else RUN=""; fi
  if have ruff || [ -n "$RUN" ]; then $RUN ruff check . && $RUN ruff format --check .; fi
  if [ -f mypy.ini ] || grep -qs '\[tool.mypy\]' pyproject.toml; then $RUN mypy .; fi
  rc=0; $RUN pytest -q || rc=$?; [ "$rc" -eq 0 ] || [ "$rc" -eq 5 ] || exit "$rc"  # 5 = no tests yet
  if have pip-audit; then step "python: pip-audit"; pip-audit || true; fi
  popd >/dev/null
fi
