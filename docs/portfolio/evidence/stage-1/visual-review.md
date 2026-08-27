# Stage 1 Visual Review Loop

The first real-service screenshot pass was inspected before the final capture set. The following five visible issues were found and addressed:

1. Real image URLs were being caught by the Vite `/assets` proxy and displayed as broken images. The proxy was removed; Vite public assets now load directly.
2. The mobile Tutor card was collapsed without a reachable trigger. A visible `打开 Tutor 规则提示` action now opens a bottom sheet/drawer.
3. The previous top-level legacy pages produced lint noise and obscured active-source quality. They remain outside the new router and are explicitly isolated from Stage 1 lint.
4. The four-item desktop navigation was too dense at phone widths. It now becomes a horizontally scrollable, full-width two-row header with readable labels.
5. Long Chinese stems and case summaries risked clipping in the practice card. The active layout uses constrained grid columns, wrapping text, a responsive image stage, and full-page captures at all required widths.

The final capture set was then rerun against the real services and includes the mobile Tutor-open state.
