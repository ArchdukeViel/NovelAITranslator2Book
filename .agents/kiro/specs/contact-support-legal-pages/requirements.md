# requirements.md

# Requirements: Contact, Support, and Legal Pages

## Introduction

The application needs public contact, support, error reporting, DMCA/takedown, privacy, and terms pages before V1 launch. Users and rights holders need a clear way to contact operators, and the public site needs basic legal/trust links in the footer.

## Requirement 1: Public support/contact page

### User story

As a visitor or user, I want a clear support/contact page so that I can reach the site operator when I need help.

### Acceptance criteria

1. WHEN a visitor opens `/support` or `/contact` THEN the system SHALL display a public support/contact page.
2. WHEN the support page renders THEN it SHALL show a configured support contact email or support form.
3. WHEN support form handling is enabled THEN the page SHALL show a contact form.
4. WHEN support form handling is disabled THEN the page SHALL show a mailto/contact fallback.
5. WHEN the support page renders THEN it SHALL link to error reporting, DMCA/takedown, privacy, and terms pages.
6. WHEN the configured support email is missing THEN the system SHALL show a safe fallback message or fail launch readiness.
7. WHEN the support page renders THEN it SHALL not require authentication.

## Requirement 2: Support form submission

### User story

As a user, I want to submit a support message so that I can ask for help without searching for an email address.

### Acceptance criteria

1. WHEN a support form is submitted with valid required fields THEN the system SHALL accept the submission.
2. WHEN required fields are missing THEN the system SHALL return validation errors.
3. WHEN an email field is provided THEN the system SHALL validate the email format.
4. WHEN a message exceeds configured maximum length THEN the system SHALL reject the submission.
5. WHEN the submission is accepted THEN the system SHALL persist it or send it to the configured support destination.
6. WHEN the submission is accepted THEN the system SHALL return a safe success response.
7. WHEN submission handling fails THEN the system SHALL return a safe generic error.
8. WHEN a support message is logged THEN the system SHALL not log secrets, passwords, tokens, or excessive message content.
9. WHEN support form handling is disabled THEN the backend SHALL reject form submissions or the frontend SHALL not show the form.

## Requirement 3: Error report page

### User story

As a reader, I want to report page, chapter, translation, or formatting problems so that operators can fix content and reader issues.

### Acceptance criteria

1. WHEN a visitor opens `/report-error` THEN the system SHALL display a public error report page.
2. WHEN the error report page renders THEN it SHALL provide a way to describe the issue.
3. WHEN the error report form is submitted with valid required fields THEN the system SHALL accept the report.
4. WHEN required fields are missing THEN the system SHALL return validation errors.
5. WHEN the report originates from a reader/chapter page THEN the frontend SHOULD prefill related page URL and safe novel/chapter context.
6. WHEN optional browser/page metadata is included THEN it SHALL be safe and limited.
7. WHEN an error report is accepted THEN the system SHALL persist it or route it to the configured support destination.
8. WHEN an error report is submitted THEN the system SHALL not expose private internal data to the public page.
9. WHEN error report handling is disabled THEN the page SHALL show a contact fallback.

## Requirement 4: Reader error report entry point

### User story

As a reader, I want a visible report link from the reader page so that I can report problems in the exact chapter I am reading.

### Acceptance criteria

1. WHEN a public reader page renders THEN it SHOULD include a “Report issue” or equivalent link.
2. WHEN the reader report link is clicked THEN the system SHALL navigate to the error report page or open an error report form.
3. WHEN the report flow opens from a reader page THEN the system SHOULD include current page URL.
4. WHEN the report flow opens from a chapter page THEN the system SHOULD include safe novel/chapter context.
5. WHEN the report is submitted THEN the backend SHALL validate all provided context before storing or sending it.
6. WHEN public reader context includes internal IDs THEN those IDs SHALL not be displayed unless they are already public-safe.

## Requirement 5: DMCA/takedown contact page

### User story

As a copyright holder or authorized representative, I want a clear takedown contact path so that I can submit a rights-related request.

### Acceptance criteria

1. WHEN a visitor opens `/dmca` or `/takedown` THEN the system SHALL display a public takedown contact page.
2. WHEN the takedown page renders THEN it SHALL show configured DMCA/legal contact information or a takedown form.
3. WHEN the takedown page renders THEN it SHALL list the information requested for a takedown review.
4. WHEN a takedown form is enabled and submitted with valid required fields THEN the system SHALL accept the submission.
5. WHEN takedown form required fields are missing THEN the system SHALL return validation errors.
6. WHEN a takedown request is accepted THEN the system SHALL persist it or route it to the configured legal/DMCA destination.
7. WHEN legal/DMCA contact configuration is missing THEN launch readiness SHALL fail or the page SHALL show a safe operator-configured fallback.
8. WHEN the takedown page renders THEN it SHALL not require authentication.

