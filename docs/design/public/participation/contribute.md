# Participation — Contribute Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | participation |
| Routes | `/contribute` |
| Design status | approved target |
| Implementation status | implemented (informational placeholder) |
| Active work | `DEBT-CONTRIB-01` (`WORK.md`) |
| Implementation | `frontend/app/(public)/contribute/page.tsx` |

## Purpose
Informational landing page explaining the community API-key contribution program.

## User Goal
Learn how community API-key contributions support translation bandwidth.

## Audience and Permissions
- **Guests & Authenticated Users:** Open public access.

## Primary Action
Read program overview and guidelines.

## Information Hierarchy
1. Page Header ("API Contributions", Subtitle)
2. Status Notice (Informational card explaining contribution status)
3. How It Works Section (Overview of key security, encryption, and usage rules)

## Page Anatomy
- Informational card layout.

## Desktop Layout
Centered container (720px max width).

## Mobile Layout
Full width text container.

## Interaction Flow
- Read-only informational surface.

## Authentication or Authorization Behavior
- Open access for all visitors.

## States

### Initial
Page rendering.

### Loading
Not applicable.

### Empty
Not applicable.

### Pending
Not applicable.

### Settled
Informational page content rendered.

### Recoverable Error
Not applicable.

### Unavailable
Not applicable.

### Unauthorized or Forbidden
Not applicable.

### Success
Not applicable.

## Components
- `Panel`
- `Badge`

## Content and Copy
- Banner: "API contributions are currently disabled."

## Accessibility
- High contrast text layout.

## Responsive Behavior
- Clean single-column layout across all viewports.

## Data Requirements
- Static content.

## Privacy, Safety, and Security
- Does not expose any credential inputs until `DEBT-CONTRIB-01` readiness gate passes.

## Acceptance Criteria
- Page displays honest unavailable state for API key submission.

## Implementation Mapping
- `frontend/app/(public)/contribute/page.tsx`
