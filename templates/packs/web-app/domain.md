### Web app (pack: web-app)

- Every screen that loads data handles four states: loading, empty, error (with a way to retry), and success.
- Forms validate on the client for speed and on the server for truth. Errors appear next to the field, in plain words.
- Never insert raw HTML from users or APIs (`innerHTML`, `dangerouslySetInnerHTML`, `v-html`) unless it's sanitized first.
- Accessible by default: real buttons and links, labels on every input, alt text on meaningful images, visible focus, works with the keyboard alone, color isn't the only signal.
- Works on a phone-width screen (360px) without horizontal scrolling.
- Destructive actions (delete, cancel, pay) ask for confirmation or can be undone.
- User-facing text uses the product's words from the glossary, not internal names.
