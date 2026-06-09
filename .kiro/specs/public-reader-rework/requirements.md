# Requirements Document

## Introduction

This feature is a WTR-LAB-style redesign and rework of the **public reader application only** — the routes under `frontend/app/(public)/**` of the Next.js 15 / React 19 / TypeScript frontend. The goal is to give readers a polished discovery-and-reading experience that works for anonymous guests, plus authenticated account features for logged-in users: a shared public chrome (header, search entry, genre/browse navigation, current-user indicator, footer), a browse/discovery home with a novel grid and cards, a novel detail page, and a focused chapter reader with typography, theme, width, and chapter-navigation controls.

This document is a revision of an earlier version that assumed the public reader was anonymous-only with no authentication. That assumption is now **outdated**. Per `docs/current_state.md` (updated 2026-06-09) and `docs/roadmap/public-platform-expansion.md`, authentication is **live**: the backend enforces a guest/user/owner role model through HTTP-only session cookies and a `require_role()` dependency. Public authentication is therefore **no longer a blocked phase**. The platform is single-owner: the owner operates through the separate admin application and is out of scope for this rework.

Accordingly, the public reader now supports two reader contexts:

- **Guests (unauthenticated):** browse the catalog, search and filter novels, read published chapters, and adjust reading preferences with browser-local persistence.
- **Logged-in users (role `user`):** everything a guest can do, plus log in/out, save novels to a library, track reading progress with a "continue reading" affordance, view reading history, rate and review novels, submit rate-limited novel/chapter requests, and contribute their own translation provider API credential (for example a Gemini or OpenAI API key) to help the platform with translation.

The rework is strictly scoped to the public surface. It MUST NOT modify, restyle, or regress the admin/owner workspace under `frontend/app/(admin)/admin/**`. The owner-facing workspace is covered by a separate spec (`admin-ui-rework`) and MUST NOT be redesigned here. Because the public reader and the admin workspace share code (`lib/api.ts`, `lib/store.ts`, `components/ui/*`, `app/globals.css`, `tailwind.config.ts`, the root `app/layout.tsx`), this document also captures foundation requirements that protect the shared boundary.

Public **contribution** of translation provider credentials is now **in scope and a core platform purpose**: logged-in Public_Users may contribute their own translation provider API resources (for example a Gemini or OpenAI API key) to assist translation, subject to secure server-side handling. The earlier prohibition on implementing scheduler, QA, or provider-policy logic in the React layer is **removed as outdated**: while heavy execution still runs in backend workers, the Public_Reader is no longer forbidden from surfacing or configuring the relevant control and policy surfaces where it makes sense.

The following remain **out of scope and explicitly blocked**: batch mode; billing; organizations; and multi-admin teams. Google OAuth is schema-supported but **not yet wired**; the login experience MUST be designed around the available session login, treating OAuth as a future enhancement. The Owner_Credential (the owner Gemini `apiToken`) MUST remain confined to the admin surface and MUST NOT be required or attached by the public reader, and a Contributed_Credential supplied by a Public_User MUST NOT be conflated with or expose the Owner_Credential.

## Glossary

