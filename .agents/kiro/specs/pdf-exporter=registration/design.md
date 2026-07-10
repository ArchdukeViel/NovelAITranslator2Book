# design.md

# Design: PDF Exporter Registration

## Overview

`pdf-exporter-registration` fixes the exporter registry path so PDF export is available when the application advertises or calls `export_pdf()`.

The current issue is that `export_pdf()` can raise `KeyError`, which strongly suggests the PDF exporter implementation exists or is expected, but is not registered with the export registry under the expected format key.

This spec ensures PDF export is registered consistently, discoverable through supported export formats, validated at startup or test time, and covered by regression tests.

## Goals

* Register the PDF exporter with the existing export registry.
* Ensure `export_pdf()` resolves the PDF exporter without `KeyError`.
* Ensure PDF export appears in supported format lists only when available.
* Add startup/test validation for required exporter registrations.
* Preserve existing export architecture and other formats.
* Add regression tests for registry lookup, direct `export_pdf()`, and API export paths.

## Non-goals

* No full PDF layout redesign.
* No new PDF rendering engine unless no exporter exists.
* No major export manifest redesign.
* No scheduled export freshness work.
* No admin export manifest UI.
* No public reader rendering changes.
* No EPUB/HTML/TXT exporter changes except ensuring registration is not broken.

## Current problem

Expected failure pattern:

```text id="ozf2rp"
export_pdf()
  -> export registry lookup for "pdf"
  -> KeyError because "pdf" is not registered
```

Possible causes:

```text id="gpv17m"
PDF exporter class exists but is not imported during registry setup
PDF exporter is registered under the wrong key
registry key uses "application/pdf" but caller uses "pdf"
export_pdf() bypasses normal registry setup
registration is conditional on an optional dependency that is missing
supported format list advertises PDF even when exporter is unavailable
tests do not validate registry completeness
```

## Existing architecture assumption

The project likely has an export abstraction similar to:

```text id="do6kes"
ExportService
ExporterRegistry
BaseExporter
HtmlExporter
EpubExporter
PdfExporter
export_pdf()
export_epub()
export_html()
```

This spec should adapt to actual project names.

Recommended approach:

```text id="34j4a6"
1. Keep the existing registry pattern.
2. Add or fix PDF exporter registration.
3. Make direct export helper methods use the same registry keys.
4. Add validation tests to prevent future missing registrations.
```

## Export format keys

Use stable canonical keys.

Recommended canonical format keys:

```text id="b6cuzx"
html
epub
pdf
txt
json
```

For PDF:

```text id="cz1ol0"
canonical key: pdf
mime type: application/pdf
file extension: .pdf
```

If the system supports aliases, PDF aliases may include:

```text id="le5k31"
application/pdf
.pdf
PDF
```

However, internal registry lookup should normalize all aliases to:

```text id="iwp1dl"
pdf
```

## Registration design

The PDF exporter should be registered during export subsystem initialization.

Recommended registration:

```python id="qx1tiw"
exporter_registry.register("pdf", PdfExporter)
```

or, if using instances:

```python id="z8xwh4"
exporter_registry.register("pdf", PdfExporter(...))
```

or, if using decorators:

```python id="5gkov7"
@register_exporter("pdf")
class PdfExporter(BaseExporter):
    ...
```

Registration must happen before:

```text id="f8umgw"
export_pdf()
supported export format lookup
export API endpoint handling
scheduled export handling
manifest generation
```

## Import safety

A common registry bug is that registration happens only if a module is imported. The export subsystem should explicitly import/register all built-in exporters.

Recommended module pattern:

```text id="fek6pq"
exports/
  __init__.py
  registry.py
  service.py
  exporters/
    __init__.py
    html.py
    epub.py
    pdf.py
```

`exports/exporters/__init__.py` or export subsystem bootstrap should import PDF exporter registration.

Avoid relying on incidental imports from API routes.

## Optional dependency handling

PDF export may depend on optional libraries.

If PDF dependencies are required for advertised PDF export:

```text id="9xtwak"
missing dependency -> startup/config validation error or PDF not advertised
```

If PDF export is optional:

```text id="hi3ezf"
dependency available -> register PDF exporter
dependency missing -> do not advertise PDF; return clear unsupported-format error if requested
```

