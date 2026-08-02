# Admin Content — Chapter Translation Editor Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | content |
| Routes | `/admin/editor` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/editor/page.tsx` |

## Purpose
Side-by-side Japanese source vs. English translation chapter editor and version manager.

## User Goal
Review AI-translated chapters paragraph by paragraph, edit translation text, and switch or roll back versions.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Save & Publish Translation Version" button.

## Information Hierarchy
1. Editor Header (Novel title, chapter selector, active version badge, Save button)
2. Side-by-Side Editor (Left Pane: Original Japanese text paragraphs; Right Pane: Editable English translation text blocks)
3. Bottom Bar / Drawer (Version history list, glossary term reference, QA check warnings)

## Page Anatomy
- Dual-pane side-by-side text grid.

## Desktop Layout
50/50 split vertical pane layout with independent scrolling synchronization.

## Mobile Layout
Tabbed toggle between "Japanese Source" and "English Translation" views.

## Interaction Flow
- Editing right-pane text updates local draft; clicking "Save" creates new translation version.

## Authentication or Authorization Behavior
- Requires owner role. Unsaved changes prompt confirmation on navigation.

## States

### Initial
Loading chapter text.

### Loading
Editor skeleton loaders.

### Empty
"Selected chapter has no source text."

### Pending
Version save mutation in flight.

### Settled
Chapter text loaded into editor panes.

### Recoverable Error
"Could not load chapter text."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation on version save.

## Components
- Dual-pane Editor grid
- `Button`
- `Badge`

## Content and Copy
- Header: "Translation Editor"

## Accessibility
- Both text panes accessible with keyboard scroll and focus traps avoided.

## Responsive Behavior
- Desktop dual-pane switches to mobile tabbed view.

## Data Requirements
- Raw Japanese chapter paragraphs, translated English version paragraphs, version history list.

## Privacy, Safety, and Security
- Preserves raw source chapter data in backend audit storage.

## Acceptance Criteria
- Unsaved changes trigger confirmation prompt before leaving page.

## Implementation Mapping
- `frontend/app/(admin)/admin/editor/page.tsx`