- **Public_Reader**: The redesigned public-facing reader application served from the `app/(public)/**` route group, used by both Guests and Public_Users.
- **Admin_Workspace**: The owner-facing application served from the `app/(admin)/admin/**` route group. Out of scope for modification; protected by foundation requirements and covered by the separate `admin-ui-rework` spec.
- **Reader**: Any end user of the Public_Reader, whether a Guest or a Public_User.
- **Guest**: An unauthenticated Reader. May browse the catalog, search/filter, read published chapters, and set browser-local reading preferences.
- **Public_User**: An authenticated Reader holding the backend role `user`. Has all Guest capabilities plus account features (library, reading progress, reading history, reviews, requests).
- **Owner**: The single platform operator holding the backend role `owner`. Operates through the Admin_Workspace and is out of scope for this rework.
- **Session**: The authentication context established at login and carried by an HTTP-only session cookie set by the backend. Not readable from JavaScript and not stored in `localStorage`.
- **Public_Layout**: The shared chrome component (`app/(public)/layout.tsx`) that wraps every public page with a header, search entry, browse/genre navigation, current-user indicator, and footer.
- **Public_Header**: The top navigation region of the Public_Layout containing the site brand/home link, the Search_Entry, the Browse_Nav, and the Current_User_Indicator.
- **Browse_Nav**: The navigation control in the Public_Header that lets a Reader browse novels by genre or other catalog facets.
- **Search_Entry**: The search affordance in the Public_Header that lets a Reader submit a free-text query.
- **Current_User_Indicator**: The Public_Header element that reflects authentication state, exposing a login entry point for Guests and the current user's identity plus a logout control for Public_Users.
- **Public_Footer**: The bottom chrome region of the Public_Layout containing static informational links and attribution.
- **Browse_View**: The discovery home page (`app/(public)/page.tsx`) presenting a grid of Novel_Cards with search and genre/filter controls.
- **Novel_Card**: A grid item in the Browse_View summarizing a single novel (title, author, cover/placeholder, chapter count) and, for Public_Users, a save-to-library control.
- **Novel_Detail_View**: The per-novel page (`app/(public)/novel/[slug]/page.tsx`) showing novel metadata, the chapter list, and account affordances (save-to-library, ratings/reviews) for Public_Users.
- **Reader_View**: The per-chapter reading page (`app/(public)/novel/[slug]/chapter/[chapterId]/page.tsx`) presenting chapter text and reading controls.
- **Login_View**: The public interface through which a Guest submits credentials to establish a Session.
- **Login_Prompt**: A public-scoped affordance shown to a Guest where a Public_User-only action would otherwise appear, inviting the Guest to log in.
- **Reader_Settings**: The collection of public reading preferences: font size, Reader_Theme, and content width.
- **Reader_Theme**: A public-scoped reading color scheme; one of `light`, `dark`, or `sepia`.
- **Reader_Preferences_Store**: The browser-local persistence mechanism for Reader_Settings (no account required, no server sync for Guests).
- **Library**: The Public_User's collection of saved novels, persisted server-side.
- **Reading_Progress**: The Public_User's per-novel reading position, persisted server-side.
- **Continue_Reading**: The Public_User affordance that resumes reading from the most recent Reading_Progress position.
- **Reading_History**: The Public_User's server-side log of recently read novels/chapters.
- **Review**: A Public_User's rating and optional written feedback for a novel, persisted server-side.
- **Novel_Request**: A Public_User's rate-limited request for a novel or chapter, recorded for Owner review and never auto-triggering paid translation.
- **Contributed_Credential**: A translation provider API credential (for example a Gemini or OpenAI API key) that a Public_User voluntarily submits to assist platform translation. Sent to the backend over the Session-authenticated channel, stored encrypted server-side, owned by the contributing Public_User, and never exposed in raw form to the frontend.
- **Contribution_View**: The Public_User-only surface within the Public_Reader through which a Public_User submits, inspects, and removes their Contributed_Credential.
- **Contribution_Status**: The validation state displayed for a Contributed_Credential; one of `Unchecked`, `Checking`, `Working`, or `Failed`, mirroring the Admin_Workspace provider-key validation pattern.
- **Masked_Credential_Display**: A rendering of a Contributed_Credential that shows only a short leading prefix and trailing suffix of the credential value, mirroring the admin provider-key masking, so the raw value is never displayed in full.
- **Public_API_Client**: The public-scoped data-access surface used by the Public_Reader to call the backend `GET /api/public/*` endpoints.
- **Auth_API_Client**: The data-access surface used by the Public_Reader to call the backend auth endpoints `POST /api/auth/login`, `POST /api/auth/logout`, and `GET /api/auth/me`, relying on the HTTP-only Session cookie.
- **User_API_Client**: The data-access surface used by the Public_Reader to call the authenticated `/api/user/*` endpoints (library, progress, history, reviews, requests, contributions), relying on the HTTP-only Session cookie.
- **Owner_Credential**: The owner Gemini provider token (`apiToken`) held in `lib/store.ts` and attached as a Bearer header by the existing shared `apiFetch`. Confined to the Admin_Workspace.
- **Public_Catalog_Endpoint**: The backend `GET /api/public/catalog` endpoint returning a paginated, searchable, filterable novel list.
- **Public_Novel_Endpoint**: The backend `GET /api/public/novels/{slug}` and `GET /api/public/novels/{slug}/chapters` endpoints.
- **Public_Chapter_Endpoint**: The backend `GET /api/public/novels/{slug}/chapters/{chapter_id}` endpoint returning a translated chapter for reading.
- **Auth_Endpoint**: The backend endpoints `POST /api/auth/login`, `POST /api/auth/logout`, and `GET /api/auth/me`.
- **Library_Endpoint**: The backend `GET/POST/DELETE /api/user/library/{slug}` endpoints.
- **Progress_Endpoint**: The backend `GET/PUT /api/user/progress/{slug}` endpoints.
- **History_Endpoint**: The backend `GET/POST /api/user/history` endpoints.
- **Review_Endpoint**: The backend `POST /api/user/reviews/{slug}` endpoint.
- **Request_Endpoint**: The backend `GET/POST /api/user/requests` endpoints.
- **Contribution_Endpoint**: The backend Session-authenticated `GET/POST/DELETE /api/user/contributions` endpoints used by the Public_Reader to submit, retrieve the masked status of, and remove a Public_User's Contributed_Credential.
- **UI_Primitive**: A shared presentational component under `components/ui/*` (e.g., `badge`, `button`, `input`, `panel`, `textarea`) used by both the Public_Reader and the Admin_Workspace.

