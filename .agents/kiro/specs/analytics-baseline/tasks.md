# tasks.md

# Tasks: Analytics Baseline

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing metrics/logging system to avoid mixing product analytics with operational metrics.
  * [ ] 0.2 Inspect public reader routes and frontend components.
  * [ ] 0.3 Inspect public novel/chapter API response shape.
  * [ ] 0.4 Inspect search routes and frontend search components.
  * [ ] 0.5 Inspect export request/download routes.
  * [ ] 0.6 Inspect glossary annotation frontend events if implemented.
  * [ ] 0.7 Inspect notification frontend/server actions if implemented.
  * [ ] 0.8 Inspect admin auth/router/frontend patterns.
  * [ ] 0.9 Inspect maintenance cron cleanup hooks.
  * [ ] 0.10 Inspect test conventions for backend APIs and frontend tracking.

* [ ] 1. Define analytics policy and event allowlist

  * [ ] 1.1 Define analytics goals and non-goals in project docs. (REQ-13)
  * [ ] 1.2 Define allowed event names. (REQ-2)
  * [ ] 1.3 Define required baseline events. (REQ-2)
  * [ ] 1.4 Define optional feature events. (REQ-7, REQ-8)
  * [ ] 1.5 Define metadata schema per event. (REQ-2)
  * [ ] 1.6 Define forbidden fields. (REQ-13)
  * [ ] 1.7 Define retention policy. (REQ-14)
  * [ ] 1.8 Define analytics disabled behavior. (REQ-15)

* [ ] 2. Add analytics configuration

  * [ ] 2.1 Add `ANALYTICS_ENABLED`. (REQ-15)
  * [ ] 2.2 Add `ANALYTICS_PUBLIC_INGESTION_ENABLED`. (REQ-9, REQ-15)
  * [ ] 2.3 Add analytics retention days. (REQ-14)
  * [ ] 2.4 Add anonymous ID/session rotation settings if needed. (REQ-13)
  * [ ] 2.5 Add raw query storage flag defaulting to false. (REQ-5, REQ-13)
  * [ ] 2.6 Add IP storage flag defaulting to false. (REQ-13)
  * [ ] 2.7 Add ingestion max events/body size/rate-limit config. (REQ-9)
  * [ ] 2.8 Validate analytics config. (REQ-15)

* [ ] 3. Add analytics event model

  * [ ] 3.1 Create `analytics_events` table/model. (REQ-1)
  * [ ] 3.2 Add event name field. (REQ-1)
  * [ ] 3.3 Add event timestamp. (REQ-1)
  * [ ] 3.4 Add actor type. (REQ-1)
  * [ ] 3.5 Add hashed actor/session/anonymous identifiers where needed. (REQ-1, REQ-13)
  * [ ] 3.6 Add safe novel/chapter/source references. (REQ-1)
  * [ ] 3.7 Add route template. (REQ-1)
  * [ ] 3.8 Add safe device category/locale fields if needed. (REQ-1)
  * [ ] 3.9 Add sanitized metadata JSON. (REQ-1, REQ-13)
  * [ ] 3.10 Add indexes for event name, event time, novel ID, chapter ID, and source references. (REQ-11)
  * [ ] 3.11 Add migration tests or migration verification. (REQ-17)

* [ ] 4. Implement analytics sanitizer

  * [ ] 4.1 Validate allowed event names. (REQ-2)
  * [ ] 4.2 Drop or reject unsupported metadata keys. (REQ-2)
  * [ ] 4.3 Enforce max metadata size. (REQ-2, REQ-9)
  * [ ] 4.4 Strip raw source text. (REQ-13)
  * [ ] 4.5 Strip raw translated text. (REQ-13)
  * [ ] 4.6 Strip raw prompts. (REQ-13)
  * [ ] 4.7 Strip glossary definitions and terms for annotation analytics. (REQ-7, REQ-13)
  * [ ] 4.8 Strip notification body text. (REQ-8, REQ-13)
  * [ ] 4.9 Strip signed URLs, credentials, tokens, and API keys. (REQ-13)
  * [ ] 4.10 Strip raw query text when raw query storage is disabled. (REQ-5, REQ-13)
  * [ ] 4.11 Add sanitizer tests for allowed, unknown, oversized, and forbidden fields. (REQ-2, REQ-13, REQ-17)

