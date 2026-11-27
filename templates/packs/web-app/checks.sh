step "web-app: no unsanitized raw HTML in new code (pack: web-app)"
# Add `forgeline:allow` to a line when the HTML is sanitized (say how in a comment).
if git diff -U0 "${FACTORY_BASE:-main}...HEAD" -- . ':(exclude)*.md' | grep '^+[^+]' | grep -v 'forgeline:allow' \
   | grep -E 'dangerouslySetInnerHTML|\.innerHTML[[:space:]]*=|v-html=|\{@html |\| safe\b|mark_safe\(|template\.HTML\('; then
  echo "raw HTML insertion above. Sanitize it (and mark the line forgeline:allow) or render text instead."; exit 1
fi