## Requirements

### Requirement 1: Public Layout and Chrome

**User Story:** As a Reader, I want a consistent header, navigation, and footer across the public reader, so that I can find search, browse, and account entry points from any public page.

#### Acceptance Criteria

1. THE Public_Reader SHALL provide a Public_Layout that wraps every page under the `app/(public)/**` route group.
2. THE Public_Layout SHALL render a Public_Header that contains a brand element linking to the Browse_View, a Search_Entry, a Browse_Nav, and a Current_User_Indicator.
3. THE Public_Layout SHALL render a Public_Footer containing static informational content.
4. WHEN a Reader activates the brand element in the Public_Header, THE Public_Reader SHALL navigate to the Browse_View.
5. THE Public_Layout SHALL apply only to the `app/(public)/**` route group and SHALL NOT render within the `app/(admin)/admin/**` route group.
6. WHERE the viewport width is at most 768 pixels, THE Public_Header SHALL present the Browse_Nav, Search_Entry, and Current_User_Indicator through a collapsible control that exposes each entry point.

### Requirement 2: Browse and Discovery Home

**User Story:** As a Reader, I want to browse available novels in a grid, so that I can discover something to read.

#### Acceptance Criteria

1. WHEN a Reader opens the Browse_View, THE Public_Reader SHALL request the novel list from the Public_Catalog_Endpoint.
2. WHEN the Public_Catalog_Endpoint returns a non-empty novel list, THE Browse_View SHALL render one Novel_Card for each returned novel.
3. THE Novel_Card SHALL display the novel title, the novel author, and the translated chapter count.
4. IF a novel has no author value, THEN THE Novel_Card SHALL display the literal text "Unknown author".
5. WHEN a Reader activates a Novel_Card, THE Public_Reader SHALL navigate to the Novel_Detail_View for that novel.
6. WHILE the Public_Catalog_Endpoint request is pending, THE Browse_View SHALL display a loading indicator.
7. IF the Public_Catalog_Endpoint returns an empty novel list, THEN THE Browse_View SHALL display an empty-state message.
8. IF the Public_Catalog_Endpoint request fails, THEN THE Browse_View SHALL display an error message without exposing provider keys, authorization headers, session values, or raw stack traces.

### Requirement 3: Search and Genre Browsing

**User Story:** As a Reader, I want to search by title or author and browse by genre, so that I can narrow the catalog to novels I care about.

#### Acceptance Criteria

1. WHEN a Reader submits a query through the Search_Entry, THE Public_Reader SHALL request results from the Public_Catalog_Endpoint with the query passed as the search parameter.
2. WHEN the Public_Catalog_Endpoint returns results for a submitted query, THE Browse_View SHALL render one Novel_Card for each returned result.
3. IF a submitted query returns zero results, THEN THE Browse_View SHALL display a no-results message that includes the submitted query text.
4. WHEN a Reader selects a genre option from the Browse_Nav, THE Public_Reader SHALL request the Public_Catalog_Endpoint with the selected genre as a filter parameter.
5. WHILE a search query or genre filter is active, THE Browse_View SHALL display a control that clears the active query and filter and restores the unfiltered novel list.
6. WHERE the Public_Catalog_Endpoint reports a total count greater than the returned page size, THE Browse_View SHALL provide a control to request the next page from the Public_Catalog_Endpoint.

