import DOMPurify from 'isomorphic-dompurify';

/**
 * Whitelist of allowed HTML tags for rich text content.
 * `p` and `br` are included for markdown paragraph/line-break rendering
 * (neither can carry XSS risk — `p` has no dangerous attributes, `br` is a void element).
 */
const ALLOWED_TAGS = ['strong', 'em', 'u', 'a', 'p', 'br'];

/**
 * Whitelist of allowed HTML attributes
 */
const ALLOWED_ATTR = ['href', 'target', 'rel'];

/**
 * Sanitizes HTML content using DOMPurify with a strict whitelist.
 * Only allows bold, italic, underline, and link formatting.
 * Uses isomorphic-dompurify which works in both browser and Node.js.
 *
 * @param dirty - The unsanitized HTML string
 * @returns Sanitized HTML string safe for rendering
 */
export function sanitizeHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    FORCE_BODY: true,
  });
}
