# tasks.md

# Tasks: Frontend Error Boundary and Empty States

## Task List

* [ ] 0. Preflight audit

  * [ ] 0.1 Inspect frontend routing framework and existing error boundary support.
  * [ ] 0.2 Inspect public reader routes and components.
  * [ ] 0.3 Inspect admin routes and dashboard/widget components.
  * [ ] 0.4 Inspect API client and error handling patterns.
  * [ ] 0.5 Inspect form components and validation handling.
  * [ ] 0.6 Inspect loading skeleton/spinner components.
  * [ ] 0.7 Inspect empty state components, if any.
  * [ ] 0.8 Inspect frontend logging/error reporting hooks.
  * [ ] 0.9 Inspect test utilities for rendering errors and failed API requests.
  * [ ] 0.10 Identify pages that can currently blank-screen.

* [ ] 1. Define shared state components

  * [ ] 1.1 Define `LoadingState`. (REQ-6)
  * [ ] 1.2 Define `EmptyState`. (REQ-7)
  * [ ] 1.3 Define `ErrorState`. (REQ-5)
  * [ ] 1.4 Define `UnavailableState`. (REQ-8, REQ-9)
  * [ ] 1.5 Define `NotFoundState`. (REQ-8, REQ-9)
  * [ ] 1.6 Define `UnauthorizedState`. (REQ-5)
  * [ ] 1.7 Define `ForbiddenState`. (REQ-5)
  * [ ] 1.8 Define `PartialErrorState`. (REQ-12)
  * [ ] 1.9 Ensure state components are accessible. (REQ-14)
  * [ ] 1.10 Add tests for state component rendering. (REQ-16)

* [ ] 2. Implement API error normalization

  * [ ] 2.1 Add `normalizeApiError()` helper. (REQ-4)
  * [ ] 2.2 Normalize network errors. (REQ-4)
  * [ ] 2.3 Normalize timeout errors. (REQ-4)
  * [ ] 2.4 Normalize `401`, `403`, `404`, `429`, validation, and `5xx` responses. (REQ-4)
  * [ ] 2.5 Preserve request ID where available. (REQ-4)
  * [ ] 2.6 Mark retryable categories. (REQ-4, REQ-11)
  * [ ] 2.7 Strip unsafe backend messages. (REQ-4, REQ-15)
  * [ ] 2.8 Add tests for every category and unsafe payload. (REQ-4, REQ-15, REQ-16)

* [ ] 3. Add safe message mapping

  * [ ] 3.1 Add safe message for network errors. (REQ-5)
  * [ ] 3.2 Add safe message for timeout errors. (REQ-5)
  * [ ] 3.3 Add safe message for unauthorized/forbidden/not-found states. (REQ-5)
  * [ ] 3.4 Add safe message for rate-limited state. (REQ-5)
  * [ ] 3.5 Add safe message for validation state. (REQ-5)
  * [ ] 3.6 Add safe message for server/unavailable/unknown states. (REQ-5)
  * [ ] 3.7 Include request ID display where appropriate. (REQ-5)
  * [ ] 3.8 Add tests for message mapping and request ID. (REQ-5, REQ-16)

* [ ] 4. Add redaction guard

  * [ ] 4.1 Redact stack traces. (REQ-15)
  * [ ] 4.2 Redact SQL/file path details. (REQ-15)
  * [ ] 4.3 Redact provider API raw errors. (REQ-15)
  * [ ] 4.4 Redact signed URLs and storage paths. (REQ-15)
  * [ ] 4.5 Redact prompts/source/translated text. (REQ-15)
  * [ ] 4.6 Redact tokens/API keys/passwords/credentials. (REQ-15)
  * [ ] 4.7 Apply redaction to UI and logging paths. (REQ-13, REQ-15)
  * [ ] 4.8 Add tests with unsafe backend error payloads. (REQ-15, REQ-16)

* [ ] 5. Add root error boundary

  * [ ] 5.1 Add `AppRootErrorBoundary` or framework-equivalent root fallback. (REQ-1)
  * [ ] 5.2 Render safe generic message. (REQ-1)
  * [ ] 5.3 Add refresh action. (REQ-1)
  * [ ] 5.4 Add return-home action where appropriate. (REQ-1)
  * [ ] 5.5 Emit safe frontend error log. (REQ-1, REQ-13)
  * [ ] 5.6 Ensure no stack traces/private data are shown. (REQ-1, REQ-15)
  * [ ] 5.7 Add tests for root boundary fallback and redaction. (REQ-1, REQ-16)

* [ ] 6. Add route-level boundaries

  * [ ] 6.1 Add public route error boundary. (REQ-2)
  * [ ] 6.2 Add admin route error boundary. (REQ-2)
  * [ ] 6.3 Add auth/settings route boundary where applicable. (REQ-2)
  * [ ] 6.4 Add safe route fallback title/description. (REQ-2)
  * [ ] 6.5 Add retry/navigation actions. (REQ-2, REQ-11)
  * [ ] 6.6 Move focus to fallback heading where practical. (REQ-2, REQ-14)
  * [ ] 6.7 Add tests for route rendering failure and focus behavior. (REQ-2, REQ-14, REQ-16)

