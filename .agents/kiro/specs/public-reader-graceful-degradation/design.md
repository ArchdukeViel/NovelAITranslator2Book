# Reader Asset Boundary Design

Prefer deleting duplicate route-local fallback code. Shared boundary receives
safe display metadata and fallback content; it never fetches directly or sees
storage paths. Existing generated bookplate remains cover fallback. Route text
and navigation render independently from optional assets.

If current shared state components already provide exact behavior, close through
focused cross-route tests instead of adding another wrapper.