### Requirement 4: Novel Detail Page

**User Story:** As a Reader, I want to see a novel's details and its chapter list, so that I can choose where to start reading.

#### Acceptance Criteria

1. WHEN a Reader opens the Novel_Detail_View for a slug, THE Public_Reader SHALL request novel metadata and the chapter list from the Public_Novel_Endpoint using that slug.
2. THE Novel_Detail_View SHALL display the novel title, the novel author, and the translated chapter count.
3. THE Novel_Detail_View SHALL render the chapter list in ascending chapter order.
4. WHERE a chapter is marked translated, THE Novel_Detail_View SHALL render a control that navigates to the Reader_View for that chapter.
5. WHERE a chapter is not marked translated, THE Novel_Detail_View SHALL display a non-interactive pending indicator for that chapter.
6. THE Novel_Detail_View SHALL provide a control that navigates back to the Browse_View.
7. IF the Public_Novel_Endpoint returns a 404 status for the requested slug, THEN THE Novel_Detail_View SHALL display a not-found message.
8. IF the Public_Novel_Endpoint request fails, THEN THE Novel_Detail_View SHALL display an error message without exposing provider keys, authorization headers, session values, or raw stack traces.

### Requirement 5: Reader Chapter Experience and Navigation

**User Story:** As a Reader, I want to read a chapter and move between chapters, so that I can read a novel continuously.

#### Acceptance Criteria

1. WHEN a Reader opens the Reader_View for a slug and chapter identifier, THE Public_Reader SHALL request the chapter from the Public_Chapter_Endpoint using that slug and chapter identifier.
2. WHEN the Public_Chapter_Endpoint returns a chapter, THE Reader_View SHALL display the chapter title and the chapter text.
3. WHILE the Public_Chapter_Endpoint request is pending, THE Reader_View SHALL display a loading indicator.
4. WHERE the returned chapter has a previous chapter identifier, THE Reader_View SHALL render a control that navigates to the Reader_View for the previous chapter.
5. WHERE the returned chapter has a next chapter identifier, THE Reader_View SHALL render a control that navigates to the Reader_View for the next chapter.
6. THE Reader_View SHALL provide a control that navigates back to the Novel_Detail_View for the current novel.
7. IF the Public_Chapter_Endpoint returns a 404 status, THEN THE Reader_View SHALL display a chapter-unavailable message.
8. IF the Public_Chapter_Endpoint request fails, THEN THE Reader_View SHALL display an error message without exposing provider keys, authorization headers, session values, or raw stack traces.

### Requirement 6: Reader Typography, Theme, and Width Controls

**User Story:** As a Reader, I want to adjust font size, theme, and reading width, so that I can read comfortably.

#### Acceptance Criteria

1. THE Reader_View SHALL provide a control to increase and a control to decrease the reading font size.
2. WHEN a Reader increases or decreases the font size, THE Reader_View SHALL constrain the font size to the inclusive range of 15 pixels to 24 pixels.
3. THE Reader_View SHALL provide a control to select the Reader_Theme from `light`, `dark`, and `sepia`.
4. WHEN a Reader selects a Reader_Theme, THE Reader_View SHALL apply the selected theme's colors to the reading area.
5. THE Reader_View SHALL provide a control to select the content width from `compact`, `comfortable`, and `wide`.
6. WHEN a Reader selects a content width, THE Reader_View SHALL apply the corresponding maximum content width to the reading area.
7. WHEN a Reader changes any Reader_Settings value, THE Public_Reader SHALL persist the changed value to the Reader_Preferences_Store.
8. WHEN a Reader opens the Reader_View after previously changing Reader_Settings, THE Reader_View SHALL apply the persisted Reader_Settings values from the Reader_Preferences_Store.
9. WHERE a Public_User is authenticated and optional server-side preference persistence is enabled, THE Public_Reader MAY additionally persist Reader_Settings to the Session-scoped account; the Reader_Preferences_Store SHALL remain the primary persistence mechanism for Guests.