* [ ] 5. Implement analytics recorder service

  * [ ] 5.1 Add `AnalyticsRecorder.record_event()`. (REQ-1)
  * [ ] 5.2 Add `record_many()` for batched events. (REQ-9)
  * [ ] 5.3 Apply enabled/disabled config. (REQ-15)
  * [ ] 5.4 Apply sanitizer before persistence. (REQ-2, REQ-13)
  * [ ] 5.5 Hash actor/session IDs where applicable. (REQ-13)
  * [ ] 5.6 Persist sanitized events. (REQ-1)
  * [ ] 5.7 Add failure isolation around persistence. (REQ-16)
  * [ ] 5.8 Add tests for record, batch record, disabled mode, sanitizer integration, and failure isolation. (REQ-1, REQ-15, REQ-16, REQ-17)

* [ ] 6. Add analytics ingestion endpoint

  * [ ] 6.1 Add `POST /analytics/events`. (REQ-9)
  * [ ] 6.2 Respect public ingestion enabled config. (REQ-9, REQ-15)
  * [ ] 6.3 Validate request body shape. (REQ-9)
  * [ ] 6.4 Enforce max events per request. (REQ-9)
  * [ ] 6.5 Enforce max body size where supported. (REQ-9)
  * [ ] 6.6 Apply rate limiting. (REQ-9)
  * [ ] 6.7 Pass events to recorder service. (REQ-9)
  * [ ] 6.8 Return safe success/validation responses. (REQ-9)
  * [ ] 6.9 Add API tests for valid batch, invalid event, oversized batch, disabled ingestion, rate limit, and unsafe metadata. (REQ-9, REQ-17)

* [ ] 7. Add frontend analytics client

  * [ ] 7.1 Add small analytics client module. (REQ-9)
  * [ ] 7.2 Add `track(eventName, payload)`. (REQ-1)
  * [ ] 7.3 Add `trackPageView(routeTemplate, metadata)`. (REQ-3)
  * [ ] 7.4 Add batching/debounce where practical. (REQ-9)
  * [ ] 7.5 Make client no-op when analytics disabled. (REQ-15)
  * [ ] 7.6 Handle network failures silently or with development-only warning. (REQ-16)
  * [ ] 7.7 Avoid sending raw URLs/query strings. (REQ-13)
  * [ ] 7.8 Add frontend tests for tracking, disabled mode, failure handling, and unsafe payload omission. (REQ-13, REQ-15, REQ-16, REQ-17)

* [ ] 8. Track public novel and chapter views

  * [ ] 8.1 Add `public_novel.view` tracking on public novel page. (REQ-3)
  * [ ] 8.2 Add `public_chapter.view` tracking on public chapter page. (REQ-3)
  * [ ] 8.3 Include safe novel/chapter IDs where available. (REQ-3)
  * [ ] 8.4 Include route template, not raw URL. (REQ-3, REQ-13)
  * [ ] 8.5 Avoid sending chapter text, selected text, or query strings. (REQ-3, REQ-13)
  * [ ] 8.6 Add tests for novel view and chapter view tracking payloads. (REQ-3, REQ-17)

* [ ] 9. Track coarse reader engagement

  * [ ] 9.1 Track next chapter action where UI exists. (REQ-4)
  * [ ] 9.2 Track previous chapter action where UI exists. (REQ-4)
  * [ ] 9.3 Track progress milestones only if needed. (REQ-4)
  * [ ] 9.4 Use coarse milestones such as 25/50/75/100. (REQ-4)
  * [ ] 9.5 Avoid raw scroll stream and selected text. (REQ-4, REQ-13)
  * [ ] 9.6 Add tests for engagement payload safety. (REQ-4, REQ-17)

* [ ] 10. Track search analytics

  * [ ] 10.1 Track `search.performed`. (REQ-5)
  * [ ] 10.2 Include safe search scope. (REQ-5)
  * [ ] 10.3 Include result count bucket. (REQ-5)
  * [ ] 10.4 Include filter count and sort key if useful. (REQ-5)
  * [ ] 10.5 Omit raw query text by default. (REQ-5, REQ-13)
  * [ ] 10.6 Respect raw query storage config if ever enabled. (REQ-5)
  * [ ] 10.7 Add tests verifying raw query is not stored/sent by default. (REQ-5, REQ-13, REQ-17)

