# requirements.md

# Requirements: PDF Exporter Registration

## Introduction

The application needs PDF export registration fixed so `export_pdf()` does not raise `KeyError`. If PDF export is advertised or callable, the exporter must be registered, discoverable, and safely handled when unavailable.

## Requirement 1: PDF exporter registration

### User story

As a user, I want PDF export to work when it is offered so I can download translated content as a PDF.

### Acceptance criteria

1. WHEN the export subsystem initializes THEN the PDF exporter SHALL be registered under the canonical `pdf` format key.
2. WHEN the PDF exporter is registered THEN registry lookup for `pdf` SHALL return the PDF exporter.
3. WHEN `export_pdf()` is called and PDF export is enabled THEN it SHALL resolve the PDF exporter without raising `KeyError`.
4. WHEN the PDF exporter implementation exists THEN it SHALL be imported or registered explicitly during export subsystem setup.
5. WHEN the application starts THEN PDF registration SHALL not depend on accidental imports from unrelated modules.
6. WHEN PDF export is disabled by configuration THEN the system SHALL not advertise PDF as available.

## Requirement 2: Safe exporter lookup

### User story

As a maintainer, I want exporter lookup to return controlled errors so missing registration does not crash callers with raw `KeyError`.

### Acceptance criteria

1. WHEN an unknown export format is requested THEN the system SHALL return a structured unsupported-format error.
2. WHEN PDF exporter is unavailable THEN the system SHALL return a structured exporter-unavailable error.
3. WHEN exporter lookup fails THEN raw `KeyError` SHALL NOT escape API or service boundaries.
4. WHEN supported formats are queried THEN unavailable exporters SHALL be omitted or clearly marked unavailable.
5. WHEN an export helper calls the registry THEN it SHALL use the same safe lookup path as normal export requests.
6. WHEN errors are returned to clients THEN they SHALL not expose stack traces or internal module paths.

## Requirement 3: `export_pdf()` wrapper behavior

### User story

As a developer, I want `export_pdf()` to use the normal export service path so PDF behavior stays consistent with other formats.

### Acceptance criteria

1. WHEN `export_pdf()` is called THEN it SHALL request format `pdf` through the standard export service or equivalent shared path.
2. WHEN `export_pdf()` succeeds THEN it SHALL return a PDF export result/artifact.
3. WHEN `export_pdf()` receives invalid export input THEN it SHALL return the same validation behavior as other export formats.
4. WHEN PDF rendering fails THEN it SHALL return a controlled `export_failed` or equivalent error.
5. WHEN PDF exporter is missing or disabled THEN `export_pdf()` SHALL return a controlled unavailable-format error.
6. WHEN `export_pdf()` is tested THEN no raw `KeyError` SHALL be raised.

## Requirement 4: Format key normalization

### User story

As a developer, I want format keys normalized so callers can request PDF consistently.

### Acceptance criteria

1. WHEN a caller requests `pdf` THEN the system SHALL use canonical key `pdf`.
2. WHEN a caller requests `PDF` THEN the system SHOULD normalize to `pdf` if case-insensitive format handling is supported.
3. WHEN a caller requests `.pdf` THEN the system MAY normalize to `pdf` if extension aliases are supported.
4. WHEN a caller requests `application/pdf` THEN the system MAY normalize to `pdf` if MIME aliases are supported.
5. WHEN a format alias is unsupported THEN the system SHALL return a structured unsupported-format error.
6. WHEN supported formats are listed THEN canonical keys SHALL be used.
7. WHEN export manifests are written THEN PDF exports SHALL use canonical format `pdf`.

## Requirement 5: Optional dependency handling

### User story

As an operator, I want PDF export dependency failures to be explicit so deployments do not silently advertise broken PDF export.

### Acceptance criteria

1. WHEN PDF export depends on optional libraries and they are installed THEN PDF exporter SHALL be available.
2. WHEN PDF export depends on optional libraries and they are missing THEN the system SHALL not raise raw import errors in normal API responses.
3. WHEN PDF dependencies are missing and PDF is optional THEN supported formats SHALL omit PDF or mark it unavailable.
4. WHEN PDF dependencies are missing and PDF is required THEN startup or readiness SHALL fail with a safe configuration error.
5. WHEN dependency errors are logged THEN logs SHALL not expose secrets or unrelated environment data.
6. WHEN an unavailable PDF export is requested THEN the system SHALL return a clear structured error.

## Requirement 6: Supported export format discovery

### User story

As a frontend developer, I want supported export formats to accurately reflect whether PDF is available.

### Acceptance criteria

1. WHEN PDF exporter is registered and available THEN supported format discovery SHALL include PDF.
2. WHEN PDF export is disabled THEN supported format discovery SHALL not show PDF as available.
3. WHEN PDF export dependencies are missing THEN supported format discovery SHALL omit PDF or mark it unavailable.
4. WHEN PDF appears in supported formats THEN it SHALL include canonical key `pdf`.
5. WHEN PDF appears in supported formats THEN it SHOULD include label, file extension, and MIME type.
6. WHEN supported format discovery is used by frontend export controls THEN users SHALL not be offered a broken PDF option.

## Requirement 7: Export API compatibility

### User story

As a user, I want API-based PDF export to work through the same export endpoint as other formats.

### Acceptance criteria

