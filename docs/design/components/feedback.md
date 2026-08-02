# Component Contract — Feedback & Status

## Specifications

- **Status Badges ("Lantern Badges"):** Rounded pill shape (999px radius). Mapped deterministically to Status roles (`--primary` for ongoing, `--info` for completed, `--warning` for hiatus, `--muted` for dropped).
- **Toast Notifications:** Fixed top-right (desktop) / top-center (mobile) toast notifications rendered at z-index 60. Self-dismiss after 4 seconds or manual close.
- **Alert Banners:** Inline contextual messages using semantic status background and text tokens (`--info-text`, `--warning-text`, `--success-text`, `--destructive`).
- **Skeletons:** Animated pulse loading blocks matching target component dimensions.
