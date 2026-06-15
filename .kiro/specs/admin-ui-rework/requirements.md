# Requirements Document

## Introduction

This feature is a UI rework of the **admin/owner workspace only** — the routes under `frontend/app/(admin)/admin/**` of the Next.js 15 / React 19 / TypeScript frontend, and the admin-only components under `components/admin/*`. The goal is to give the single platform owner a consistent, dense, and predictable operations workspace: a refreshed admin shell (sidebar + topbar with collapse and active-state behavior), an owner login/logout experience with a current-owner indicator, consistent page-heading / loading / empty / error patterns across pages, consistent data-table density and column sorting across the activity, library, requests, and users surfaces, consistent modal dialog and confirmation behavior, a clear provider-credential/settings experience with masked tokens and visible validation status, owner-facing controls to configure and drive scheduler, QA, and provider-policy behavior through the backend, owner oversight of user-contributed provider credentials with masked display and validation status, an owner user-management surface, owner review and approval of user-submitted requests, audit-notice surfacing for dangerous actions, and an admin dark-mode mechanism that stays isolated from the public reader theme.

Per the current platform state (`docs/current_state.md`, updated 2026-06-09) and the platform expansion roadmap (`docs/roadmap/public-platform-expansion.md`), the platform now runs a live **guest / user / owner** role model backed by PostgreSQL (Supabase) as the system of record, with Redis/RQ background workers and `AuditLog` / `SystemSetting` models. Owner authentication is via **HTTP-only session cookies** established through `POST /api/auth/login`, ended through `POST /api/auth/logout`, and inspected through `GET /api/auth/me`; the backend enforces owner-only operations with `require_role("owner")` over the `/api/admin/*` surface. Registered users (role `user`) now exist and can submit requests, which the owner reviews. Public **contribution** is now allowed platform-wide: registered users can contribute their own translation provider API credentials, which are stored encrypted server-side, and the Owner oversees those contributed credentials from the Admin_Workspace. This rework updates the admin workspace to that reality: the session cookie — not a stored bearer token — authenticates admin requests, and the provider API key (the Gemini token) is treated strictly as owner-managed provider configuration, not as the authentication mechanism.

This rework is strictly scoped to the admin surface. It MUST NOT redesign, restyle, or regress the public reader under `frontend/app/(public)/**`, and it is **not** a WTR-LAB-style public redesign — the public-reader-rework spec owns that work and does not apply here. Because the admin workspace and the public reader share code (`lib/api.ts`, `lib/store.ts`, `components/ui/*`, `app/globals.css`, `tailwind.config.ts`, and the root `app/layout.tsx`), this document also captures foundation requirements that protect the shared boundary so that admin changes do not break public usage.

The following remain **blocked** and are explicitly out of scope: multi-admin teams, organizations, billing, batch mode, and role assignment beyond the single-owner model. The Admin_Workspace MUST NOT expose raw provider API keys, raw contributed credentials, authorization headers, session tokens, cookies, or stack traces in the UI, logs, or error envelopes. The Admin_Workspace MAY own, surface, and configure scheduler, QA, and provider-policy control surfaces that drive backend-owned controls through the Admin_API; backend workers still perform the heavy translation, crawl, scheduler, and QA execution. Frontend route hiding is NOT the security boundary — backend `require_role("owner")` enforcement is.

## Glossary

