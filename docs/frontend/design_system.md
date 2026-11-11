# Bearing design system

The current application extends Bearing with the focused product workspace
described in [product_ux_redesign.md](product_ux_redesign.md). Marketing tokens
below remain unchanged. `.product-app` scopes warm neutral surfaces, 10/18/22px
radii, low-shadow cards, larger editorial headings and lime active navigation
to the application. Dark workspace surfaces are charcoal forest. The approved
landing page does not receive these overrides.

Continues Claude's checkpoint A–D visual system. The source of truth is
`apps/web/src/app/globals.css`; shared classes live in `components/styles.ts`.

| Role | Light theme | Dark theme |
| --- | --- | --- |
| Forest ink | `#0f2a22` | `#0b1f19` |
| Research surface | `#f5f7f5` | `#0f1714` |
| Panel | `#ffffff` | `#16211d` |
| Primary action | `#1d6b4f` | `#3fa57a` |
| Primary action text | `#ffffff` | `#0b1f19` |
| Main text | `#13221c` | `#e6eee9` |

Schibsted Grotesk is bundled locally, with system fallbacks and tabular financial
digits. The body is 15px; headings use the existing 1.25 scale. Radii are 4/8/14px.
Forest rails and hero bands frame mineral paper research surfaces. Teal, orange
and blue chart series remain separate from caution/danger status colors.

Use the existing Panel, Field, Button, Badge, Disclosure and Tabs components.
Financial amounts arrive as decimal strings; formatting never sums or converts
currencies. Missing amounts read “Not reported”; unavailable totals retain their
backend reason. Exact amounts are accessible in financial tables/tooltips.

At small widths, navigation becomes a native modal drawer, project rows become
cards, financial tables scroll locally, and ranked chart bars occupy their own
row. Above 1024px the persistent rail returns. Long evidence and financial tables
retain local horizontal scrolling. Native dialogs provide focus containment and
Escape behavior. Tabs support arrows, Home and End with focus movement.

Visible focus uses a blue outline. All motion honors reduced-motion preference.
Themes follow the OS unless the user persists a choice; action text has its own
contrast token. Avoid adding remote font dependencies or decorative data.