* [ ] 11. Track export analytics

  * [ ] 11.1 Record `export.requested` server-side when export is requested. (REQ-6, REQ-10)
  * [ ] 11.2 Record `export.downloaded` server-side when artifact is downloaded. (REQ-6, REQ-10)
  * [ ] 11.3 Record `export.failed` where useful and safe. (REQ-6)
  * [ ] 11.4 Include safe format/status/freshness metadata. (REQ-6)
  * [ ] 11.5 Omit raw artifact path, signed URL, and storage key. (REQ-6, REQ-13)
  * [ ] 11.6 Add tests for request, download, failure, and unsafe field omission. (REQ-6, REQ-10, REQ-17)

* [ ] 12. Track glossary annotation interaction analytics

  * [ ] 12.1 Track `glossary_annotation.opened` if annotation rendering exists. (REQ-7)
  * [ ] 12.2 Include safe match type or count bucket only. (REQ-7)
  * [ ] 12.3 Omit source term. (REQ-7, REQ-13)
  * [ ] 12.4 Omit display term. (REQ-7, REQ-13)
  * [ ] 12.5 Omit definition. (REQ-7, REQ-13)
  * [ ] 12.6 Add tests verifying terms/definitions are not sent or stored. (REQ-7, REQ-13, REQ-17)

* [ ] 13. Track notification interaction analytics

  * [ ] 13.1 Track `notification.opened` if notification system exists. (REQ-8)
  * [ ] 13.2 Track `notification.action_clicked` if notification actions exist. (REQ-8)
  * [ ] 13.3 Include safe event type/severity/channel. (REQ-8)
  * [ ] 13.4 Omit notification title/body content. (REQ-8, REQ-13)
  * [ ] 13.5 Add tests verifying notification body is not stored. (REQ-8, REQ-13, REQ-17)

* [ ] 14. Implement analytics summary service

  * [ ] 14.1 Aggregate public novel views. (REQ-11)
  * [ ] 14.2 Aggregate public chapter views. (REQ-11)
  * [ ] 14.3 Aggregate search counts. (REQ-11)
  * [ ] 14.4 Aggregate export requests/downloads. (REQ-11)
  * [ ] 14.5 Aggregate glossary annotation opens if implemented. (REQ-11)
  * [ ] 14.6 Aggregate notification interactions if implemented. (REQ-11)
  * [ ] 14.7 Aggregate top novels by safe ID/title if allowed. (REQ-11)
  * [ ] 14.8 Support summary windows such as 24h, 7d, 30d. (REQ-11)
  * [ ] 14.9 Return partial groups safely if some aggregation fails. (REQ-11, REQ-16)
  * [ ] 14.10 Add tests for summary aggregation and partial failure. (REQ-11, REQ-17)

* [ ] 15. Add admin analytics API

  * [ ] 15.1 Add `GET /admin/analytics/summary`. (REQ-11)
  * [ ] 15.2 Protect endpoint with admin auth. (REQ-11)
  * [ ] 15.3 Validate window query param. (REQ-11)
  * [ ] 15.4 Return generated timestamp and window. (REQ-11)
  * [ ] 15.5 Return aggregate counts. (REQ-11)
  * [ ] 15.6 Avoid raw event stream by default. (REQ-11, REQ-13)
  * [ ] 15.7 Add tests for admin, non-admin, unauthenticated, valid window, invalid window, and response shape. (REQ-11, REQ-17)

* [ ] 16. Add optional admin analytics dashboard

  * [ ] 16.1 Add `/admin/analytics` route if dashboard is in scope. (REQ-12)
  * [ ] 16.2 Add admin route guard. (REQ-12)
  * [ ] 16.3 Add analytics API client. (REQ-12)
  * [ ] 16.4 Render novel/chapter view totals. (REQ-12)
  * [ ] 16.5 Render search totals. (REQ-12)
  * [ ] 16.6 Render export request/download totals. (REQ-12)
  * [ ] 16.7 Render top novels if available. (REQ-12)
  * [ ] 16.8 Render feature usage if available. (REQ-12)
  * [ ] 16.9 Add loading/empty/error states. (REQ-12)
  * [ ] 16.10 Add frontend tests for admin dashboard behavior. (REQ-12, REQ-17)