- **Admin_Workspace**: The owner-facing application served from the `app/(admin)/admin/**` route group; the subject of this rework.
- **Public_Reader**: The anonymous reader application served from the `app/(public)/**` route group. Out of scope for modification; protected by foundation requirements. Owned by the separate public-reader-rework spec.
- **Owner**: The single authenticated platform operator who administers the Admin_Workspace. Exactly one owner exists (role `owner`, seeded via backend bootstrap secret). Registered users (role `user`) and anonymous guests also exist on the platform but do not access the Admin_Workspace.
- **Auth_API**: The backend authentication endpoints `POST /api/auth/login` (owner secret-based bootstrap login), `POST /api/auth/logout`, and `GET /api/auth/me`, used to establish, end, and inspect the Owner_Session.
- **Owner_Session**: The authenticated owner session established by the Auth_API and carried by the HTTP-only Session_Cookie.
- **Session_Cookie**: The HTTP-only, browser-managed cookie that carries the Owner_Session. It is not readable by JavaScript and is not stored in any JavaScript-accessible storage.
- **Owner_Login_View**: The admin login surface that collects the owner login secret and calls `POST /api/auth/login`.
- **Logout_Control**: The Admin_Topbar control that ends the Owner_Session by calling `POST /api/auth/logout`.
- **Owner_Session_Indicator**: The Admin_Topbar element that displays the current authenticated owner identity, sourced from `GET /api/auth/me`.
- **Role_Enforcement**: Backend authorization applied via `require_role("owner")` over the Admin_API; the actual security boundary for owner-only operations.
- **Admin_API**: The backend owner endpoints under `/api/admin/*` (crawl, translation, providers, settings, activity, user management) guarded by Role_Enforcement.
- **Admin_API_Client**: The admin-scoped data-access surface within `lib/api.ts` that calls the Auth_API and Admin_API with the Session_Cookie included on each request; it does not attach a provider key or bearer token as the authentication credential.
- **Admin_Shell**: The persistent layout chrome (`components/admin/admin-shell.tsx`) rendered by `app/(admin)/admin/layout.tsx`, composed of the Admin_Sidebar and the Admin_Topbar, that wraps every admin page.
- **Admin_Sidebar**: The fixed left navigation region of the Admin_Shell containing the brand element, the primary navigation links, and the link to the Public_Reader.
- **Admin_Topbar**: The sticky top region of the Admin_Shell containing the current-section indicator, the Dark_Mode_Toggle, the Credential_Status_Indicator, the Owner_Session_Indicator, and the Logout_Control.
- **Nav_Item**: A single primary navigation entry in the Admin_Sidebar (Home, Add Novel, Library, Activity Log, Requests, Users, Editor, Settings) that links to an admin route.
- **Active_Nav_State**: The visual treatment applied to the Nav_Item whose route matches the current path or a descendant of the current path.
- **Sidebar_Collapsed_State**: The boolean UI state controlling whether the Admin_Sidebar is rendered in its narrow (icon-only) form or its expanded (icon-plus-label) form.
- **Page_Heading**: The shared heading component (`components/admin/page-heading.tsx`) presenting a page title and optional description at the top of an admin page.
- **Loading_State**: The visual indicator an admin page or table presents while a backend request is pending.
- **Empty_State**: The shared component (`components/admin/empty-state.tsx`) presenting a message when a data set is empty.
- **Error_State**: The shared component (`components/admin/error-banner.tsx`) presenting a backend or application error message in an admin page or table.
- **Admin_Data_Table**: A dense tabular presentation used on the Activity_View, Library_View, Requests_View, and Users_View, with a header row, sortable columns, and consistent row density.
- **Sortable_Column**: An Admin_Data_Table column whose header (`components/admin/sortable-header.tsx`) lets the Owner reorder rows by that column's value.
- **Sort_Direction**: The current ordering of a sorted Admin_Data_Table column; one of `asc` or `desc`.
- **Activity_View**: The admin activity log page (`app/(admin)/admin/activity/**`) presenting the activity records.
- **Library_View**: The admin library page (`app/(admin)/admin/library/**`) presenting the managed novel collection.
- **Requests_View**: The admin requests page (`app/(admin)/admin/requests/**`) presenting user-submitted novel and chapter requests for owner review.
- **Users_View**: The admin user-management page presenting registered User_Records and their User_Roles for owner review and single-owner administration.
- **User_Record**: A registered platform user (role `user` or `owner`) shown in the Users_View.
- **User_Role**: The role assigned to a User_Record; one of `guest`, `user`, `owner`.
- **Novel_Request**: A user-submitted request for a novel or chapter, presented in the Requests_View for owner review.
- **Request_Status**: The review state of a Novel_Request (for example, pending, approved, rejected, or completed).
- **Settings_View**: The admin settings page (`app/(admin)/admin/settings/page.tsx`) presenting the Provider_Credential controls and runtime configuration controls.
- **Modal_Dialog**: A centered overlay surface rendered by the shared dialog primitive (`components/admin/dialog-shell.tsx`) with a title, body, and optional footer.
- **Confirm_Dialog**: The shared confirmation dialog (`components/admin/confirm-dialog.tsx`) built on the Modal_Dialog that requests Owner confirmation before an action, with confirm and cancel controls and an optional destructive treatment.
- **Provider_Credential**: The Gemini provider API key the Owner configures in the Settings_View. It is provider configuration managed through the Admin_API; it is NOT the authentication mechanism for the Admin_Workspace.
- **Credential_Status_Indicator**: The Admin_Topbar element that summarizes the active Provider_Credential status (for example, the active provider label or "None").
- **Masked_Token**: A display form of a provider credential — the owner's Provider_Credential or a Contributed_Credential — that reveals at most a short prefix and suffix and obscures the remaining characters.
- **Token_Validation_Status**: The validation state of a Provider_Credential or Contributed_Credential entry; one of `Unchecked`, `Checking`, `Working`, or `Failed`.
- **Audit_Log**: The backend record (`AuditLog` model) of a dangerous owner action, written by the Admin_API.
- **Audit_Notice**: The UI affordance that informs the Owner a dangerous action is recorded to the Audit_Log.
- **Provider_Policy**: The owner-configured backend policy, managed through the Admin_API, that governs how provider credentials — the owner's Provider_Credential and enabled Contributed_Credentials — participate in the translation provider pool.
- **Scheduler_Controls**: The owner-facing control surface in the Admin_Workspace for configuring backend scheduler behavior through the Admin_API.
- **QA_Controls**: The owner-facing control surface in the Admin_Workspace for configuring backend QA (quality-assurance) behavior through the Admin_API.
- **Contributed_Credential**: A translation provider API credential donated by a registered User, stored encrypted server-side, surfaced to the Owner for oversight in the Admin_Workspace. It is distinct from the owner's own Provider_Credential.
- **Contributed_Credential_State**: Whether a Contributed_Credential is enabled or disabled for use in translation, controlled by the Owner through the Admin_API.
- **Dark_Mode_Toggle**: The Admin_Topbar control that switches the Admin_Workspace between light and dark appearance.
- **Admin_Dark_Mode**: The Admin_Workspace appearance state (`darkMode` in `lib/store.ts`) applied by toggling the `dark` class on the document root element.
- **Reader_Theme**: The public-scoped reading color scheme (`readerTheme` in `lib/store.ts`) owned by the public-reader-rework spec; one of `light`, `dark`, or `sepia`.
- **UI_State_Store**: The shared zustand store (`lib/store.ts`) persisting admin UI preferences (Sidebar_Collapsed_State, Admin_Dark_Mode) and public reader preferences under a single storage key. The Owner_Session is NOT stored here; it is carried only by the HTTP-only Session_Cookie.
- **UI_Primitive**: A shared presentational component under `components/ui/*` (for example `badge`, `button`, `input`, `panel`, `textarea`) used by both the Admin_Workspace and the Public_Reader.