* [ ] 7. Add section/widget boundaries

  * [ ] 7.1 Add reusable `SectionErrorBoundary`. (REQ-3)
  * [ ] 7.2 Wrap admin dashboard widgets. (REQ-3, REQ-12)
  * [ ] 7.3 Wrap optional public reader features such as annotations/settings widgets. (REQ-3, REQ-12)
  * [ ] 7.4 Wrap export freshness/summary panels. (REQ-3, REQ-12)
  * [ ] 7.5 Add compact section fallback and retry. (REQ-3)
  * [ ] 7.6 Add tests confirming parent page remains visible. (REQ-3, REQ-12, REQ-16)

* [ ] 8. Standardize loading states

  * [ ] 8.1 Replace ad-hoc full-page loading states with shared component. (REQ-6)
  * [ ] 8.2 Replace ad-hoc table/list loading states. (REQ-6)
  * [ ] 8.3 Add section/widget loading states. (REQ-6)
  * [ ] 8.4 Add pending state for action buttons. (REQ-6)
  * [ ] 8.5 Add accessible loading text/status. (REQ-6, REQ-14)
  * [ ] 8.6 Add timeout/error transition where practical. (REQ-6)
  * [ ] 8.7 Add tests for loading states. (REQ-6, REQ-16)

* [ ] 9. Standardize empty states

  * [ ] 9.1 Add public novel list empty state. (REQ-7)
  * [ ] 9.2 Add search results empty state. (REQ-7)
  * [ ] 9.3 Add activity list empty state. (REQ-7)
  * [ ] 9.4 Add export list empty state. (REQ-7)
  * [ ] 9.5 Add notification empty state. (REQ-7)
  * [ ] 9.6 Add admin metrics/analytics no-data state. (REQ-7)
  * [ ] 9.7 Add filtered-empty variants where relevant. (REQ-7)
  * [ ] 9.8 Add tests for each major empty state. (REQ-7, REQ-16)

* [ ] 10. Add public reader fallback states

  * [ ] 10.1 Add chapter loading state. (REQ-8)
  * [ ] 10.2 Add chapter not-found state. (REQ-8)
  * [ ] 10.3 Add chapter unavailable state. (REQ-8)
  * [ ] 10.4 Add degraded/fallback notice. (REQ-8, REQ-12)
  * [ ] 10.5 Ensure annotation failures do not hide chapter content. (REQ-8, REQ-12)
  * [ ] 10.6 Ensure settings load failure uses defaults. (REQ-8)
  * [ ] 10.7 Add retry for retryable reader API errors. (REQ-8, REQ-11)
  * [ ] 10.8 Add tests for public reader loading/not-found/unavailable/degraded/partial states. (REQ-8, REQ-16)

* [ ] 11. Add admin fallback states

  * [ ] 11.1 Add admin list error state. (REQ-9)
  * [ ] 11.2 Add admin detail not-found state. (REQ-9)
  * [ ] 11.3 Add admin forbidden state. (REQ-9)
  * [ ] 11.4 Add admin widget partial error states. (REQ-9, REQ-12)
  * [ ] 11.5 Add admin action failure/success states. (REQ-9)
  * [ ] 11.6 Display request ID where available. (REQ-9)
  * [ ] 11.7 Add tests for admin page fallback states. (REQ-9, REQ-16)

* [ ] 12. Improve form error states

  * [ ] 12.1 Normalize validation error response handling. (REQ-10)
  * [ ] 12.2 Render field-level errors. (REQ-10)
  * [ ] 12.3 Render form-level errors. (REQ-10)
  * [ ] 12.4 Preserve user input after recoverable errors. (REQ-10)
  * [ ] 12.5 Add pending submit state. (REQ-10)
  * [ ] 12.6 Add rate-limit form message. (REQ-10)
  * [ ] 12.7 Associate errors with fields for accessibility. (REQ-10, REQ-14)
  * [ ] 12.8 Add tests for validation, submit failure, pending, rate-limited, and success states. (REQ-10, REQ-16)

* [ ] 13. Implement retry behavior

  * [ ] 13.1 Add reusable retry action component or hook. (REQ-11)
  * [ ] 13.2 Enable retry for network errors. (REQ-11)
  * [ ] 13.3 Enable retry for timeouts. (REQ-11)
  * [ ] 13.4 Enable retry for temporary server/unavailable states where safe. (REQ-11)
  * [ ] 13.5 Show sign-in action for unauthorized state. (REQ-11)
  * [ ] 13.6 Show navigation action for not-found/forbidden states. (REQ-11)
  * [ ] 13.7 Avoid duplicate non-idempotent actions. (REQ-11)
  * [ ] 13.8 Add tests for retry/refetch and non-retryable categories. (REQ-11, REQ-16)

