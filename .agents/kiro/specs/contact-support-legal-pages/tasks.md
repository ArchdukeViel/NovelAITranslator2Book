# tasks.md

# Tasks: Contact, Support, and Legal Pages

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing public frontend route structure.
  * [ ] 0.2 Inspect existing layout/footer components.
  * [ ] 0.3 Inspect public reader page layout and available chapter/novel context.
  * [ ] 0.4 Inspect existing backend public router conventions.
  * [ ] 0.5 Inspect existing config/settings pattern.
  * [ ] 0.6 Inspect existing email/notification sender support, if any.
  * [ ] 0.7 Inspect existing rate-limit or anti-abuse middleware.
  * [ ] 0.8 Inspect existing database model/migration conventions if submission persistence is needed.
  * [ ] 0.9 Inspect existing frontend/backend test patterns.

* [ ] 1. Define contact/legal configuration

  * [ ] 1.1 Add public site name config if missing. (REQ-9)
  * [ ] 1.2 Add support email config. (REQ-1, REQ-9)
  * [ ] 1.3 Add legal email config. (REQ-5, REQ-9)
  * [ ] 1.4 Add DMCA/takedown email config. (REQ-5, REQ-9)
  * [ ] 1.5 Add contact form enabled flag. (REQ-1, REQ-2, REQ-9)
  * [ ] 1.6 Add error report form enabled flag. (REQ-3, REQ-9)
  * [ ] 1.7 Add takedown form enabled flag. (REQ-5, REQ-9)
  * [ ] 1.8 Add legal placeholder mode flag if useful. (REQ-6, REQ-7)
  * [ ] 1.9 Add production config validation for required contact destinations. (REQ-9, REQ-15)
  * [ ] 1.10 Ensure public config does not expose secrets. (REQ-9, REQ-12)

* [ ] 2. Define public page route map

  * [ ] 2.1 Choose canonical support/contact path. (REQ-1)
  * [ ] 2.2 Define `/support` route. (REQ-1)
  * [ ] 2.3 Define `/report-error` route. (REQ-3)
  * [ ] 2.4 Define `/dmca` or `/takedown` route. (REQ-5)
  * [ ] 2.5 Define `/privacy` route. (REQ-6)
  * [ ] 2.6 Define `/terms` route. (REQ-7)
  * [ ] 2.7 Add redirects or aliases if both `/contact` and `/support` are supported. (REQ-1)
  * [ ] 2.8 Verify all routes are public and do not require authentication. (REQ-1, REQ-3, REQ-5, REQ-6, REQ-7)

* [ ] 3. Add static legal placeholder content

  * [ ] 3.1 Draft privacy placeholder content. (REQ-6)
  * [ ] 3.2 Include privacy sections for information collected, usage, cookies/local storage, support/error reports, retention placeholder, and contact. (REQ-6)
  * [ ] 3.3 Add privacy last-updated date. (REQ-6)
  * [ ] 3.4 Clearly mark privacy page as placeholder/draft if final legal copy is not ready. (REQ-6)
  * [ ] 3.5 Draft terms placeholder content. (REQ-7)
  * [ ] 3.6 Include terms sections for use of service, user responsibilities, content/source material disclaimer, account access, prohibited use, service availability, takedown/contact, and changes. (REQ-7)
  * [ ] 3.7 Add terms last-updated date. (REQ-7)
  * [ ] 3.8 Clearly mark terms page as placeholder/draft if final legal copy is not ready. (REQ-7)
  * [ ] 3.9 Review terms/privacy copy to avoid overpromising uptime, translation accuracy, permanent storage, or final legal completeness. (REQ-7, REQ-12)

* [ ] 4. Implement support/contact frontend page

  * [ ] 4.1 Add support/contact page component. (REQ-1)
  * [ ] 4.2 Render configured support email or fallback. (REQ-1, REQ-9)
  * [ ] 4.3 Render contact form when enabled. (REQ-1, REQ-2)
  * [ ] 4.4 Render mailto/contact fallback when form is disabled. (REQ-1, REQ-9)
  * [ ] 4.5 Add category selector. (REQ-2)
  * [ ] 4.6 Add required subject/message fields. (REQ-2)
  * [ ] 4.7 Add optional name and related URL fields. (REQ-2)
  * [ ] 4.8 Add warning not to submit passwords/tokens/secrets. (REQ-12)
  * [ ] 4.9 Add links to error report, DMCA/takedown, privacy, and terms. (REQ-1)
  * [ ] 4.10 Add success and error states. (REQ-2)