## Requirements

### Requirement 1: Admin Shell Navigation Refresh

**User Story:** As the Owner, I want a refreshed admin shell with a sidebar and topbar, so that I can navigate the workspace consistently from every admin page.

#### Acceptance Criteria

1. THE Admin_Workspace SHALL render the Admin_Shell as the layout wrapper for every page under the `app/(admin)/admin/**` route group.
2. THE Admin_Shell SHALL render an Admin_Sidebar containing a brand element, one Nav_Item for each primary admin destination, and a link to the Public_Reader.
3. THE Admin_Shell SHALL render an Admin_Topbar containing a current-section indicator, the Dark_Mode_Toggle, the Credential_Status_Indicator, the Owner_Session_Indicator, and the Logout_Control.
4. WHEN the Owner activates a Nav_Item, THE Admin_Workspace SHALL navigate to that Nav_Item's admin route.
5. WHEN the Owner activates the brand element in the Admin_Sidebar, THE Admin_Workspace SHALL navigate to the admin dashboard route.
6. THE Admin_Shell SHALL render only within the `app/(admin)/admin/**` route group and SHALL NOT render within the `app/(public)/**` route group.

### Requirement 2: Active Navigation State

**User Story:** As the Owner, I want the current section highlighted in the sidebar, so that I always know which page I am viewing.

#### Acceptance Criteria

