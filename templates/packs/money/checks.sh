step "money: no floating point for amounts in new code (pack: money)"
# Only lines this branch adds are checked. Add `forgeline:allow` to a line to accept it on purpose.
if git diff -U0 "${FACTORY_BASE:-main}...HEAD" -- . ':(exclude)*.md' ':(exclude)*.lock' \
   | grep '^+[^+]' | grep -v 'forgeline:allow' \
   | grep -iE '(amount|price|balance|money|total|cost|fee|tax|refund|payout|salary|wage)' \
   | grep -E '\b(float|float32|float64|double|Double|Float|parseFloat|toFixed|real)\b'; then
  echo "money looks like floating point above. Use integer minor units or an exact decimal type."; exit 1
fi
