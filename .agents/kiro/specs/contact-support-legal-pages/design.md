# design.md

# Design: Contact, Support, and Legal Pages

## Overview

`contact-support-legal-pages` adds the minimum public-facing trust, support, and legal surfaces required before V1 launch.

The application should not launch publicly without a clear way for users, copyright holders, and visitors to contact operators. This spec adds contact/support pages, an error report path, DMCA/takedown contact information, privacy and terms placeholder pages, and footer links.

This is a V1 launch blocker because public users need a clear support path, rights holders need a takedown contact path, and the site needs basic legal/documentation surfaces even if final legal copy is completed later.

## Goals

* Add public contact/support page.
* Add public error report path.
* Add DMCA/takedown contact page or section.
* Add privacy policy placeholder page.
* Add terms of service placeholder page.
* Add footer links to contact, support, privacy, terms, and takedown pages.
* Add configurable operator/support contact information.
* Add backend endpoint or email-link fallback for support submissions.
* Add anti-abuse protections for public forms.
* Add tests for page rendering, form validation, and footer links.

## Non-goals

* No full help center/knowledge base.
* No full ticketing system.
* No legal advice or final lawyer-approved legal copy.
* No automated DMCA adjudication workflow.
* No public moderation queue.
* No user-to-user messaging.
* No analytics integration.
* No full notification system unless already available.

## Page structure

Recommended public pages:

```text id="cm12uu"
/contact
/support
/report-error
/dmca
/privacy
/terms
```

If the frontend prefers fewer pages, `/contact` may include support, error reporting, and takedown sections. However, footer links should still make each purpose clear.

Recommended minimum V1 structure:

```text id="nzb9wa"
/support
  General support and contact form

/report-error
  Reader/translation/chapter issue report form

/dmca
  Copyright/takedown contact instructions

/privacy
  Privacy policy placeholder

/terms
  Terms of service placeholder
```

## Configuration

Add deployment-configurable contact values.

Recommended environment/config values:

```text id="0tg75a"
PUBLIC_SITE_NAME=NovelAI Translator
PUBLIC_SUPPORT_EMAIL=support@example.com
PUBLIC_LEGAL_EMAIL=legal@example.com
PUBLIC_DMCA_EMAIL=dmca@example.com
PUBLIC_CONTACT_FORM_ENABLED=true
PUBLIC_ERROR_REPORT_FORM_ENABLED=true
PUBLIC_DMCA_CONTACT_ENABLED=true
PUBLIC_LEGAL_PLACEHOLDER_MODE=true
```

If form handling is not configured, pages should gracefully fall back to `mailto:` links.

## Contact and support page

The support page should provide:

```text id="4iv52o"
support email
general contact form if enabled
expected response-time placeholder
links to error report, DMCA/takedown, privacy, and terms
```

Recommended form fields:

```text id="8ocodt"
name optional
email required
subject required
category required
message required
related_url optional
```

Recommended categories:

```text id="ew49vi"
general
account
translation_issue
reader_issue
bug_report
copyright_or_takedown
other
```

For copyright/takedown category, the UI should route users to `/dmca` or show takedown-specific instructions.

## Error report page

The error report page gives users a way to report reader, chapter, translation, crawler, or UI problems.

Recommended path:

```text id="00zgtd"
/report-error
```

Recommended form fields:

```text id="5gikc4"
email optional
problem_type required
message required
page_url optional
novel_id optional
chapter_id optional
browser_info optional
```

Recommended problem types:

```text id="73ow0b"
broken_page
missing_chapter
wrong_chapter_order
bad_translation
formatting_issue
image_issue
login_issue
other
```

If the user clicks “Report issue” from a reader/chapter page, the frontend should prefill:

```text id="r4qo6n"
page_url
novel_id
chapter_id
chapter title if safe
```

The error report flow should not expose private internal IDs publicly unless those IDs are already part of the public API contract. If internal IDs are needed, submit them only in the request payload.

## DMCA/takedown page

The DMCA/takedown page should provide a clear contact path for copyright holders.

Recommended path:

```text id="a4kweu"
/dmca
```

The page should include:

```text id="o2g369"
designated takedown contact email or form
required information for a takedown request
statement that operators will review valid requests
link to contact/support
```

Recommended request information:

```text id="kgp9vo"
copyright holder or authorized representative name
contact email
description of copyrighted work
URL or identifying location of allegedly infringing content
statement of authorization
statement of good-faith belief
signature or typed name
```

This page can be a placeholder operational contact page for V1, but it must clearly tell rights holders how to reach the operator.

## Privacy policy placeholder

Recommended path:

```text id="62549n"
/privacy
```

The placeholder should state that the service may process basic account, usage, and support information. It should avoid claiming final legal completeness unless final copy has been reviewed.

Minimum sections:

```text id="4mep95"
Information we collect
How we use information
Cookies/local storage
Support/error reports
Data retention placeholder
Contact
Last updated date
```

Use obvious placeholder language where legal review is still required.

## Terms of service placeholder

Recommended path:

```text id="14dkzt"
/terms
```

Minimum sections:

```text id="mgj1dq"
Use of the service
User responsibilities
Content/source material disclaimer
Account access
Prohibited use
Service availability
Takedown/contact
Changes to terms
Last updated date
```