* [ ] 5. Implement error report frontend page

  * [ ] 5.1 Add error report page component. (REQ-3)
  * [ ] 5.2 Add problem type selector. (REQ-3)
  * [ ] 5.3 Add message field. (REQ-3)
  * [ ] 5.4 Add optional email field. (REQ-3)
  * [ ] 5.5 Add optional page URL field. (REQ-3)
  * [ ] 5.6 Add browser/page metadata capture only if safe and useful. (REQ-3, REQ-12)
  * [ ] 5.7 Read URL params for reader/chapter context prefill. (REQ-3, REQ-4)
  * [ ] 5.8 Add fallback contact instructions when form is disabled. (REQ-3, REQ-9)
  * [ ] 5.9 Add success and error states. (REQ-3)
  * [ ] 5.10 Add warning not to submit passwords/tokens/secrets. (REQ-12)

* [ ] 6. Add reader report issue entry point

  * [ ] 6.1 Add “Report issue” link or button to public reader page. (REQ-4)
  * [ ] 6.2 Include current page URL in report link. (REQ-4)
  * [ ] 6.3 Include safe novel/chapter context in report link or submission payload. (REQ-4)
  * [ ] 6.4 Avoid displaying private internal IDs unless already public-safe. (REQ-4, REQ-12)
  * [ ] 6.5 Validate submitted context server-side. (REQ-4, REQ-12)
  * [ ] 6.6 Add frontend test for reader report link and prefill behavior. (REQ-4, REQ-14)

* [ ] 7. Implement DMCA/takedown frontend page

  * [ ] 7.1 Add DMCA/takedown page component. (REQ-5)
  * [ ] 7.2 Render configured DMCA/legal contact email or fallback. (REQ-5, REQ-9)
  * [ ] 7.3 Add required information checklist for takedown requests. (REQ-5)
  * [ ] 7.4 Render takedown form when enabled. (REQ-5)
  * [ ] 7.5 Render mailto/legal fallback when form is disabled. (REQ-5, REQ-9)
  * [ ] 7.6 Add fields for requester name, contact email, work description, content URL/location, statements, and signature/typed name if form is enabled. (REQ-5)
  * [ ] 7.7 Add success and error states. (REQ-5)
  * [ ] 7.8 Add support/contact link. (REQ-5)

* [ ] 8. Implement privacy and terms frontend pages

  * [ ] 8.1 Add privacy page route/component. (REQ-6)
  * [ ] 8.2 Add terms page route/component. (REQ-7)
  * [ ] 8.3 Ensure both pages are public. (REQ-6, REQ-7)
  * [ ] 8.4 Add readable layout and headings. (REQ-6, REQ-7)
  * [ ] 8.5 Add contact/support link to both pages. (REQ-6, REQ-7)
  * [ ] 8.6 Add tests that pages render and contain required sections. (REQ-6, REQ-7, REQ-14)

* [ ] 9. Add global footer links

  * [ ] 9.1 Locate shared footer/layout component. (REQ-8)
  * [ ] 9.2 Add support/contact footer link. (REQ-8)
  * [ ] 9.3 Add report issue footer link. (REQ-8)
  * [ ] 9.4 Add DMCA/takedown footer link. (REQ-8)
  * [ ] 9.5 Add privacy footer link. (REQ-8)
  * [ ] 9.6 Add terms footer link. (REQ-8)
  * [ ] 9.7 Ensure public reader layout exposes these links or an equivalent accessible location. (REQ-8)
  * [ ] 9.8 Ensure error pages expose support/contact when practical. (REQ-8)
  * [ ] 9.9 Add tests for footer link presence and destinations. (REQ-8, REQ-14)

* [ ] 10. Define support submission backend contract

  * [ ] 10.1 Define support/contact submission request model. (REQ-2)
  * [ ] 10.2 Define error report submission request model. (REQ-3)
  * [ ] 10.3 Define takedown submission request model. (REQ-5)
  * [ ] 10.4 Define common success response. (REQ-2, REQ-3, REQ-5)
  * [ ] 10.5 Define validation error responses. (REQ-2, REQ-3, REQ-5, REQ-10)
  * [ ] 10.6 Define safe failure responses. (REQ-2, REQ-3, REQ-5, REQ-12)
  * [ ] 10.7 Define stable error codes for disabled forms, validation, rate limiting, and submission failures. (REQ-10, REQ-12)

* [ ] 11. Add submission persistence if chosen

  * [ ] 11.1 Create `support_submissions` table/model or equivalent if persistence is enabled. (REQ-11, REQ-13)
  * [ ] 11.2 Add fields for type, category, email, name, subject, message, related URL, novel/chapter context, status, metadata, created time, and updated time. (REQ-11, REQ-13)
  * [ ] 11.3 Add indexes for type, status, created time, and category if useful. (REQ-11)
  * [ ] 11.4 Add migration. (REQ-11)
  * [ ] 11.5 Add repository/service methods to create submissions. (REQ-11)
  * [ ] 11.6 Ensure stored submissions are not exposed publicly. (REQ-11, REQ-12)
  * [ ] 11.7 Add tests for persistence success and failure. (REQ-11, REQ-14)

