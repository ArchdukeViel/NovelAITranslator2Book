# Discovery — Shared Search Overlay

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | discovery |
| Routes | Global overlay (`/` key, desktop header search input, mobile search tab) |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/components/public/search-overlay.tsx`, `frontend/lib/search-overlay.ts`, `frontend/components/public/search-entry.tsx` |

## Purpose
Unified search overlay providing instant, grouped search results across titles, authors, genres, and tags.

## User Goal
Instantly locate a novel, author, or tag without navigating to full catalog browse.

## Audience and Permissions
- **Guests & Authenticated Users:** Unrestricted search access.

## Primary Action
Enter query and select matching result.

## Information Hierarchy
1. Search Input Bar (Auto-focused text input with clear button)
2. Empty State View (Recent local searches list + Popular genre shortcuts)
3. Grouped Results View (Novels section, Authors section, Genres & Tags section)
4. Footer CTA ("See all results for '...'")

## Page Anatomy
- Centered modal dialog on desktop (max-w-2xl); full-screen sheet on mobile.
- Keyboard-trapped input field.
- Highlightable result items with keyboard arrow focus indicators.

## Desktop Layout
Centered modal overlay with semi-transparent backdrop (`bg-background/80 backdrop-blur-sm`).

## Mobile Layout
Full-screen overlay filling viewport.

## Interaction Flow
- Triggered by clicking header search input, tapping mobile Search tab, or pressing `/` hotkey.
- Keystrokes debounced (225ms); `AbortController` cancels stale requests.
- `ArrowDown` / `ArrowUp` cycle results; `Enter` opens highlighted item; `Escape` closes overlay.

## Authentication or Authorization Behavior
- Open access. Recent search history stored locally in browser `localStorage`.

## States

### Initial
Empty query state displaying recent search history items and genre pills.

### Loading
Input displays subtle loading spinner; existing results remain visible to prevent layout flicker.

### Empty
"No results found for '...' Try searching by title, author, or tag."

### Pending
Async fetch in flight.

### Settled
Grouped search results rendered.

### Recoverable Error
"Search is temporarily unavailable. Check network connection."

### Unavailable
Backend search index offline.

### Unauthorized or Forbidden
Not applicable.

### Success
Navigation to selected result item.

## Components
- `SearchOverlay`
- `SearchEntry`
- `Command` primitives

## Content and Copy
- Placeholder: "Search by novel title, author, genre, or tag..."
- Empty state: "No matches found"

## Accessibility
- Dialog role (`role="dialog"`), `aria-expanded`, dynamic live region for result counts.
- `Escape` key closes overlay and restores focus to trigger element.

## Responsive Behavior
- Adapts between desktop centered modal and mobile full-screen layer.

## Data Requirements
- Fast title/author/tag search query API (`usePublicCatalog` search filter).

## Privacy, Safety, and Security
- Recent searches saved locally on device only (`localStorage`); never synced to backend.

## Acceptance Criteria
- `/` hotkey opens overlay unless typing inside a form input.
- `Escape` closes overlay and returns focus.
- Keystrokes cancel in-flight stale requests without flickering UI.

## Implementation Mapping
- `frontend/components/public/search-overlay.tsx`
- `frontend/lib/search-overlay.ts`
