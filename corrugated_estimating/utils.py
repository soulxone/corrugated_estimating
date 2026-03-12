"""
Corrugated Estimating – Calculation Engine
===========================================
Blank-size and cost calculation functions for corrugated boxes.
All dimensions are in INCHES. Board cost is per 1,000 sq ft (MSF).
"""

# ── Constants ──────────────────────────────────────────────────────────────────
MM_PER_INCH = 25.4
MANUFACTURER_JOINT_INCHES = 1.25   # standard RSC/FOL overlap joint


def _mm_to_in(mm):
    return mm / MM_PER_INCH


def calculate_blank_size(box_style, L, W, D, flute_caliper_mm=3.7):
    """
    Calculate corrugated blank dimensions from inside box dimensions.

    Parameters
    ----------
    box_style        : str   — e.g. "RSC", "FOL", "HSC", "BLISS", "TRAY", "DIE-CUT"
    L, W, D          : float — inside Length, Width, Depth (inches)
    flute_caliper_mm : float — flute thickness in mm (default 3.7mm = C-flute)

    Returns
    -------
    (blank_length, blank_width, blank_area_sqft) as floats
    """
    caliper_in = _mm_to_in(flute_caliper_mm)
    style = (box_style or "RSC").upper().split()[0]   # "RSC", "FOL", etc.

    if style in ("RSC", "FOL", "TELESCOPE", "ROLL"):
        # Regular Slotted Container / Full Overlap / Telescope
        # Blank Length = 2*(L + W) + manufacturer joint
        # Blank Width  = 2*(D + caliper) — top and bottom flaps each = D/2 + tuck
        # Tuck = D/2 for standard RSC
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * (D + caliper_in) + 2 * caliper_in

    elif style == "HSC":
        # Half Slotted Container — only bottom flaps, no top
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = D + (D / 2) + 2 * caliper_in

    elif style in ("BLISS", "ROLLA"):
        # Bliss / Rolla wrap — body wrap + two end panels
        # Simplified: treat as RSC with slightly different width
        blank_length = 2 * (L + D) + MANUFACTURER_JOINT_INCHES
        blank_width  = W + 2 * (D / 2) + 2 * caliper_in

    elif style == "TRAY":
        # One-piece tray (no flaps on top)
        blank_length = L + 2 * D + 2 * MANUFACTURER_JOINT_INCHES
        blank_width  = W + 2 * D + 2 * caliper_in

    elif style in ("DIE-CUT", "OTHER"):
        # Die-cut: caller must provide dimensions directly; return as-is
        # Blank is approx bounding rectangle of scored sheet
        blank_length = L + 2 * D + MANUFACTURER_JOINT_INCHES
        blank_width  = W + 2 * D

    else:
        # Default to RSC formula for unknown styles
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * (D + caliper_in) + 2 * caliper_in

    blank_area_sqft = (blank_length * blank_width) / 144.0   # sq in → sq ft
    return blank_length, blank_width, blank_area_sqft


def calculate_material_cost(blank_area_sqft, board_cost_msf, quantity):
    """
    Calculate total material cost for a given quantity.

    Parameters
    ----------
    blank_area_sqft : float — area of one blank in square feet
    board_cost_msf  : float — board cost per 1,000 sq ft
    quantity        : int   — number of boxes

    Returns
    -------
    float — total material cost in dollars
    """
    if not (blank_area_sqft and board_cost_msf and quantity):
        return 0.0
    return (blank_area_sqft / 1000.0) * board_cost_msf * quantity


def calculate_print_cost(num_colors, print_method_doc):
    """
    Calculate plate / print setup charges.

    Parameters
    ----------
    num_colors       : int  — number of print colors
    print_method_doc : Document — Corrugated Print Method frappe doc

    Returns
    -------
    float — total plate + setup cost
    """
    if not print_method_doc:
        return 0.0
    plates = (num_colors or 0) * float(print_method_doc.per_color_plate_charge or 0)
    setup  = float(print_method_doc.setup_charge or 0)
    return plates + setup


def calculate_sell_price(total_cost, markup_pct, quantity):
    """
    Calculate sell prices from cost + markup.

    Returns
    -------
    dict with keys: sell_price_m (per M), sell_price_unit, extended_total
    """
    if not quantity:
        return {"sell_price_m": 0, "sell_price_unit": 0, "extended_total": 0}
    markup = float(markup_pct or 30) / 100.0
    sell_total = float(total_cost or 0) * (1 + markup)
    return {
        "sell_price_m":    round((sell_total / quantity) * 1000, 2),
        "sell_price_unit": round(sell_total / quantity, 6),
        "extended_total":  round(sell_total, 2),
    }