## Requirement 6: Privacy policy placeholder page

### User story

As a visitor, I want to read the site’s privacy information so that I understand what information may be collected or used.

### Acceptance criteria

1. WHEN a visitor opens `/privacy` THEN the system SHALL display a public privacy page.
2. WHEN the privacy page renders THEN it SHALL include a last-updated date.
3. WHEN final legal copy is not available THEN the privacy page SHALL clearly indicate placeholder or draft status.
4. WHEN the privacy page renders THEN it SHALL include basic sections for information collected, use of information, cookies/local storage, support/error reports, retention placeholder, and contact.
5. WHEN the privacy page renders THEN it SHALL not require authentication.
6. WHEN the footer renders THEN it SHALL link to the privacy page.
7. WHEN the site uses support/error forms THEN the privacy page SHALL mention that submitted information may be used to respond to reports.

## Requirement 7: Terms of service placeholder page

### User story

As a visitor, I want to read basic terms so that I understand the rules and disclaimers for using the service.

### Acceptance criteria

1. WHEN a visitor opens `/terms` THEN the system SHALL display a public terms page.
2. WHEN the terms page renders THEN it SHALL include a last-updated date.
3. WHEN final legal copy is not available THEN the terms page SHALL clearly indicate placeholder or draft status.
4. WHEN the terms page renders THEN it SHALL include basic sections for use of service, user responsibilities, content/source material disclaimer, account access, prohibited use, service availability, takedown/contact, and changes to terms.
5. WHEN the terms page renders THEN it SHALL not require authentication.
6. WHEN the footer renders THEN it SHALL link to the terms page.
7. WHEN the terms page describes the service THEN it SHALL not overpromise uptime, translation accuracy, permanent storage, or legal status of third-party content.

## Requirement 8: Global footer links

### User story

As a visitor, I want support and legal links available from public pages so that I can find them easily.

### Acceptance criteria

1. WHEN public pages render THEN the footer SHALL include a support/contact link.
2. WHEN public pages render THEN the footer SHALL include a report issue link.
3. WHEN public pages render THEN the footer SHALL include a DMCA/takedown link.
4. WHEN public pages render THEN the footer SHALL include a privacy link.
5. WHEN public pages render THEN the footer SHALL include a terms link.
6. WHEN a footer link is clicked THEN it SHALL navigate to the correct public page.
7. WHEN public reader pages render THEN support/legal links SHALL be available in the footer or an equivalent accessible location.
8. WHEN an error page renders THEN support/contact links SHOULD still be available.

## Requirement 9: Contact configuration

### User story

As an operator, I want contact addresses and form behavior to be configurable so that deployments can use the correct support and legal destinations.

### Acceptance criteria

1. WHEN support email config is set THEN support pages SHALL use that value.
2. WHEN legal email config is set THEN legal pages SHALL use that value.
3. WHEN DMCA email config is set THEN takedown pages SHALL use that value.
4. WHEN contact form config is disabled THEN contact pages SHALL use email fallback.
5. WHEN error report form config is disabled THEN error report pages SHALL use email fallback.
6. WHEN takedown form config is disabled THEN takedown page SHALL use email fallback.
7. WHEN required contact config is missing in production mode THEN launch readiness SHALL fail or show a clear configuration error.
8. WHEN contact config is returned to the frontend THEN it SHALL not include secrets.

## Requirement 10: Anti-abuse protection

### User story

As an operator, I want public forms protected from abuse so that support endpoints cannot be spammed easily.

### Acceptance criteria

1. WHEN a public support/error/takedown form is submitted THEN the system SHALL apply rate limiting or equivalent abuse protection.
2. WHEN a client exceeds the configured rate limit THEN the system SHALL reject the submission.
3. WHEN a honeypot field is configured and filled THEN the system SHALL reject or silently drop the submission according to project convention.
4. WHEN duplicate submissions are detected within a short window THEN the system SHOULD reject or de-prioritize duplicates.
5. WHEN message length exceeds configured limits THEN the system SHALL reject the submission.
6. WHEN validation fails THEN the system SHALL return safe error messages.
7. WHEN abuse checks run THEN they SHALL not reveal sensitive internal rules.

