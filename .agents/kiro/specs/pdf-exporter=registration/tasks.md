# tasks.md

# Tasks: PDF Exporter Registration

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Locate `export_pdf()` implementation.
  * [ ] 0.2 Locate exporter registry implementation.
  * [ ] 0.3 Locate all built-in exporter classes/modules.
  * [ ] 0.4 Locate PDF exporter implementation, if it exists.
  * [ ] 0.5 Locate supported export format discovery code.
  * [ ] 0.6 Locate export API endpoint handling `format`.
  * [ ] 0.7 Locate export manifest creation code.
  * [ ] 0.8 Inspect optional PDF dependency handling.
  * [ ] 0.9 Inspect existing export tests and snapshots.
  * [ ] 0.10 Reproduce or identify the exact `KeyError` path. (REQ-13)

* [ ] 1. Define canonical PDF format metadata

  * [ ] 1.1 Define canonical format key `pdf`. (REQ-4)
  * [ ] 1.2 Define PDF MIME type `application/pdf`. (REQ-8)
  * [ ] 1.3 Define PDF file extension `.pdf`. (REQ-8)
  * [ ] 1.4 Define PDF display label. (REQ-6)
  * [ ] 1.5 Define supported PDF aliases if the export system supports aliases. (REQ-4)
  * [ ] 1.6 Ensure manifest format value uses `pdf`. (REQ-8)

* [ ] 2. Fix PDF exporter registration

  * [ ] 2.1 Add or fix registration for PDF exporter under `pdf`. (REQ-1)
  * [ ] 2.2 Ensure PDF exporter module is imported during export subsystem initialization. (REQ-1)
  * [ ] 2.3 Avoid relying on API route imports for registration. (REQ-1)
  * [ ] 2.4 Avoid import cycles with other exporters. (REQ-10)
  * [ ] 2.5 Ensure existing exporters remain registered. (REQ-10)
  * [ ] 2.6 Add unit test that registry lookup for `pdf` succeeds when enabled. (REQ-1, REQ-12)

* [ ] 3. Add safe exporter lookup

  * [ ] 3.1 Replace raw dictionary lookup with safe registry lookup if needed. (REQ-2)
  * [ ] 3.2 Return structured `unsupported_export_format` for unknown formats. (REQ-2)
  * [ ] 3.3 Return structured `exporter_unavailable` for known but unavailable formats. (REQ-2)
  * [ ] 3.4 Ensure raw `KeyError` does not escape service boundaries. (REQ-2)
  * [ ] 3.5 Ensure safe errors do not include stack traces or internal paths. (REQ-2, REQ-11)
  * [ ] 3.6 Add tests for unknown format and missing exporter behavior. (REQ-2, REQ-12)

* [ ] 4. Update `export_pdf()`

  * [ ] 4.1 Make `export_pdf()` use canonical format `pdf`. (REQ-3)
  * [ ] 4.2 Route `export_pdf()` through the standard export service path where practical. (REQ-3)
  * [ ] 4.3 Preserve existing input validation behavior. (REQ-3)
  * [ ] 4.4 Convert missing exporter state to controlled error. (REQ-3)
  * [ ] 4.5 Convert PDF render failures to controlled export failure. (REQ-3)
  * [ ] 4.6 Add regression test proving `export_pdf()` does not raise `KeyError`. (REQ-3, REQ-12)
  * [ ] 4.7 Add test proving `export_pdf()` invokes PDF exporter. (REQ-3, REQ-12)

* [ ] 5. Add format normalization

  * [ ] 5.1 Inspect existing format normalization behavior. (REQ-4)
  * [ ] 5.2 Normalize `PDF` to `pdf` if case-insensitive formats are supported. (REQ-4)
  * [ ] 5.3 Normalize `.pdf` to `pdf` if extension aliases are supported. (REQ-4)
  * [ ] 5.4 Normalize `application/pdf` to `pdf` if MIME aliases are supported. (REQ-4)
  * [ ] 5.5 Return structured unsupported-format error for unsupported aliases. (REQ-4)
  * [ ] 5.6 Add tests for canonical key and supported aliases. (REQ-4, REQ-12)

* [ ] 6. Handle optional PDF dependencies

  * [ ] 6.1 Identify PDF rendering dependencies. (REQ-5)
  * [ ] 6.2 Decide whether PDF export is required or optional for the deployment. (REQ-5)
  * [ ] 6.3 Add config flag for PDF export enabled/disabled if missing and needed. (REQ-5)
  * [ ] 6.4 Add config flag for PDF export required if needed. (REQ-5, REQ-9)
  * [ ] 6.5 If dependencies are missing and PDF is optional, mark PDF unavailable without raw import error. (REQ-5)
  * [ ] 6.6 If dependencies are missing and PDF is required, fail validation/startup/readiness with safe error. (REQ-5, REQ-9)
  * [ ] 6.7 Add tests for dependency-available and dependency-missing behavior where practical. (REQ-5, REQ-12)

* [ ] 7. Update supported format discovery

  * [ ] 7.1 Locate supported export format list endpoint/service. (REQ-6)
  * [ ] 7.2 Include PDF when PDF exporter is registered and available. (REQ-6)
  * [ ] 7.3 Omit or mark PDF unavailable when PDF export is disabled. (REQ-6)
  * [ ] 7.4 Omit or mark PDF unavailable when dependencies are missing. (REQ-6)
  * [ ] 7.5 Include canonical key, label, extension, and MIME type for PDF when listed. (REQ-6)
  * [ ] 7.6 Add tests for supported format discovery in enabled, disabled, and unavailable states. (REQ-6, REQ-12)