The terms page should not overpromise uptime, translation accuracy, permanent storage, or legal status of content.

## Footer links

Add footer links globally.

Recommended footer links:

```text id="8qh9cx"
Support
Report an issue
DMCA / Takedown
Privacy
Terms
```

The footer should appear on:

```text id="tbebux"
public home/catalog pages
public reader pages
login/register pages where layout supports it
error pages
```

Admin-only pages may use a different layout, but contact/legal links should remain accessible somewhere obvious.

## Backend support submission design

If forms are enabled, add backend submission endpoints.

Recommended endpoints:

```http id="rhzjwl"
POST /support/contact
POST /support/error-report
POST /support/takedown
```

Alternative:

```http id="xfy2cd"
POST /public/support/contact
POST /public/support/error-report
POST /public/support/takedown
```

Use existing API conventions.

Recommended backend service components:

```text id="aym8sp"
SupportRouter
SupportSubmissionService
SupportNotificationService
SupportAbuseGuard
```

Submission handling should:

1. Validate form input.
2. Apply rate limiting/anti-spam guard.
3. Persist submission or send email according to configured mode.
4. Return a safe success response.
5. Log safe metadata.

## Submission persistence

If the project has an operations database, persist support submissions.

Recommended table/model: `support_submissions`

Recommended fields:

```text id="9vqdyw"
id
type
category
email
name
subject
message
related_url
novel_id
chapter_id
status
metadata_json
created_at
updated_at
```

Recommended types:

```text id="p44u11"
contact
error_report
takedown
```

Recommended statuses:

```text id="azma05"
new
reviewing
resolved
closed
spam
```

If persistence is too large for V1, a mail-only mode is acceptable, but the system must still provide a reliable configured recipient path.

## Email/notification behavior

If email sending exists, support submissions should send an email to configured operator addresses.

Recommended routing:

```text id="4801af"
general support -> PUBLIC_SUPPORT_EMAIL
error reports -> PUBLIC_SUPPORT_EMAIL
DMCA/takedown -> PUBLIC_DMCA_EMAIL or PUBLIC_LEGAL_EMAIL
legal questions -> PUBLIC_LEGAL_EMAIL
```

If email sending does not exist, use `mailto:` fallback links and document that form persistence/notifications are disabled.

## Anti-abuse controls

Public support forms can be abused. V1 should include basic protections.

Recommended controls:

```text id="345pg7"
rate limit by IP/session
maximum message length
required fields
honeypot field
optional captcha if existing infrastructure supports it
reject suspicious empty/duplicate submissions
```

Do not build a full spam classifier in this spec.

## Error handling

For form submissions:

* Return validation errors for missing required fields.
* Return rate-limit errors for abuse.
* Return safe generic errors for internal failures.
* Do not expose stack traces.
* Do not expose email provider errors publicly.
* Do not reveal whether a specific account/email exists.

Recommended error codes:

```text id="v1u5sj"
support_disabled
invalid_email
missing_required_field
message_too_long
rate_limited
submission_failed
notification_failed
```

## Security and privacy

Support forms collect user-provided information. The implementation must:

```text id="k07zii"
avoid collecting passwords or secrets
warn users not to submit passwords/tokens
sanitize rendered submission content
rate-limit public endpoints
redact sensitive values in logs
avoid exposing submissions publicly
restrict admin review access if admin review UI exists
```

## Frontend design

### Support page

Features:

```text id="orohc3"
page title
short support explanation
contact form or mailto fallback
links to report error and DMCA page
success/error state
```

### Error report page

Features:

```text id="rnurl6"
problem type selector
message input
optional email input
page URL prefill
reader/chapter context prefill when launched from reader
success/error state
```

### DMCA page

Features:

```text id="u5vlqv"
takedown contact instructions
email or form
required information checklist
support/legal links
```

### Privacy and terms pages

Features:

```text id="mfrk4d"
static readable copy
last updated date
clear placeholder label if not final
contact link
```

## Admin review UI

A full support inbox is not required for V1. If submission persistence is added and an admin UI already exists, a simple admin list can be added later.

Recommended follow-up:

```text id="y51mao"
admin-support-inbox
```

## Testing strategy

Backend tests:

```text id="o5iwcg"
support submission validation
error report submission validation
takedown submission validation
rate limiting
mailto/form disabled behavior
email routing if email sender exists
persistence if support_submissions table exists
safe error handling
```

Frontend tests:

```text id="awhwrn"
pages render
footer links render
forms validate required fields
success state
error state
reader report link pre-fills context
privacy/terms pages are reachable
```

## Rollout plan

1. Add contact/legal configuration.
2. Add static privacy and terms placeholder copy.
3. Add support/contact page.
4. Add error report page.
5. Add DMCA/takedown page.
6. Add footer links.
7. Add form backend or mailto fallback.
8. Add anti-abuse controls.
9. Add tests.
10. Add launch verification checklist:

    * Support page reachable.
    * Error report path reachable.
    * DMCA/takedown contact visible.
    * Privacy page reachable.
    * Terms page reachable.
    * Footer links present.
    * Forms work or mailto fallback works.