### Requirement 7: Public-Scoped API Access Without Owner Credential

**User Story:** As the platform owner, I want the public reader to use public and session-authenticated data surfaces without my provider credential, so that the reader cannot leak or depend on owner provider authentication.

#### Acceptance Criteria

1. THE Public_Reader SHALL retrieve Guest reader data through the Public_API_Client targeting the backend `GET /api/public/*` endpoints.
2. THE Public_API_Client, Auth_API_Client, and User_API_Client SHALL NOT attach the Owner_Credential as an Authorization header on any request.
3. WHILE an Owner_Credential value is present in the shared store, THE Public_Reader SHALL continue to issue public, auth, and user requests without that credential.
4. THE Public_Reader SHALL NOT call the owner `GET /api/novels/*` endpoints for any reader data.
5. WHEN the Public_Reader issues a request to an Auth_Endpoint or a `/api/user/*` endpoint, THE Public_Reader SHALL include the HTTP-only Session cookie with the request and SHALL NOT attach a Bearer token derived from the shared store.

### Requirement 8: Authentication and Session

**User Story:** As a Reader, I want to log in and out and see whether I am signed in, so that I can access account features securely.

#### Acceptance Criteria

1. THE Public_Header SHALL render the Current_User_Indicator reflecting the authentication state reported by `GET /api/auth/me`.
2. WHILE no Session is established, THE Current_User_Indicator SHALL present a login entry point that opens the Login_View.
3. WHEN a Guest submits valid credentials through the Login_View, THE Auth_API_Client SHALL call `POST /api/auth/login` and THE Public_Reader SHALL establish the Public_User context from the response.
4. IF `POST /api/auth/login` returns a 401 status, THEN THE Login_View SHALL display an invalid-credentials message without exposing submitted credentials or raw stack traces.
5. WHILE a Session is established, THE Current_User_Indicator SHALL display the current user's identity and a logout control.
6. WHEN a Public_User activates the logout control, THE Auth_API_Client SHALL call `POST /api/auth/logout` and THE Public_Reader SHALL return to the Guest context.
7. THE Public_Reader SHALL rely on the HTTP-only Session cookie for authentication and SHALL NOT store the Session token in JavaScript-accessible storage, including `localStorage`, `sessionStorage`, or the shared store.
8. THE Login_View SHALL provide credential-based session login and SHALL NOT depend on Google OAuth-specific controls or flows.

### Requirement 9: Gating User-Only Controls Behind Authentication

**User Story:** As a Guest, I want to be clearly prompted to log in instead of seeing broken account actions, so that I understand which features require an account.

#### Acceptance Criteria

1. WHILE the Reader is a Guest, THE Public_Reader SHALL present a Login_Prompt in place of each Public_User-only control, including save-to-library, rating/review, request, and credential-contribution controls.
2. WHEN a Guest activates a Login_Prompt, THE Public_Reader SHALL open the Login_View.
3. WHILE the Reader is a Public_User, THE Public_Reader SHALL present the Public_User-only controls in place of the Login_Prompt.
4. IF a request to a `/api/user/*` endpoint returns a 401 or 403 status, THEN THE Public_Reader SHALL present the Login_Prompt and SHALL NOT expose raw stack traces.

### Requirement 10: Save to Library

**User Story:** As a Public_User, I want to save novels to my library and remove them, so that I can keep track of novels I care about.

#### Acceptance Criteria

1. WHILE the Reader is a Public_User, THE Novel_Card and the Novel_Detail_View SHALL each render a save-to-library control.
2. WHEN a Public_User activates the save-to-library control for a novel not in the Library, THE User_API_Client SHALL call `POST /api/user/library/{slug}` for that novel's slug.
3. WHEN a Public_User activates the save-to-library control for a novel already in the Library, THE User_API_Client SHALL call `DELETE /api/user/library/{slug}` for that novel's slug.
4. WHEN the Library_Endpoint confirms an add or remove, THE Public_Reader SHALL update the save-to-library control to reflect the new Library membership state.
5. WHEN a Public_User opens a view containing a save-to-library control, THE Public_Reader SHALL request the Library membership state from `GET /api/user/library/{slug}` to set the initial control state.
6. IF a Library_Endpoint request fails, THEN THE Public_Reader SHALL display an error message and SHALL leave the displayed Library membership state unchanged.