* [ ] 8. Update export API path

  * [ ] 8.1 Ensure export API normalizes requested format. (REQ-7)
  * [ ] 8.2 Ensure `format=pdf` uses registered PDF exporter. (REQ-7)
  * [ ] 8.3 Ensure unauthorized export requests still follow existing auth rules. (REQ-7, REQ-11)
  * [ ] 8.4 Ensure private/unpublished content export still follows existing visibility rules. (REQ-7, REQ-11)
  * [ ] 8.5 Return structured unavailable error when PDF exporter is unavailable. (REQ-7)
  * [ ] 8.6 Return structured export failure when PDF rendering fails. (REQ-7)
  * [ ] 8.7 Add API tests for successful PDF export and unavailable PDF error. (REQ-7, REQ-12)

* [ ] 9. Update export manifest handling

  * [ ] 9.1 Ensure successful PDF artifacts use format `pdf`. (REQ-8)
  * [ ] 9.2 Ensure PDF artifacts use MIME type `application/pdf` where manifest supports MIME types. (REQ-8)
  * [ ] 9.3 Ensure PDF artifacts use extension `.pdf` where manifest supports extensions. (REQ-8)
  * [ ] 9.4 Ensure failed PDF exports do not create misleading successful manifest entries. (REQ-8)
  * [ ] 9.5 Ensure existing non-PDF manifest behavior does not regress. (REQ-8, REQ-10)
  * [ ] 9.6 Add manifest tests for successful PDF export and PDF failure. (REQ-8, REQ-12)

* [ ] 10. Add registry validation

  * [ ] 10.1 Add exporter registry validation helper if missing. (REQ-9)
  * [ ] 10.2 Validate required built-in exporters. (REQ-9)
  * [ ] 10.3 Validate `pdf` when PDF export is enabled or required. (REQ-9)
  * [ ] 10.4 Skip required PDF validation when PDF export is disabled. (REQ-9)
  * [ ] 10.5 Wire validation into tests and optionally startup/readiness. (REQ-9)
  * [ ] 10.6 Add test that missing PDF registration fails validation. (REQ-9, REQ-12)

* [ ] 11. Add security and safe error checks

  * [ ] 11.1 Ensure PDF export errors do not expose stack traces. (REQ-11)
  * [ ] 11.2 Ensure PDF export errors do not expose internal filesystem paths. (REQ-11)
  * [ ] 11.3 Ensure dependency errors are converted to safe messages. (REQ-11)
  * [ ] 11.4 Ensure filename sanitization still applies to PDF exports. (REQ-11)
  * [ ] 11.5 Ensure existing export authorization still applies. (REQ-11)
  * [ ] 11.6 Add tests for safe errors where practical. (REQ-11, REQ-12)

* [ ] 12. Regression test coverage

  * [ ] 12.1 Add registry contains `pdf` test. (REQ-1, REQ-12)
  * [ ] 12.2 Add `export_pdf()` no-`KeyError` test. (REQ-3, REQ-12)
  * [ ] 12.3 Add `export_pdf()` invokes PDF exporter test. (REQ-3, REQ-12)
  * [ ] 12.4 Add unknown format structured error test. (REQ-2, REQ-12)
  * [ ] 12.5 Add supported formats include PDF when available test. (REQ-6, REQ-12)
  * [ ] 12.6 Add supported formats hide/mark PDF unavailable when disabled test. (REQ-6, REQ-12)
  * [ ] 12.7 Add export API `format=pdf` success test. (REQ-7, REQ-12)
  * [ ] 12.8 Add PDF unavailable/dependency-missing test if optional dependencies apply. (REQ-5, REQ-12)
  * [ ] 12.9 Add existing exporters remain registered test. (REQ-10, REQ-12)
  * [ ] 12.10 Add manifest canonical PDF metadata test. (REQ-8, REQ-12)
  * [ ] 12.11 Run existing export test suite and update only additive snapshots. (REQ-10, REQ-12)

* [ ] 13. Documentation

  * [ ] 13.1 Document canonical PDF export key. (REQ-4)
  * [ ] 13.2 Document PDF export dependency requirements. (REQ-5)
  * [ ] 13.3 Document PDF enabled/disabled config if added. (REQ-5)
  * [ ] 13.4 Document supported format discovery behavior. (REQ-6)
  * [ ] 13.5 Document controlled errors for unavailable PDF export. (REQ-2, REQ-7)
  * [ ] 13.6 Add troubleshooting note for missing exporter registration. (REQ-9)

* [ ] 14. Completion verification

  * [ ] 14.1 Inspect registry and verify `pdf` is registered when PDF is enabled. (REQ-13)
  * [ ] 14.2 Call `export_pdf()` in a controlled test and verify no `KeyError`. (REQ-13)
  * [ ] 14.3 Export a small novel/chapter as PDF through the normal service path. (REQ-13)
  * [ ] 14.4 Export through API with `format=pdf`. (REQ-7, REQ-13)
  * [ ] 14.5 Verify supported format discovery shows PDF only when usable. (REQ-6, REQ-13)
  * [ ] 14.6 Simulate unavailable PDF exporter and verify structured error, not `KeyError`. (REQ-2, REQ-13)
  * [ ] 14.7 Verify existing HTML/EPUB export still works. (REQ-10, REQ-13)
  * [ ] 14.8 Mark `pdf-exporter-registration` complete only after the original `KeyError` path is covered by regression tests.