* [ ] 12. Implement support submission service

  * [ ] 12.1 Add validation for required fields. (REQ-2, REQ-3, REQ-5)
  * [ ] 12.2 Add email format validation. (REQ-2, REQ-3, REQ-5)
  * [ ] 12.3 Add message length validation. (REQ-2, REQ-10)
  * [ ] 12.4 Add category/problem type validation. (REQ-2, REQ-3)
  * [ ] 12.5 Add takedown-specific field validation if takedown form is enabled. (REQ-5)
  * [ ] 12.6 Add server-side validation for related URL and novel/chapter context. (REQ-3, REQ-4, REQ-12)
  * [ ] 12.7 Persist accepted submissions if persistence is enabled. (REQ-11)
  * [ ] 12.8 Route accepted submissions to email/notification destination if enabled. (REQ-11)
  * [ ] 12.9 Return safe success/failure responses. (REQ-2, REQ-3, REQ-5, REQ-12)

* [ ] 13. Implement email or notification routing

  * [ ] 13.1 Inspect existing email sender or notification service. (REQ-11)
  * [ ] 13.2 Add support submission email template if email sending exists. (REQ-11)
  * [ ] 13.3 Route general support to support email. (REQ-11)
  * [ ] 13.4 Route error reports to support email. (REQ-11)
  * [ ] 13.5 Route DMCA/takedown submissions to DMCA/legal email. (REQ-5, REQ-11)
  * [ ] 13.6 Record routing failure if persistence succeeds but notification fails. (REQ-11)
  * [ ] 13.7 Redact secrets from email/log errors. (REQ-12)
  * [ ] 13.8 Add tests with fake email sender for routing success and failure. (REQ-11, REQ-14)

* [ ] 14. Implement public support API endpoints

  * [ ] 14.1 Add `POST /support/contact` or project-standard equivalent. (REQ-2)
  * [ ] 14.2 Add `POST /support/error-report` or project-standard equivalent. (REQ-3)
  * [ ] 14.3 Add `POST /support/takedown` or project-standard equivalent. (REQ-5)
  * [ ] 14.4 Ensure endpoints do not require authentication. (REQ-1, REQ-3, REQ-5)
  * [ ] 14.5 Apply form-enabled flags. (REQ-2, REQ-3, REQ-5, REQ-9)
  * [ ] 14.6 Return validation errors for bad input. (REQ-2, REQ-3, REQ-5, REQ-10)
  * [ ] 14.7 Return safe generic errors for internal failures. (REQ-12)
  * [ ] 14.8 Add backend API tests. (REQ-14)

* [ ] 15. Add anti-abuse controls

  * [ ] 15.1 Apply existing rate limiter to support endpoints if available. (REQ-10)
  * [ ] 15.2 Add per-IP/session rate limits if no existing limiter exists. (REQ-10)
  * [ ] 15.3 Add honeypot field support if compatible with frontend. (REQ-10)
  * [ ] 15.4 Add duplicate submission guard if practical. (REQ-10)
  * [ ] 15.5 Add maximum subject/message length limits. (REQ-10)
  * [ ] 15.6 Ensure anti-abuse rejection messages are safe. (REQ-10, REQ-12)
  * [ ] 15.7 Add tests for rate limit, honeypot, duplicate, and length validation where practical. (REQ-10, REQ-14)

* [ ] 16. Add frontend form integration

  * [ ] 16.1 Add API client method for contact submissions. (REQ-2)
  * [ ] 16.2 Add API client method for error reports. (REQ-3)
  * [ ] 16.3 Add API client method for takedown submissions. (REQ-5)
  * [ ] 16.4 Wire support/contact form to backend. (REQ-2)
  * [ ] 16.5 Wire error report form to backend. (REQ-3)
  * [ ] 16.6 Wire takedown form to backend if enabled. (REQ-5)
  * [ ] 16.7 Add client-side required field validation. (REQ-2, REQ-3, REQ-5)
  * [ ] 16.8 Add success states after submission. (REQ-2, REQ-3, REQ-5)
  * [ ] 16.9 Add safe error states for validation, rate limit, and backend failure. (REQ-10, REQ-12)
  * [ ] 16.10 Hide forms and show fallback when disabled. (REQ-9)

* [ ] 17. Security and privacy hardening

  * [ ] 17.1 Add user-facing warning not to submit passwords/tokens/secrets. (REQ-12)
  * [ ] 17.2 Sanitize or escape stored/rendered submission content. (REQ-12)
  * [ ] 17.3 Avoid logging full message bodies unless explicitly needed and safe. (REQ-12)
  * [ ] 17.4 Redact secrets in submission errors and notification errors. (REQ-12)
  * [ ] 17.5 Ensure public API errors do not expose stack traces. (REQ-12)
  * [ ] 17.6 Ensure support submissions are not publicly readable. (REQ-11, REQ-12)
  * [ ] 17.7 Validate related URLs and IDs server-side. (REQ-4, REQ-12)
  * [ ] 17.8 Add tests for unsafe input escaping and public error redaction where practical. (REQ-12, REQ-14)