### Requirement 11: Reading Progress and Continue Reading

**User Story:** As a Public_User, I want my reading position saved and a way to continue, so that I can resume reading where I left off.

#### Acceptance Criteria

1. WHILE the Reader is a Public_User reading a chapter in the Reader_View, WHEN the displayed chapter changes, THE User_API_Client SHALL call `PUT /api/user/progress/{slug}` with the current chapter identifier for that novel's slug.
2. WHEN a Public_User opens the Novel_Detail_View for a novel with recorded Reading_Progress, THE Public_Reader SHALL request the Reading_Progress from `GET /api/user/progress/{slug}` and SHALL render a Continue_Reading control.
3. WHEN a Public_User activates the Continue_Reading control, THE Public_Reader SHALL navigate to the Reader_View for the chapter identified by the recorded Reading_Progress.
4. WHILE the Reader is a Guest, THE Public_Reader SHALL NOT call the Progress_Endpoint.
5. IF a Progress_Endpoint request fails, THEN THE Public_Reader SHALL display the reading content without the Continue_Reading affordance and SHALL NOT expose raw stack traces.

### Requirement 12: Reading History

**User Story:** As a Public_User, I want to see novels and chapters I have read recently, so that I can find my way back to them.

#### Acceptance Criteria

1. WHILE the Reader is a Public_User reading a chapter in the Reader_View, WHEN the chapter is displayed, THE User_API_Client SHALL call `POST /api/user/history` to record the read event.
2. WHEN a Public_User opens the Reading_History view, THE User_API_Client SHALL request entries from `GET /api/user/history`.
3. WHEN the History_Endpoint returns a non-empty entry list, THE Reading_History view SHALL render one entry for each returned record in most-recent-first order.
4. IF the History_Endpoint returns an empty entry list, THEN THE Reading_History view SHALL display an empty-state message.
5. WHILE the Reader is a Guest, THE Public_Reader SHALL NOT call the History_Endpoint.

### Requirement 13: Ratings and Reviews

**User Story:** As a Public_User, I want to rate and review a novel, so that I can share feedback.

#### Acceptance Criteria

1. WHILE the Reader is a Public_User on the Novel_Detail_View, THE Public_Reader SHALL render a rating-and-review control.
2. WHEN a Public_User submits a rating and optional written feedback, THE User_API_Client SHALL call `POST /api/user/reviews/{slug}` with the rating and feedback for that novel's slug.
3. WHEN the Review_Endpoint confirms submission, THE Public_Reader SHALL display a submission-confirmed message.
4. IF the submitted rating is outside the accepted rating range, THEN THE Public_Reader SHALL display a validation message and SHALL NOT call the Review_Endpoint.
5. IF the Review_Endpoint request fails, THEN THE Public_Reader SHALL display an error message without exposing raw stack traces.

### Requirement 14: Novel and Chapter Requests

**User Story:** As a Public_User, I want to request a novel or chapter, so that I can ask the owner to add content I want.

#### Acceptance Criteria

1. WHILE the Reader is a Public_User, THE Public_Reader SHALL render a request control for submitting a Novel_Request.
2. WHEN a Public_User submits a Novel_Request, THE User_API_Client SHALL call `POST /api/user/requests` with the request type and request details.
3. WHEN the Request_Endpoint confirms submission, THE Public_Reader SHALL display a request-submitted message.
4. THE Public_Reader SHALL present a submitted Novel_Request as a request for Owner review and SHALL NOT represent it as triggering translation.
5. IF the Request_Endpoint returns a status indicating the rate limit has been exceeded, THEN THE Public_Reader SHALL display a rate-limit message and SHALL NOT resubmit the Novel_Request automatically.
6. WHEN a Public_User opens the request list, THE User_API_Client SHALL request the Public_User's submitted requests from `GET /api/user/requests`.

### Requirement 15: Public-Scoped Theming Isolated From Admin

**User Story:** As the platform owner, I want the reader theme to be independent of the admin dark-mode mechanism, so that reader theming never changes admin appearance and vice versa.

