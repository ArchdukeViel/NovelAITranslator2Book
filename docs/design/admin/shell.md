# Admin Shell & Frame

Layout frame, navigation, and global controls for admin operators.

## Navigation Structure

- **Desktop Sidebar:**
  - Overview / Dashboard (`/admin`, `/admin/dashboard`)
  - Ingestion (Crawler `/admin/crawler`, Activity `/admin/activity`)
  - Content (Library `/admin/library`, Translation `/admin/translation`, Editor `/admin/editor`, Glossary `/admin/novels/[id]/glossary`)
  - Moderation (Requests `/admin/requests`, Reviews `/admin/reviews`, Takedowns `/admin/takedowns`)
  - People (Users `/admin/users`)
  - Operations (Analytics `/admin/analytics`, Audit `/admin/audit`, Credentials `/admin/credentials`, Maintenance `/admin/maintenance`, Settings `/admin/settings`)
- **Header Frame:** Current page title, breadcrumb trail, system health indicator, owner session control.

## Responsive Adaptivity

- Sidebar collapses into collapsible drawer on smaller viewports.
- High-density data tables scroll horizontally with sticky first columns where necessary.

## Global Error & Unsaved State Handling

- Unsaved changes prompt confirmation before navigating away from editor forms.
- Operational error banners display sanitized error messages with clear next actions.
