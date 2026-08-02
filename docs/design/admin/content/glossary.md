# Admin Content — Glossary Management Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | content |
| Routes | `/admin/novels/[novelId]/glossary` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/novels/[novelId]/glossary/page.tsx`, `frontend/components/admin/glossary-qa-panel.tsx` |

## Purpose
Novel-specific translation dictionary and term glossary manager.

## User Goal
Add, edit, or import CJK-to-English translation terms (character names, locations, terms) to enforce consistency during AI translation.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Add Glossary Term" / "Save Glossary" button.

## Information Hierarchy
1. Page Header (Novel title, "Import Terms" button, "Auto-Populate" button)
2. Add Term Form (Original CJK term input, English translation input, Category select)
3. Glossary Terms Table (Original term, translation, category, actions)
4. Glossary Diagnostics / QA Panel (`GlossaryQAPanel`)

## Page Anatomy
- Form card + Data table + QA diagnostics block.

## Desktop Layout
Full width data table with inline editing controls.

## Mobile Layout
Stacked card view.

## Interaction Flow
- Adding a term inserts row into table. Term edits trigger automatic translation cache invalidation notices.

## Authentication or Authorization Behavior
- Requires owner role.

## States

### Initial
Loading glossary terms.

### Loading
Table pulse loading.

### Empty
"No glossary terms defined for this novel yet."

### Pending
Save term mutation in flight.

### Settled
Populated glossary table.

### Recoverable Error
"Failed to update glossary terms."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast notification confirming glossary update.

## Components
- `GlossaryQAPanel`
- `Table`
- `Button`
- `Input`

## Content and Copy
- Header: "Novel Translation Glossary"

## Accessibility
- Form controls labeled; QA warnings announced via live regions.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Novel glossary terms list (`useAdminGlossary`).

## Privacy, Safety, and Security
- Modifying terms invalidates cached chapter translations to prevent term drift.

## Acceptance Criteria
- Auto-populate extracts candidate terms from source chapters.

## Implementation Mapping
- `frontend/app/(admin)/admin/novels/[novelId]/glossary/page.tsx`
- `frontend/components/admin/glossary-qa-panel.tsx`