#### Acceptance Criteria

1. THE Reader_Theme SHALL be applied through public-scoped styling that does not toggle the `dark` class on the document root element.
2. WHEN a Reader selects the `dark` Reader_Theme, THE Public_Reader SHALL NOT modify the Admin_Workspace `darkMode` state in the shared store.
3. THE Public_Reader SHALL store Reader_Theme separately from the Admin_Workspace `darkMode` value.
4. WHILE the Admin_Workspace `darkMode` value is enabled, THE Reader_View SHALL render using the selected Reader_Theme rather than the admin dark-mode palette.

### Requirement 16: Shared Component Reuse Without Admin Regression

**User Story:** As the platform owner, I want the public redesign to reuse shared UI primitives without breaking admin, so that the admin workspace remains visually and functionally unchanged.

#### Acceptance Criteria

1. WHERE the Public_Reader reuses a UI_Primitive, THE Public_Reader SHALL consume that primitive without modifying its default styling contract.
2. IF the redesign requires a public-only visual variant, THEN THE Public_Reader SHALL apply that variant through public-scoped composition rather than altering the shared UI_Primitive defaults.
3. THE Public_Reader SHALL NOT modify files under `app/(admin)/admin/**` or `components/admin/*`.
4. WHEN the redesign is complete, THE Admin_Workspace SHALL render its existing tables and controls with unchanged styling and behavior.
5. THE Public_Reader SHALL pass the existing `npm run typecheck` and `npm run build` checks.


### Requirement 17: Public Contribution of Translation Provider Credentials

**User Story:** As a Public_User, I want to contribute my own translation provider API credential, so that I can help the platform translate novels.

#### Acceptance Criteria

1. WHILE the Reader is a Public_User, THE Public_Reader SHALL render a Contribution_View that provides a control to submit a Contributed_Credential and, where a Contributed_Credential already exists, a control to remove it.
2. WHILE the Reader is a Guest, THE Public_Reader SHALL present a Login_Prompt in place of the Contribution_View controls.
3. WHEN a Guest activates the Contribution_View Login_Prompt, THE Public_Reader SHALL open the Login_View.
4. THE Public_Reader SHALL submit a Contributed_Credential only when a Public_User explicitly submits one through the Contribution_View.
5. WHEN a Public_User submits a Contributed_Credential through the Contribution_View, THE User_API_Client SHALL call `POST /api/user/contributions` over the Session-authenticated channel and SHALL include the HTTP-only Session cookie with the request.
6. THE Public_Reader SHALL NOT persist a raw Contributed_Credential value in JavaScript-accessible storage, including `localStorage`, `sessionStorage`, or the shared store.
7. WHEN the Contribution_View displays a Contributed_Credential, THE Public_Reader SHALL render the credential through Masked_Credential_Display showing only a short leading prefix and trailing suffix.
8. WHEN a Public_User opens the Contribution_View, THE User_API_Client SHALL request the current Contributed_Credential status from `GET /api/user/contributions` and THE Contribution_View SHALL display the returned Contribution_Status.
9. THE Contribution_View SHALL display the Contribution_Status as one of `Unchecked`, `Checking`, `Working`, or `Failed`.
10. WHILE backend validation of a Contributed_Credential is in progress, THE Contribution_View SHALL display the `Checking` Contribution_Status.
11. WHEN a Public_User activates the remove control for an existing Contributed_Credential, THE User_API_Client SHALL call `DELETE /api/user/contributions` and THE Public_Reader SHALL update the Contribution_View to reflect that no Contributed_Credential is present.
12. THE Contribution_View SHALL present that a Contributed_Credential is used to assist translation per backend policy and SHALL NOT represent that contribution grants access to any other Public_User's Contributed_Credential or to the Owner_Credential.
13. THE Contribution_View SHALL NOT display any other Public_User's Contributed_Credential or the Owner_Credential.
14. IF a Contribution_Endpoint request fails, THEN THE Public_Reader SHALL display an error message without exposing the raw Contributed_Credential, the Owner_Credential, authorization headers, session values, or raw stack traces.
15. IF a request to the Contribution_Endpoint returns a 401 or 403 status, THEN THE Public_Reader SHALL present the Login_Prompt and SHALL NOT expose raw stack traces.
