# Public Reader Performance Budget

Local acceptance budgets for M4 public reader routes.

| Surface | Budget | Evidence |
|---|---:|---|
| Catalog API | p95 ≤ 500 ms, response ≤ 250 KiB | Focused API timing/payload check with `page_size=24` |
| Novel detail API | p95 ≤ 300 ms, response ≤ 100 KiB | Focused API timing/payload check |
| Chapter API | p95 ≤ 750 ms, response ≤ 1 MiB | Focused API timing/payload check |
| Catalog page size | Default 24, hard maximum 100 | FastAPI query validation tests |
| Glossary annotations | Maximum 50 per chapter response | Public-router regression test |
| Initial reader requests | One chapter payload; optional assets load separately | Browser network inspection |
| Public GET cache | `public, max-age=60` | Public-router header tests |
| Route JavaScript | Each public route ≤ 250 KiB first-load JS | `npm run build` route table |

Public catalog, novel, chapter-list, and translated-chapter responses contain no
user-specific data and may use short shared caching. Authentication, account,
admin, DMCA intake, errors, unavailable shells, and HTTP 451 responses must not
receive public cache headers.

Use `npm run build` for bundle evidence. Add analyzer tooling only when route
output exceeds budget and built-in Next.js route sizes cannot identify cause.