* [ ] 14. Add degraded/partial state patterns

  * [ ] 14.1 Add partial error UI for failed optional sections. (REQ-12)
  * [ ] 14.2 Use partial state for reader annotations. (REQ-12)
  * [ ] 14.3 Use partial state for export freshness summary. (REQ-12)
  * [ ] 14.4 Use partial state for admin dashboard widgets. (REQ-12)
  * [ ] 14.5 Add section retry where useful. (REQ-12)
  * [ ] 14.6 Add tests for partial content remains visible. (REQ-12, REQ-16)

* [ ] 15. Add frontend error logging

  * [ ] 15.1 Add safe logging adapter or no-op production adapter. (REQ-13)
  * [ ] 15.2 Log error boundary events. (REQ-13)
  * [ ] 15.3 Log unhandled promise rejections where practical. (REQ-13)
  * [ ] 15.4 Log API error categories where policy allows. (REQ-13)
  * [ ] 15.5 Include safe route/component/request/build fields. (REQ-13)
  * [ ] 15.6 Apply redaction before logging. (REQ-13, REQ-15)
  * [ ] 15.7 Ensure logging failure does not affect UI. (REQ-13)
  * [ ] 15.8 Add tests for safe logging and disabled logging. (REQ-13, REQ-16)

* [ ] 16. Accessibility pass for state components

  * [ ] 16.1 Ensure route errors move focus to heading where practical. (REQ-14)
  * [ ] 16.2 Ensure loading states have accessible text/status. (REQ-14)
  * [ ] 16.3 Ensure critical errors are announced where appropriate. (REQ-14)
  * [ ] 16.4 Ensure empty states are readable text. (REQ-14)
  * [ ] 16.5 Ensure retry buttons are keyboard accessible. (REQ-14)
  * [ ] 16.6 Ensure form errors are associated with fields. (REQ-14)
  * [ ] 16.7 Add accessibility tests for state components. (REQ-14, REQ-16)

* [ ] 17. Test coverage pass

  * [ ] 17.1 Test root error boundary. (REQ-1, REQ-16)
  * [ ] 17.2 Test route-level error boundary. (REQ-2, REQ-16)
  * [ ] 17.3 Test section/widget error boundary. (REQ-3, REQ-16)
  * [ ] 17.4 Test API error normalization. (REQ-4, REQ-16)
  * [ ] 17.5 Test safe message mapping. (REQ-5, REQ-16)
  * [ ] 17.6 Test loading states. (REQ-6, REQ-16)
  * [ ] 17.7 Test empty states. (REQ-7, REQ-16)
  * [ ] 17.8 Test public reader fallback states. (REQ-8, REQ-16)
  * [ ] 17.9 Test admin fallback states. (REQ-9, REQ-16)
  * [ ] 17.10 Test form error states. (REQ-10, REQ-16)
  * [ ] 17.11 Test retry behavior. (REQ-11, REQ-16)
  * [ ] 17.12 Test partial/degraded states. (REQ-12, REQ-16)
  * [ ] 17.13 Test frontend logging safety. (REQ-13, REQ-16)
  * [ ] 17.14 Test redaction/privacy rules. (REQ-15, REQ-16)

* [ ] 18. Documentation

  * [ ] 18.1 Document shared state components and when to use them. (REQ-6, REQ-7)
  * [ ] 18.2 Document error normalization categories. (REQ-4)
  * [ ] 18.3 Document safe message guidelines. (REQ-5)
  * [ ] 18.4 Document retry rules. (REQ-11)
  * [ ] 18.5 Document partial/degraded state pattern. (REQ-12)
  * [ ] 18.6 Document frontend logging and redaction rules. (REQ-13, REQ-15)
  * [ ] 18.7 Document manual QA scenarios for major public/admin routes. (REQ-17)

* [ ] 19. Completion verification

  * [ ] 19.1 Force a route component to throw and verify route fallback renders. (REQ-17)
  * [ ] 19.2 Force a widget to throw and verify parent page remains visible. (REQ-17)
  * [ ] 19.3 Return public reader not-found response and verify safe not-found state. (REQ-8, REQ-17)
  * [ ] 19.4 Return public reader server/unavailable response and verify retryable state. (REQ-8, REQ-11, REQ-17)
  * [ ] 19.5 Return empty list responses and verify empty states. (REQ-7, REQ-17)
  * [ ] 19.6 Return validation errors and verify form errors render while preserving input. (REQ-10, REQ-17)
  * [ ] 19.7 Return unsafe backend error payload and verify no secrets/stack traces are displayed. (REQ-15, REQ-17)
  * [ ] 19.8 Click retry for retryable request and verify request runs again. (REQ-11, REQ-17)
  * [ ] 19.9 Verify fallback states are keyboard accessible and readable by test queries. (REQ-14, REQ-17)
  * [ ] 19.10 Mark `frontend-error-boundary-and-empty-states` complete only after major public/admin routes avoid blank screens and unsafe error exposure.