* [ ] 18. Frontend test coverage

  * [ ] 18.1 Test support/contact page renders. (REQ-1, REQ-14)
  * [ ] 18.2 Test error report page renders. (REQ-3, REQ-14)
  * [ ] 18.3 Test DMCA/takedown page renders. (REQ-5, REQ-14)
  * [ ] 18.4 Test privacy page renders. (REQ-6, REQ-14)
  * [ ] 18.5 Test terms page renders. (REQ-7, REQ-14)
  * [ ] 18.6 Test footer links render and navigate correctly. (REQ-8, REQ-14)
  * [ ] 18.7 Test required field validation. (REQ-2, REQ-3, REQ-5, REQ-14)
  * [ ] 18.8 Test successful form submission state. (REQ-2, REQ-3, REQ-5, REQ-14)
  * [ ] 18.9 Test backend error state. (REQ-10, REQ-14)
  * [ ] 18.10 Test mailto fallback mode. (REQ-9, REQ-14)
  * [ ] 18.11 Test reader report prefill behavior if implemented. (REQ-4, REQ-14)

* [ ] 19. Backend test coverage

  * [ ] 19.1 Test contact submission validation. (REQ-2, REQ-14)
  * [ ] 19.2 Test error report submission validation. (REQ-3, REQ-14)
  * [ ] 19.3 Test takedown submission validation. (REQ-5, REQ-14)
  * [ ] 19.4 Test form disabled behavior. (REQ-2, REQ-3, REQ-5, REQ-9, REQ-14)
  * [ ] 19.5 Test persistence success if persistence is enabled. (REQ-11, REQ-14)
  * [ ] 19.6 Test persistence failure safe response. (REQ-11, REQ-12, REQ-14)
  * [ ] 19.7 Test email routing success if email sender exists. (REQ-11, REQ-14)
  * [ ] 19.8 Test email routing failure behavior. (REQ-11, REQ-14)
  * [ ] 19.9 Test rate limiting or abuse protection. (REQ-10, REQ-14)
  * [ ] 19.10 Test public endpoints do not require authentication. (REQ-1, REQ-3, REQ-5, REQ-14)
  * [ ] 19.11 Test safe error redaction. (REQ-12, REQ-14)

* [ ] 20. Documentation and launch copy review

  * [ ] 20.1 Document required contact configuration. (REQ-9, REQ-15)
  * [ ] 20.2 Document form-enabled versus mailto fallback modes. (REQ-9)
  * [ ] 20.3 Document support submission routing. (REQ-11)
  * [ ] 20.4 Document takedown request handling path. (REQ-5, REQ-15)
  * [ ] 20.5 Document legal placeholder status and need for final review. (REQ-6, REQ-7)
  * [ ] 20.6 Add V1 launch checklist items for support/legal pages. (REQ-15)
  * [ ] 20.7 Review public copy for broken links, placeholder warnings, and overpromising. (REQ-6, REQ-7, REQ-15)

* [ ] 21. Release verification

  * [ ] 21.1 Open support/contact page without authentication. (REQ-1, REQ-15)
  * [ ] 21.2 Open error report page without authentication. (REQ-3, REQ-15)
  * [ ] 21.3 Open DMCA/takedown page without authentication. (REQ-5, REQ-15)
  * [ ] 21.4 Open privacy page without authentication. (REQ-6, REQ-15)
  * [ ] 21.5 Open terms page without authentication. (REQ-7, REQ-15)
  * [ ] 21.6 Verify footer links appear on public pages. (REQ-8, REQ-15)
  * [ ] 21.7 Verify footer links appear or equivalent links are accessible on reader pages. (REQ-8, REQ-15)
  * [ ] 21.8 Submit test support request if forms are enabled. (REQ-2, REQ-15)
  * [ ] 21.9 Submit test error report if forms are enabled. (REQ-3, REQ-15)
  * [ ] 21.10 Submit test takedown request if takedown form is enabled. (REQ-5, REQ-15)
  * [ ] 21.11 Verify support/legal destinations receive submissions or persistence records are created. (REQ-11, REQ-15)
  * [ ] 21.12 Verify mailto fallback works when forms are disabled. (REQ-9, REQ-15)
  * [ ] 21.13 Verify required contact config exists in production/staging. (REQ-9, REQ-15)
  * [ ] 21.14 Mark `contact-support-legal-pages` launch blocker complete only after public pages, footer links, and support/takedown contact paths are verified.
