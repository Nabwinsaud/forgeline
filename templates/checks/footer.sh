
# --- Secrets -------------------------------------------------------------------
step "secrets"
if have gitleaks; then
  gitleaks detect --no-banner --redact --log-opts="${FACTORY_BASE:-main}..HEAD"
else
  echo "gitleaks not installed; skipping (recommended: brew install gitleaks)"
fi

# --- Your business checks go here ----------------------------------------------
# e.g. ./scripts/check-no-pii-in-logs.sh

printf '\ngate: all checks passed\n'