Do not let missing optional dependencies become a raw `KeyError`.

Recommended error:

```text id="ucgyip"
exporter_unavailable
```

or:

```text id="t9zmd6"
unsupported_export_format
```

with safe message:

```text id="5n1a8t"
PDF export is not available in this deployment.
```

## `export_pdf()` behavior

`export_pdf()` should be a thin wrapper around the normal export service.

Recommended behavior:

```python id="yaj8mk"
def export_pdf(request):
    return export_service.export(format="pdf", request=request)
```

It should not duplicate exporter lookup logic unless necessary.

Expected outcomes:

```text id="hsc65f"
registered PDF exporter -> returns PDF artifact/result
PDF exporter unavailable -> returns clear typed export error
invalid export input -> returns validation/export error
unexpected PDF render failure -> returns export_failed with safe message
```

`KeyError` should not escape to callers.

## Supported format discovery

If the application exposes supported export formats, PDF should appear only when usable.

Recommended supported format object:

```json id="qa9uov"
{
  "key": "pdf",
  "label": "PDF",
  "extension": ".pdf",
  "mime_type": "application/pdf",
  "available": true
}
```

If unavailable:

```json id="5h9jpv"
{
  "key": "pdf",
  "label": "PDF",
  "extension": ".pdf",
  "mime_type": "application/pdf",
  "available": false,
  "reason": "missing_dependency"
}
```

Alternatively, omit unavailable formats from public lists.

## Startup validation

Add a lightweight validation hook for built-in exporters.

Recommended required exporters when configured:

```text id="zda636"
html
epub
pdf if PDF_EXPORT_ENABLED=true
```

Recommended config:

```text id="mwkx0y"
PDF_EXPORT_ENABLED=true
PDF_EXPORT_REQUIRED=false
```

Behavior:

```text id="auwlkw"
PDF_EXPORT_ENABLED=true and dependencies available -> register pdf
PDF_EXPORT_ENABLED=true and dependencies missing -> return controlled unavailable state
PDF_EXPORT_REQUIRED=true and pdf unavailable -> fail startup/readiness
PDF_EXPORT_ENABLED=false -> do not advertise PDF
```

If the project does not need config, keep it simple and always register PDF.

## API behavior

Any export API endpoint that accepts `format=pdf` should:

```text id="h06scp"
normalize format to "pdf"
look up exporter safely
return PDF artifact when available
return structured unsupported/unavailable error when not available
never return raw KeyError
```

Recommended error codes:

```text id="daijw1"
unsupported_export_format
exporter_unavailable
export_dependency_missing
export_failed
```

## Manifest behavior

If export manifests record format information, PDF exports should use canonical PDF metadata:

```json id="w1jfer"
{
  "format": "pdf",
  "mime_type": "application/pdf",
  "file_extension": ".pdf"
}
```

This spec does not require new manifest UI work.

## Security

PDF export may process user-generated or translated content.

Registration itself has low security risk, but export behavior should preserve existing safeguards:

```text id="1ylqvk"
do not expose local filesystem paths publicly
sanitize filenames
enforce export authorization
avoid SSRF-prone remote asset loading unless already controlled
do not include private unpublished content in public exports
return safe errors
```

## Testing strategy

Tests should cover:

```text id="9qmcgm"
PDF exporter is registered under "pdf"
format normalization maps "PDF" and ".pdf" to "pdf" if aliases exist
export_pdf() does not raise KeyError
export_pdf() calls the registered PDF exporter
supported format list includes PDF when available
supported format list excludes or marks PDF unavailable when disabled/missing dependency
export API with format=pdf succeeds when exporter available
export API with unavailable PDF returns structured error
registry validation catches missing required PDF registration
other exporters remain registered
```

## Rollout plan

1. Inspect exporter registry and PDF exporter implementation.
2. Identify expected PDF registry key.
3. Add/fix PDF exporter registration.
4. Normalize PDF format aliases if missing.
5. Update `export_pdf()` to use safe registry lookup.
6. Update supported format discovery.
7. Add startup/test validation for registered exporters.
8. Add regression tests for `KeyError`.
9. Verify:

   * `export_pdf()` works.
   * export API `format=pdf` works.
   * PDF appears only when available.
   * no raw `KeyError` reaches API callers.
