# Admin Operations — Analytics Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | operations |
| Routes | `/admin/analytics` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/analytics/page.tsx` |

## Purpose
System telemetry dashboard for tracking chapter reading metrics, active reader traffic, and AI translation token costs.

## User Goal
Analyze platform traffic, popular novels, and monitor AI translation token usage and costs.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
Filter analytics timeframe and inspect usage charts.

## Information Hierarchy
1. Page Header ("System Telemetry & Analytics", Timeframe Selector: 7d, 30d, 90d)
2. Traffic Summary Cards (Chapter Reads, Active Readers, Total Token Spend)
3. Charts Grid (Reading activity over time, AI Translation token consumption by model)

## Page Anatomy
- Timeframe filter bar + Metric cards + Telemetry charts.

## Desktop Layout
Full width charts grid.

## Mobile Layout
Single column stacked charts layout.

## Interaction Flow
- Changing timeframe dropdown refetches analytics metrics for selected window.

## Authentication or Authorization Behavior
- Requires owner role.

## States

### Initial
Loading chart skeletons.

### Loading
Pulse loading state for charts.

### Empty
"No analytics data recorded for selected timeframe."

### Pending
Not applicable.

### Settled
Populated analytics charts.

### Recoverable Error
"Failed to load analytics data."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Not applicable.

## Components
- `Panel`
- `Select`

## Content and Copy
- Header: "Platform Analytics & Token Usage"

## Accessibility
- Charts accompany tabular text data for screen readers.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Aggregated analytics events data (`useAdminAnalytics`).

## Privacy, Safety, and Security
- Analyzes anonymized event data; no personal user tracking exposed.

## Acceptance Criteria
- Token spend charts display accurate AI provider model breakdowns.

## Implementation Mapping
- `frontend/app/(admin)/admin/analytics/page.tsx`