## Requirement 11: Submission storage and routing

### User story

As an operator, I want submitted reports to be stored or routed so that they are not lost.

### Acceptance criteria

1. WHEN submission persistence is enabled THEN accepted submissions SHALL be stored in a durable table or store.
2. WHEN submission persistence is enabled THEN stored submissions SHALL include type, category, message, contact email when provided, related URL/context, status, and timestamps.
3. WHEN email routing is enabled THEN accepted submissions SHALL be sent to the configured support/legal destination.
4. WHEN both persistence and email routing are disabled THEN form submission SHALL not be enabled.
5. WHEN routing fails after persistence succeeds THEN the system SHALL record the routing failure for operator review.
6. WHEN persistence fails THEN the submission SHALL return a safe failure response.
7. WHEN submissions are stored THEN they SHALL not be publicly readable.
8. WHEN takedown requests are routed THEN they SHALL go to legal/DMCA contact destination, not only general support.

## Requirement 12: Security and privacy handling

### User story

As a user and operator, I want support/legal flows to avoid exposing sensitive information.

### Acceptance criteria

1. WHEN forms render THEN they SHOULD warn users not to submit passwords, tokens, or secrets.
2. WHEN submissions are accepted THEN stored/rendered content SHALL be escaped or sanitized.
3. WHEN submissions are logged THEN message content SHOULD be minimized or redacted.
4. WHEN public endpoints fail THEN they SHALL not expose stack traces.
5. WHEN email provider errors occur THEN public responses SHALL not expose provider credentials or raw internal errors.
6. WHEN support submissions include user email addresses THEN those submissions SHALL be protected from public access.
7. WHEN frontend pages display configured emails THEN they SHALL only display intended public contact emails.
8. WHEN internal IDs are submitted as context THEN they SHALL be validated server-side.

## Requirement 13: Optional admin review compatibility

### User story

As a future admin, I want support submissions to be compatible with an admin inbox later.

### Acceptance criteria

1. WHEN support submissions are persisted THEN they SHALL include a status field.
2. WHEN support submissions are persisted THEN they SHALL include a type field distinguishing contact, error report, and takedown.
3. WHEN support submissions are persisted THEN they SHALL include created and updated timestamps.
4. WHEN support submissions are persisted THEN they SHOULD include enough context to support future admin review.
5. WHEN no admin inbox is implemented in this spec THEN the absence SHALL be documented as a follow-up, not a blocker.

## Requirement 14: Test coverage

### User story

As a maintainer, I want tests for public support/legal pages so that launch-critical trust links do not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL verify support/contact page renders.
2. WHEN tests run THEN they SHALL verify error report page renders.
3. WHEN tests run THEN they SHALL verify DMCA/takedown page renders.
4. WHEN tests run THEN they SHALL verify privacy page renders.
5. WHEN tests run THEN they SHALL verify terms page renders.
6. WHEN tests run THEN they SHALL verify footer links point to the correct pages.
7. WHEN tests run THEN they SHALL verify form validation for required fields.
8. WHEN tests run THEN they SHALL verify rate-limit or anti-abuse behavior where practical.
9. WHEN tests run THEN they SHALL verify successful form submission path when forms are enabled.
10. WHEN tests run THEN they SHALL verify mailto fallback when forms are disabled.
11. WHEN tests run THEN they SHALL verify reader issue-report prefill if implemented.
12. WHEN tests run THEN they SHALL verify public pages do not require authentication.

## Requirement 15: Launch readiness

### User story

As a deployer, I want support and legal surfaces verified before V1 so that the public site has minimum operational trust paths.

### Acceptance criteria

1. WHEN V1 launch verification is performed THEN support/contact page SHALL be reachable.
2. WHEN V1 launch verification is performed THEN error report path SHALL be reachable.
3. WHEN V1 launch verification is performed THEN DMCA/takedown contact path SHALL be reachable.
4. WHEN V1 launch verification is performed THEN privacy page SHALL be reachable.
5. WHEN V1 launch verification is performed THEN terms page SHALL be reachable.
6. WHEN V1 launch verification is performed THEN footer links SHALL appear on public pages.
7. WHEN forms are enabled THEN test submissions SHALL be accepted and routed or persisted.
8. WHEN forms are disabled THEN mailto/contact fallback SHALL work.
9. WHEN required contact config is missing THEN launch SHALL be blocked or an explicit launch exception SHALL be documented.