1. WHEN the current path equals a Nav_Item route, THE Admin_Sidebar SHALL apply the Active_Nav_State to that Nav_Item.
2. WHEN the current path is a descendant of a Nav_Item route, THE Admin_Sidebar SHALL apply the Active_Nav_State to that Nav_Item.
3. WHILE the Active_Nav_State is applied to a Nav_Item, THE Admin_Topbar current-section indicator SHALL display that Nav_Item's label.
4. WHEN the current path matches more than one Nav_Item route prefix, THE Admin_Sidebar SHALL apply the Active_Nav_State to the most specific matching Nav_Item.
5. THE Admin_Sidebar SHALL apply the Active_Nav_State to at most one Nav_Item at a time.

### Requirement 3: Sidebar Collapse Behavior

**User Story:** As the Owner, I want to collapse the sidebar, so that I can give dense data tables more horizontal space.

#### Acceptance Criteria

1. THE Admin_Sidebar SHALL provide a control that toggles the Sidebar_Collapsed_State.
2. WHEN the Owner activates the collapse control, THE Admin_Shell SHALL switch the Sidebar_Collapsed_State to its opposite value.
3. WHILE the Sidebar_Collapsed_State is collapsed, THE Admin_Sidebar SHALL render each Nav_Item as an icon without its text label and SHALL expose the label through an accessible title attribute.
4. WHILE the Sidebar_Collapsed_State is collapsed, THE Admin_Shell SHALL reduce the main content area's left offset to match the narrow sidebar width.
5. WHEN the Owner changes the Sidebar_Collapsed_State, THE Admin_Workspace SHALL persist the changed value to the UI_State_Store.
6. WHEN the Owner loads any admin page after a prior change to the Sidebar_Collapsed_State, THE Admin_Shell SHALL render the Admin_Sidebar using the persisted Sidebar_Collapsed_State value.

### Requirement 4: Owner Authentication and Session

**User Story:** As the Owner, I want to log in and out of the admin workspace and see who I am signed in as, so that only I can operate it and unauthenticated access is rejected.

#### Acceptance Criteria

1. IF an unauthenticated visitor requests an admin route, THEN THE Admin_Workspace SHALL present the Owner_Login_View.
2. WHEN the Owner submits a valid login secret in the Owner_Login_View, THE Admin_Workspace SHALL call `POST /api/auth/login` and SHALL establish the Owner_Session on success.
3. IF the Owner submits an invalid login secret, THEN THE Admin_Workspace SHALL display an Error_State and SHALL NOT establish an Owner_Session.
4. THE Admin_Workspace SHALL carry the Owner_Session through the HTTP-only Session_Cookie and SHALL NOT store the session token in any JavaScript-accessible storage.
5. THE Admin_Topbar SHALL render the Owner_Session_Indicator using the owner identity returned by `GET /api/auth/me`.
6. WHEN the Owner activates the Logout_Control, THE Admin_Workspace SHALL call `POST /api/auth/logout` and SHALL present the Owner_Login_View.
7. IF the Admin_API returns a 401 or 403 response for an admin request, THEN THE Admin_Workspace SHALL treat the Owner_Session as ended and SHALL present the Owner_Login_View.
8. THE Admin_Workspace SHALL rely on backend Role_Enforcement as the authorization boundary and SHALL treat sidebar route hiding as a presentation concern rather than a security control.

### Requirement 5: Consistent Page Heading Pattern

**User Story:** As the Owner, I want every admin page to present its title the same way, so that the workspace feels coherent.

#### Acceptance Criteria

1. THE Admin_Workspace SHALL render a Page_Heading at the top of each admin page content area.
2. THE Page_Heading SHALL display a page title.
3. WHERE a page supplies a description, THE Page_Heading SHALL display the description beneath the title.
4. THE Admin_Workspace SHALL render the Page_Heading using a single shared heading component across all admin pages.

### Requirement 6: Consistent Loading, Empty, and Error Patterns

**User Story:** As the Owner, I want loading, empty, and error feedback to look and behave the same across pages, so that I can interpret system state at a glance.

#### Acceptance Criteria

1. WHILE a backend request for an admin page or table is pending, THE Admin_Workspace SHALL display a Loading_State for that page or table.
2. WHEN a backend request returns an empty data set, THE Admin_Workspace SHALL display an Empty_State with a descriptive message.
3. IF a backend request for an admin page or table fails, THEN THE Admin_Workspace SHALL display an Error_State with a human-readable message.
4. THE Error_State SHALL present the error message without exposing provider API keys, authorization headers, session tokens, cookies, or raw stack traces.
5. THE Admin_Workspace SHALL render the Loading_State, Empty_State, and Error_State using shared components across all admin pages.
6. WHERE a data set is presented inside an Admin_Data_Table, THE Empty_State SHALL render as a single row spanning all table columns.

