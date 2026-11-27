step "auth: TLS verification stays on, no obvious hardcoded secrets in new code (pack: auth)"
added="$(git diff -U0 "${FACTORY_BASE:-main}...HEAD" -- . ':(exclude)*.md' | grep '^+[^+]' | grep -v 'forgeline:allow' || true)"
if printf '%s\n' "$added" | grep -E 'InsecureSkipVerify:[[:space:]]*true|verify[[:space:]]*=[[:space:]]*False|rejectUnauthorized:[[:space:]]*false|NODE_TLS_REJECT_UNAUTHORIZED|CURLOPT_SSL_VERIFYPEER,[[:space:]]*(0|false)'; then
  echo "TLS verification is disabled above. Fix the certificate instead."; exit 1
fi
if printf '%s\n' "$added" | grep -iE '(password|passwd|secret|api_?key|token)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"' ]{8,}["'"'"']'; then
  echo "looks like a hardcoded secret above. Read it from the environment or a secret store."; exit 1
fi