1. WHEN an authorized user requests export with format `pdf` THEN the API SHALL invoke the registered PDF exporter.
2. WHEN PDF export succeeds THEN the API SHALL return or create a PDF artifact according to existing export conventions.
3. WHEN PDF exporter is unavailable THEN the API SHALL return a structured unavailable-format error.
4. WHEN PDF exporter fails during rendering THEN the API SHALL return a structured export failure.
5. WHEN unauthorized users request PDF export THEN existing export authorization rules SHALL apply.
6. WHEN an unpublished/private item is exported THEN existing content visibility rules SHALL apply.
7. WHEN API errors occur THEN raw `KeyError`, stack traces, and internal import errors SHALL not be returned.

## Requirement 8: Export manifest compatibility

### User story

As an operator, I want PDF export artifacts to be recorded consistently in manifests so export history stays reliable.

### Acceptance criteria

1. WHEN a PDF export artifact is created THEN its manifest entry SHALL use format `pdf`.
2. WHEN a PDF export artifact is created THEN its MIME type SHOULD be `application/pdf`.
3. WHEN a PDF export artifact is created THEN its file extension SHOULD be `.pdf`.
4. WHEN PDF export fails before artifact creation THEN the manifest SHALL not record a misleading successful PDF artifact.
5. WHEN export freshness or manifest code reads format values THEN PDF SHALL use the same canonical format key as registry lookup.
6. WHEN PDF exporter registration is fixed THEN existing non-PDF manifest behavior SHALL not regress.

## Requirement 9: Startup or validation checks

### User story

As a maintainer, I want missing built-in exporter registration caught early so this bug does not return.

### Acceptance criteria

1. WHEN exporter registry validation runs THEN it SHALL verify required built-in exporters are registered.
2. WHEN PDF export is enabled or required THEN validation SHALL verify `pdf` is registered and available.
3. WHEN PDF export is disabled THEN validation SHALL not require PDF registration.
4. WHEN validation fails in test or required startup mode THEN it SHALL produce a clear error.
5. WHEN validation succeeds THEN export registry SHALL include all required formats.
6. WHEN tests run THEN missing PDF registration SHALL cause a failing test.

## Requirement 10: Regression safety for other exporters

### User story

As a maintainer, I want the PDF registration fix to avoid breaking EPUB, HTML, or other export formats.

### Acceptance criteria

1. WHEN PDF exporter registration is added THEN existing exporter registrations SHALL remain intact.
2. WHEN supported formats are listed THEN existing formats SHALL still appear according to their availability.
3. WHEN non-PDF export helpers are called THEN their behavior SHALL not change.
4. WHEN registry validation runs THEN it SHALL validate all required exporters, not only PDF.
5. WHEN tests run THEN existing export tests SHALL continue passing.
6. WHEN registry initialization imports PDF exporter THEN it SHALL not introduce import cycles that break other exporters.

## Requirement 11: Security and safe errors

### User story

As an operator, I want PDF export registration and failures to avoid leaking internal details.

### Acceptance criteria

1. WHEN PDF export fails THEN public/API errors SHALL not include stack traces.
2. WHEN PDF export fails THEN public/API errors SHALL not include internal filesystem paths.
3. WHEN PDF export fails due to dependency issues THEN public/API errors SHALL not include raw import traces.
4. WHEN PDF export creates files THEN existing filename sanitization rules SHALL apply.
5. WHEN PDF export is requested THEN existing content authorization rules SHALL apply.
6. WHEN PDF exporter is unavailable THEN the response SHALL be safe and user-understandable.

## Requirement 12: Test coverage

### User story

As a maintainer, I want tests that prove PDF export registration works and cannot regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL verify the registry contains `pdf` when PDF export is enabled.
2. WHEN tests run THEN they SHALL verify `export_pdf()` does not raise `KeyError`.
3. WHEN tests run THEN they SHALL verify `export_pdf()` invokes the PDF exporter.
4. WHEN tests run THEN they SHALL verify unknown format lookup returns a structured error.
5. WHEN tests run THEN they SHALL verify supported format discovery includes PDF when available.
6. WHEN tests run THEN they SHALL verify supported format discovery hides or marks PDF unavailable when disabled.
7. WHEN tests run THEN they SHALL verify API export with `format=pdf` succeeds when exporter is available.
8. WHEN tests run THEN they SHALL verify PDF unavailable/dependency-missing behavior if optional dependencies apply.
9. WHEN tests run THEN they SHALL verify existing exporters remain registered.
10. WHEN tests run THEN they SHALL verify export manifest uses canonical PDF metadata where applicable.

## Requirement 13: Completion verification

### User story

As a maintainer, I want a clear completion check so this bug is only closed when the PDF export path actually works.

### Acceptance criteria

1. WHEN `export_pdf()` is called in a controlled test THEN it SHALL not raise `KeyError`.
2. WHEN the export registry is inspected THEN `pdf` SHALL be registered if PDF export is enabled.
3. WHEN supported formats are inspected THEN PDF SHALL appear only when usable.
4. WHEN the export API is called with `format=pdf` THEN it SHALL return a PDF export result or controlled unavailable error.
5. WHEN PDF export is unavailable by config or dependency THEN the system SHALL return a structured error, not `KeyError`.
6. WHEN existing export tests run THEN non-PDF formats SHALL still pass.