### Requirement 7: Consistent Data-Table Density and Sorting

**User Story:** As the Owner, I want the activity, library, requests, and users tables to share the same density and sorting behavior, so that I can scan and reorder records the same way everywhere.

#### Acceptance Criteria

1. THE Admin_Workspace SHALL render the Activity_View, the Library_View, the Requests_View, and the Users_View record lists as Admin_Data_Tables that share a common row density and header styling.
2. THE Admin_Data_Table SHALL render each Sortable_Column header using a single shared sortable-header component.
3. WHEN the Owner activates a Sortable_Column header, THE Admin_Data_Table SHALL reorder its rows by that column's value in the current Sort_Direction.
4. WHEN the Owner activates a Sortable_Column header that is already the active sort column, THE Admin_Data_Table SHALL invert the Sort_Direction.
5. WHEN the Owner activates a Sortable_Column header that is not the active sort column, THE Admin_Data_Table SHALL set that column as the active sort column and apply the column's default Sort_Direction.
6. THE Admin_Data_Table SHALL display a direction indicator on the active Sortable_Column header.
7. THE Admin_Data_Table SHALL provide consistent density and sorting behavior across the Activity_View, the Library_View, the Requests_View, and the Users_View.

### Requirement 8: Consistent Dialog and Confirmation Behavior

**User Story:** As the Owner, I want modal dialogs and confirmations to behave consistently, so that destructive actions are predictable and reversible up to the point of confirmation.

#### Acceptance Criteria

1. THE Admin_Workspace SHALL render every modal overlay using the shared Modal_Dialog component.
2. THE Modal_Dialog SHALL display a title and SHALL render as a centered overlay above the page content.
3. WHERE an action requires Owner confirmation, THE Admin_Workspace SHALL present a Confirm_Dialog with a confirm control and a cancel control.
4. WHEN the Owner activates the cancel control of a Confirm_Dialog, THE Admin_Workspace SHALL dismiss the Confirm_Dialog without performing the action.
5. WHEN the Owner activates the confirm control of a Confirm_Dialog, THE Admin_Workspace SHALL perform the confirmed action.
6. WHERE a Confirm_Dialog represents a destructive action, THE Confirm_Dialog SHALL render the confirm control with a destructive visual treatment.
7. WHILE a confirmed action is pending, THE Confirm_Dialog SHALL disable the confirm control and the cancel control.

### Requirement 9: Provider Credential and Settings Experience

**User Story:** As the Owner, I want to configure, validate, activate, and remove the Gemini provider API key with clear status, so that translation has provider access — separately from how I authenticate to the admin workspace.

#### Acceptance Criteria

1. THE Settings_View SHALL provide a control for the Owner to enter and store a Provider_Credential through the Admin_API.
2. WHEN the Settings_View displays a stored Provider_Credential, THE Settings_View SHALL render it as a Masked_Token.
3. THE Masked_Token SHALL reveal at most a short prefix and a short suffix of the Provider_Credential and SHALL obscure the remaining characters.
4. THE Settings_View SHALL display the Token_Validation_Status for each stored Provider_Credential.
5. WHEN the Owner triggers validation of a Provider_Credential, THE Settings_View SHALL set the Token_Validation_Status to `Checking` until the backend validation result is received.
6. WHEN backend validation reports the Provider_Credential as working, THE Settings_View SHALL set the Token_Validation_Status to `Working`.
7. IF backend validation reports the Provider_Credential as failed, THEN THE Settings_View SHALL set the Token_Validation_Status to `Failed` and SHALL display the failure message without exposing the raw Provider_Credential value, authorization headers, session tokens, or stack traces.
8. WHEN the Owner activates the control to use a stored Provider_Credential, THE Admin_Workspace SHALL set that credential as the active Provider_Credential through the Admin_API.
9. WHEN the Owner activates the control to remove a stored Provider_Credential, THE Admin_Workspace SHALL delete that credential through the Admin_API.
10. THE Admin_Workspace SHALL treat the Provider_Credential as provider configuration and SHALL NOT use the Provider_Credential as the authentication credential for admin requests.
11. THE Credential_Status_Indicator SHALL summarize the active Provider_Credential without rendering the raw credential value.

