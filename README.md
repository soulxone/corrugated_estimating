# Corrugated Estimating

Full corrugated box estimating app for Frappe/ERPNext.

## Features
- **Master tables**: Box Style, Flute, Board Grade, Print Method (with pricing)
- **Corrugated Estimate** DocType with `track_changes=1` — full field-level audit trail
- **Multiple quantity breaks** per estimate (child table) with auto-calculated:
  - Material cost from blank area × board cost/MSF × quantity
  - Plate/setup charges from Print Method master
  - Sell price/M and per-unit with configurable markup %
- **Blank size calculation**: RSC, FOL, HSC, BLISS, TRAY, DIE-CUT formulas
- **Linked to** CRM Lead, CRM Deal, and ERPNext Customer
- **Customer form tab** showing full estimate history
- **Live browser-side calculation** via whitelisted API endpoint