* [ ] 17. Add retention cleanup hook

  * [ ] 17.1 Add analytics cleanup repository method. (REQ-14)
  * [ ] 17.2 Delete events older than retention. (REQ-14)
  * [ ] 17.3 Support dry-run cleanup if maintenance cron supports it. (REQ-14)
  * [ ] 17.4 Integrate with `maintenance-cron`. (REQ-14)
  * [ ] 17.5 Ensure cleanup does not delete core app records. (REQ-14)
  * [ ] 17.6 Add tests for cleanup eligibility, dry-run, and preservation of app data. (REQ-14, REQ-17)

* [ ] 18. Add privacy and security review tests

  * [ ] 18.1 Test no full source text is stored. (REQ-13, REQ-17)
  * [ ] 18.2 Test no full translated text is stored. (REQ-13, REQ-17)
  * [ ] 18.3 Test no prompts are stored. (REQ-13, REQ-17)
  * [ ] 18.4 Test no glossary definitions are stored. (REQ-13, REQ-17)
  * [ ] 18.5 Test no notification bodies are stored. (REQ-13, REQ-17)
  * [ ] 18.6 Test no signed URLs/credentials/tokens are stored. (REQ-13, REQ-17)
  * [ ] 18.7 Test admin summary does not expose raw per-user clickstream. (REQ-11, REQ-13, REQ-17)
  * [ ] 18.8 Test public ingestion cannot store arbitrary metadata. (REQ-9, REQ-13, REQ-17)

* [ ] 19. Add failure isolation tests

  * [ ] 19.1 Test analytics failure during reader view does not break reader. (REQ-16)
  * [ ] 19.2 Test analytics failure during search does not break search. (REQ-16)
  * [ ] 19.3 Test analytics failure during export request does not break export. (REQ-16)
  * [ ] 19.4 Test analytics failure during notification action does not break notification behavior. (REQ-16)
  * [ ] 19.5 Test admin summary partial failure returns safe response. (REQ-16)
  * [ ] 19.6 Test analytics disabled mode stores no events. (REQ-15, REQ-16)

* [ ] 20. Documentation

  * [ ] 20.1 Document analytics purpose and non-goals. (REQ-13)
  * [ ] 20.2 Document allowed event names. (REQ-2)
  * [ ] 20.3 Document event metadata schemas. (REQ-2)
  * [ ] 20.4 Document forbidden fields and privacy rules. (REQ-13)
  * [ ] 20.5 Document ingestion endpoint. (REQ-9)
  * [ ] 20.6 Document admin summary endpoint. (REQ-11)
  * [ ] 20.7 Document retention cleanup. (REQ-14)
  * [ ] 20.8 Document disabling analytics. (REQ-15)

* [ ] 21. Completion verification

  * [ ] 21.1 View a public novel and verify safe event is stored. (REQ-3, REQ-18)
  * [ ] 21.2 View a public chapter and verify safe event is stored. (REQ-3, REQ-18)
  * [ ] 21.3 Perform search and verify safe event is stored without raw query. (REQ-5, REQ-18)
  * [ ] 21.4 Request an export and verify safe export event is stored. (REQ-6, REQ-18)
  * [ ] 21.5 Download an export and verify safe download event is stored. (REQ-6, REQ-18)
  * [ ] 21.6 Open admin summary as admin and verify aggregate counts. (REQ-11, REQ-18)
  * [ ] 21.7 Try admin summary as non-admin and verify access blocked. (REQ-11, REQ-18)
  * [ ] 21.8 Inspect event rows and verify no private content, prompts, definitions, signed URLs, or secrets. (REQ-13, REQ-18)
  * [ ] 21.9 Disable analytics and verify no new events are stored while app behavior continues. (REQ-15, REQ-18)
  * [ ] 21.10 Mark `analytics-baseline` complete only after useful aggregate usage data is recorded safely.