### Requirement 10: Owner User Management

**User Story:** As the Owner, I want to view registered users and their roles and perform owner-only user actions, so that I can administer the single-owner platform consistent with the permission matrix.

#### Acceptance Criteria

1. WHILE the Owner_Session is active, THE Admin_Workspace SHALL provide access to the Users_View.
2. THE Users_View SHALL retrieve User_Records and their User_Roles through the Admin_API.
3. THE Users_View SHALL present each User_Record with its email and User_Role.
4. WHERE the Owner performs a user-management action, THE Admin_Workspace SHALL invoke the corresponding Admin_API endpoint guarded by Role_Enforcement.
5. THE Users_View SHALL NOT present multi-admin, team, organization, billing, or role-assignment-beyond-single-owner controls.
6. IF a non-owner request reaches a user-management endpoint, THEN the Admin_API SHALL reject the request through Role_Enforcement.

### Requirement 11: Requests Review and Approval

**User Story:** As the Owner, I want to review user-submitted novel and chapter requests and approve or run them, so that users can request content without automatically triggering paid translation.

#### Acceptance Criteria

1. THE Requests_View SHALL retrieve user-submitted Novel_Requests through the Admin_API.
2. THE Requests_View SHALL present each Novel_Request with its Request_Status in an Admin_Data_Table.
3. WHEN the Owner approves or rejects a Novel_Request, THE Admin_Workspace SHALL update the Request_Status through the corresponding Admin_API endpoint.
4. THE Admin_Workspace SHALL NOT automatically trigger a paid translation in response to a submitted Novel_Request.
5. WHEN the Owner runs an approved Novel_Request, THE Admin_Workspace SHALL initiate the work only through an explicit Owner-invoked Admin_API call.

### Requirement 12: Audit Logging Surfacing

**User Story:** As the Owner, I want to be informed that dangerous actions are recorded, so that I have accountability for destructive operations.

#### Acceptance Criteria

1. WHERE the Owner confirms a dangerous action such as deleting or unpublishing content, THE Confirm_Dialog SHALL present an Audit_Notice indicating the action is recorded to the Audit_Log.
2. THE Admin_Workspace SHALL rely on the Admin_API to write the Audit_Log record for dangerous owner actions.
3. THE Audit_Notice SHALL NOT expose session tokens, cookies, provider API keys, or stack traces.

### Requirement 13: Admin Dark Mode Isolated From Public Reader Theme

**User Story:** As the Owner, I want the admin dark mode to be independent of the public reader theme, so that changing one never alters the other.

#### Acceptance Criteria

1. THE Dark_Mode_Toggle SHALL switch the Admin_Dark_Mode state between enabled and disabled.
2. WHEN the Admin_Dark_Mode state is enabled, THE Admin_Workspace SHALL apply dark appearance by adding the `dark` class to the document root element.
3. WHEN the Admin_Dark_Mode state is disabled, THE Admin_Workspace SHALL remove the `dark` class from the document root element.
4. WHEN the Owner toggles the Admin_Dark_Mode state, THE Admin_Workspace SHALL NOT modify the Reader_Theme value in the UI_State_Store.
5. THE Admin_Workspace SHALL store the Admin_Dark_Mode value separately from the Reader_Theme value.
6. WHEN the Owner changes the Admin_Dark_Mode state, THE Admin_Workspace SHALL persist the changed value to the UI_State_Store.

### Requirement 14: Admin Session and State Scoping

**User Story:** As the Owner, I want admin session and state to stay scoped to the admin surface, so that nothing leaks into the public reader.

#### Acceptance Criteria

1. THE Admin_Workspace SHALL retrieve owner data through the Admin_API_Client targeting the Admin_API.
2. THE Admin_API_Client SHALL authenticate admin-scoped requests using the HTTP-only Session_Cookie and SHALL NOT attach the Provider_Credential as the authentication credential.
3. THE Admin_Workspace SHALL NOT render multi-admin, team-management, role-assignment-beyond-single-owner, organization, or billing controls.
4. THE Admin_Workspace SHALL confine the Sidebar_Collapsed_State and the Admin_Dark_Mode value to admin-scoped fields of the UI_State_Store.
5. WHEN the Public_Reader surface is rendered, THE Admin_Workspace SHALL NOT require the Owner_Session, the Sidebar_Collapsed_State, or the Admin_Dark_Mode value to be present.

