# Trust — Informational Pages

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | trust |
| Routes | `/about`, `/contact`, `/support`, `/faq`, `/news`, `/legal`, `/terms`, `/privacy`, `/cookie-policy` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/about/page.tsx`, `frontend/app/(public)/faq/page.tsx`, `frontend/app/(public)/news/page.tsx`, `frontend/app/(public)/terms/page.tsx`, `frontend/app/(public)/privacy/page.tsx`, etc. |

## Purpose
Static informational, support, FAQ, product changelog, and legal compliance pages.

## User Goal
Read platform information, get answers to common questions, view news updates, or review legal policies.

## Audience and Permissions
- **Guests & Authenticated Users:** Open public access.

## Primary Action
Read content.

## Information Hierarchy
1. Page Header (Title, Last updated date)
2. Main Content Body (Structured prose layout, max width 720px)
3. Footer Navigation

## Page Anatomy
- Clean text container with styled heading hierarchy.

## Desktop Layout
Centered 720px text column.

## Mobile Layout
Full width column with 16px side padding.

## Interaction Flow
- Read-only static pages. FAQ contains expandable accordion sections.

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
Static prose content rendered.

### Recoverable Error
Not applicable.

### Unavailable
Not applicable.

### Unauthorized or Forbidden
Not applicable.

### Success
Not applicable.

## Components
- Static page container
- Accordion (FAQ)

## Content and Copy
- Professional, clear, legal and informational copy. Public copy never leaks internal codenames.

## Accessibility
- Logical H1/H2/H3 heading hierarchy and high contrast text.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Static content.

## Privacy, Safety, and Security
- Does not render private data or backend paths.

## Acceptance Criteria
- Content width restricted to 720px max for optimal reading measure.

## Implementation Mapping
- `frontend/app/(public)/about/page.tsx`
- `frontend/app/(public)/faq/page.tsx`
- `frontend/app/(public)/news/page.tsx`