### Requirement 15: Shared Component Reuse Without Public Regression

**User Story:** As the Owner, I want the admin rework to reuse shared UI primitives without breaking the public reader, so that the public surface remains visually and functionally unchanged.

#### Acceptance Criteria

1. WHERE the Admin_Workspace reuses a UI_Primitive, THE Admin_Workspace SHALL consume that primitive without modifying its default styling contract.
2. IF the rework requires an admin-only visual variant, THEN THE Admin_Workspace SHALL apply that variant through admin-scoped composition rather than altering the shared UI_Primitive defaults.
3. THE Admin_Workspace SHALL NOT modify files under `app/(public)/**`.
4. WHEN the rework is complete, THE Public_Reader SHALL render its existing pages and controls with unchanged styling and behavior.
5. THE Admin_Workspace SHALL pass the existing `npm run typecheck` and `npm run build` checks.

### Requirement 16: Owner Control of Scheduler, QA, and Provider Policy

**User Story:** As the Owner, I want to configure and drive scheduler, QA, and provider-policy behavior from the admin workspace, so that I can manage how translation work is scheduled, quality-checked, and routed across providers.

#### Acceptance Criteria

1. THE Admin_Workspace SHALL present the current Scheduler_Controls, QA_Controls, and Provider_Policy configuration retrieved from the Admin_API.
2. THE Admin_Workspace SHALL provide owner-facing Scheduler_Controls that configure backend scheduler behavior through the Admin_API.
3. THE Admin_Workspace SHALL provide owner-facing QA_Controls that configure backend QA behavior through the Admin_API.
4. THE Admin_Workspace SHALL provide owner-facing controls that configure the Provider_Policy through the Admin_API.
5. WHEN the Owner submits a Scheduler_Controls, QA_Controls, or Provider_Policy configuration change, THE Admin_Workspace SHALL persist the change through the corresponding Admin_API endpoint guarded by Role_Enforcement.
6. THE Admin_Workspace SHALL rely on backend workers to perform scheduler, QA, and translation execution.
7. IF a Scheduler_Controls, QA_Controls, or Provider_Policy configuration request fails, THEN THE Admin_Workspace SHALL display an Error_State without exposing provider API keys, contributed credentials, authorization headers, session tokens, cookies, or stack traces.

### Requirement 17: Owner Oversight of Contributed Credentials

**User Story:** As the Owner, I want to oversee user-contributed provider credentials, so that I can control which contributed credentials participate in translation while never exposing raw keys.

#### Acceptance Criteria

1. THE Admin_Workspace SHALL retrieve Contributed_Credential entries through the Admin_API.
2. THE Admin_Workspace SHALL present each Contributed_Credential with the contributing user identity, its Token_Validation_Status, and its Contributed_Credential_State.
3. THE Admin_Workspace SHALL render each Contributed_Credential as a Masked_Token and SHALL NOT display the raw contributed credential value.
4. WHEN the Owner enables or disables a Contributed_Credential for use in translation, THE Admin_Workspace SHALL update the Contributed_Credential_State through the Admin_API.
5. WHEN the Owner triggers validation of a Contributed_Credential, THE Admin_Workspace SHALL set its Token_Validation_Status to `Checking` until the backend validation result is received.
6. WHEN backend validation reports a Contributed_Credential as working, THE Admin_Workspace SHALL set its Token_Validation_Status to `Working`.
7. IF backend validation reports a Contributed_Credential as failed, THEN THE Admin_Workspace SHALL set its Token_Validation_Status to `Failed` and SHALL display the failure message without exposing the raw contributed credential value, authorization headers, session tokens, cookies, or stack traces.
8. THE Admin_Workspace SHALL provide controls for the Owner to configure how Contributed_Credentials participate in the Provider_Policy through the Admin_API.
9. THE Admin_Workspace SHALL NOT display raw contributed keys, authorization headers, session tokens, cookies, or stack traces for any Contributed_Credential.
