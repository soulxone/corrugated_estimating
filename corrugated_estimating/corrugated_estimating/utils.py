"""
Corrugated Estimating – Calculation Engine (Full Model v2)
==========================================================
Implements the complete Welch Wyse Box Estimator costing model:

  Material  →  Converting  →  Overhead  →  Amortized Fixed  →  Freight  →  COGS  →  Sell Price

All box dimensions are in INCHES.
Board cost is expressed as $/MSF  (dollars per 1,000 square feet).
Machine rates (converting) are also $/MSF.

New in v2:
  - Waste factor applied to blank area before material cost calc
  - Full converting cost from machine rates (FFG + Slot + Die + Glue + Bundle + QC)
  - Overhead as % of converting
  - Tooling + setup amortized per quantity
  - Freight model: LTL ($/cwt), TL ($/mile), or Manual
  - Target-margin sell pricing:  Sell = COGS / (1 − margin%)
  - Sensitivity matrix (board cost × quantity grid)
  - All settings loaded from Corrugated Estimating Settings singleton
"""

import frappe

# ── Constants ────────────────────────────────────────────────────────────────
MM_PER_INCH = 25.4
MANUFACTURER_JOINT_INCHES = 1.25    # standard RSC/FOL mfr joint allowance

# Hard-coded fallbacks if Settings doc doesn't exist yet
_SETTINGS_DEFAULTS = {
    # Machine rates ($/MSF)
    "ffg_rate":            55.0,
    "slot_rate":           12.0,
    "diecut_rate":          0.0,
    "glue_rate":            6.5,
    "bundle_rate":          4.0,
    "qc_rate":              3.5,
    # Freight
    "ltl_rate_cwt":        18.5,
    "tl_rate_mile":         3.2,
    "tl_haul_miles":      500.0,
    "dim_factor":         139.0,
    "boxes_per_pallet":    40.0,
    # Benchmarks / misc
    "wt_rate_per_lb":       0.75,
    "sqin_rate":          0.0024,
    "wax_cost_msf":         0.10,
    "print_addon_default":  4.0,
    # Estimate defaults
    "default_waste_pct":         8.0,
    "default_overhead_pct":     15.0,
    "default_target_margin_pct": 35.0,
    "default_board_cost_msf":  180.0,
}


# ── Settings loader ──────────────────────────────────────────────────────────

def get_settings():
    """
    Fetch Corrugated Estimating Settings singleton.
    Returns a plain dict. Falls back to _SETTINGS_DEFAULTS if the doc is missing.
    """
    try:
        doc = frappe.get_single("Corrugated Estimating Settings")
        result = {}
        for key, default in _SETTINGS_DEFAULTS.items():
            val = getattr(doc, key, None)
            result[key] = float(val) if (val is not None and val != "") else default
        return result
    except Exception:
        return dict(_SETTINGS_DEFAULTS)


# ── Blank Size ───────────────────────────────────────────────────────────────

def _mm_to_in(mm):
    return float(mm or 0) / MM_PER_INCH


def calculate_blank_size(box_style, L, W, D, flute_caliper_mm=3.7):
    """
    Calculate corrugated blank dimensions from inside box dimensions.

    Parameters
    ----------
    box_style        : str   — e.g. "RSC", "FOL", "HSC", "BLISS", "TRAY", "DIE-CUT"
    L, W, D          : float — inside Length, Width, Depth (inches)
    flute_caliper_mm : float — flute thickness in mm (default 3.7 mm = C-flute)

    Returns
    -------
    tuple: (blank_length_in, blank_width_in, blank_area_sqft)
    """
    L, W, D = float(L or 0), float(W or 0), float(D or 0)
    caliper_in = _mm_to_in(flute_caliper_mm or 3.7)

    # Normalize style code
    style = (box_style or "RSC").upper().replace("-", "").replace(" ", "")

    if style in ("RSC", "FOL", "TELESCOPE", "ROLL", "OPF", "CSSC", "SFF"):
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * D + 4 * caliper_in

    elif style == "HSC":
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = D + (D / 2) + 2 * caliper_in

    elif style in ("BLISS", "BLI", "ROLLA"):
        blank_length = 2 * (L + D) + MANUFACTURER_JOINT_INCHES
        blank_width  = W + D + 2 * caliper_in

    elif style in ("TRAY", "FTC", "HTC", "DST"):
        blank_length = L + 2 * D + 2 * MANUFACTURER_JOINT_INCHES
        blank_width  = W + 2 * D + 2 * caliper_in

    elif style in ("DSC", "DSCRSC"):
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * (D + caliper_in) + 4 * caliper_in

    elif style in ("SEF", "SEAL"):
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * D + 4 * caliper_in + 0.5

    elif style in ("WRT", "WRAP", "WPF", "FPF", "RPT"):
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = D + 2 * caliper_in

    elif style in ("INT", "PAD"):
        blank_length = L
        blank_width  = W

    elif style in ("DIECUT", "OTHER", "DIE"):
        blank_length = L + 2 * D + MANUFACTURER_JOINT_INCHES
        blank_width  = W + 2 * D

    else:
        # Default: RSC formula
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * D + 4 * caliper_in

    blank_area_sqft = (blank_length * blank_width) / 144.0
    return blank_length, blank_width, blank_area_sqft


# ── Material Cost (internal) ─────────────────────────────────────────────────

def _calc_material_per_unit(blank_area_sqft, board_cost_msf, waste_pct=8.0,
                             num_colors=0, print_addon_per_color_msf=4.0,
                             wax_treat=False, wax_cost_msf=0.10):
    """
    Full per-unit material cost with waste factor, print add-on, and wax treatment.

    Returns
    -------
    (mat_per_unit, gross_sqft_per_unit)
    """
    area = float(blank_area_sqft or 0)
    if area <= 0:
        return 0.0, 0.0

    waste      = float(waste_pct or 8.0) / 100.0
    gross_sqft = area * (1.0 + waste)
    gross_msf  = gross_sqft / 1000.0

    board  = float(board_cost_msf or 0)
    colors = int(num_colors or 0)
    addon  = float(print_addon_per_color_msf or 0)
    wax    = float(wax_cost_msf or 0.10) if wax_treat else 0.0

    mat_per_unit = (board * gross_msf
                    + colors * addon / 1000.0 * area
                    + wax * gross_msf)
    return mat_per_unit, gross_sqft


# ── Converting Cost ──────────────────────────────────────────────────────────

def calculate_converting_cost_per_unit(gross_sqft_per_unit, die_cut=False, settings=None):
    """
    Converting cost per unit from machine rates in Settings.

    Rate  = FFG + Slot + [DieCut] + Glue + Bundle + QC  ($/MSF)
    Cost  = rate / 1000 × gross_sqft
    """
    if settings is None:
        settings = get_settings()

    rate = (
        settings["ffg_rate"]
        + settings["slot_rate"]
        + (settings["diecut_rate"] if die_cut else 0.0)
        + settings["glue_rate"]
        + settings["bundle_rate"]
        + settings["qc_rate"]
    )
    return rate / 1000.0 * float(gross_sqft_per_unit or 0)


# ── Overhead ─────────────────────────────────────────────────────────────────

def calculate_overhead_per_unit(converting_per_unit, overhead_pct=15.0):
    """Overhead = converting × overhead %."""
    return float(converting_per_unit or 0) * float(overhead_pct or 15.0) / 100.0


# ── Amortized Fixed Costs ────────────────────────────────────────────────────

def calculate_amortized_fixed(tooling_cost, setup_cost, quantity):
    """Tooling + setup amortized across the print quantity."""
    qty = int(quantity or 0)
    if qty <= 0:
        return 0.0
    return (float(tooling_cost or 0) + float(setup_cost or 0)) / qty


# ── Freight Cost ─────────────────────────────────────────────────────────────

def calculate_freight_cost_per_unit(blank_area_sqft, board_lbs_msf=90.0,
                                     freight_mode="LTL",
                                     freight_manual_per_unit=0.0,
                                     settings=None):
    """
    Freight cost per unit.

    Modes:
      None   — no freight cost
      LTL    — box_weight_lbs / 100 × ltl_rate_cwt
      TL     — (tl_rate × haul_miles) / pieces_per_truck
      Manual — flat per-unit value
    """
    if settings is None:
        settings = get_settings()

    if not freight_mode or freight_mode == "None":
        return 0.0

    if freight_mode == "Manual":
        return float(freight_manual_per_unit or 0)

    box_wt_lbs = float(board_lbs_msf or 90.0) / 1000.0 * float(blank_area_sqft or 0)

    if freight_mode == "LTL":
        return box_wt_lbs / 100.0 * settings["ltl_rate_cwt"]

    if freight_mode == "TL":
        pallets_per_truck = 40.0
        pieces_per_truck  = settings["boxes_per_pallet"] * pallets_per_truck
        tl_total = settings["tl_rate_mile"] * settings["tl_haul_miles"]
        return tl_total / pieces_per_truck if pieces_per_truck > 0 else 0.0

    return 0.0


# ── Full Row Cost (all-in) ───────────────────────────────────────────────────

def calculate_full_row(
        quantity, blank_area_sqft, board_cost_msf,
        waste_pct=8.0, num_colors=0, print_addon_per_color_msf=4.0,
        wax_treat=False, die_cut=False,
        overhead_pct=15.0, target_margin_pct=35.0,
        tooling_cost=0.0, setup_cost=0.0,
        freight_mode="LTL", freight_manual_per_unit=0.0,
        board_lbs_msf=90.0,
        plate_charges=0.0, die_charge=0.0, setup_charge_legacy=0.0,
        markup_pct=30.0,
        settings=None):
    """
    Calculate the complete cost breakdown for a single quantity row.

    Returns a dict with all cost component keys matching the child DocType fields.
    """
    if settings is None:
        settings = get_settings()

    qty = int(quantity or 0)
    if qty <= 0:
        return {
            "material_cost":   0.0, "converting_cost": 0.0,
            "overhead_cost":   0.0, "amort_fixed":      0.0,
            "freight_cost":    0.0, "total_cogs":       0.0,
            "total_cost":      0.0, "plate_charges":    0.0,
            "sell_price_m":    0.0, "sell_price_unit":  0.0,
            "extended_total":  0.0,
        }

    # Material
    mat_per_unit, gross_sqft = _calc_material_per_unit(
        blank_area_sqft, board_cost_msf,
        waste_pct, num_colors, print_addon_per_color_msf,
        wax_treat, settings.get("wax_cost_msf", 0.10),
    )
    mat_total = mat_per_unit * qty

    # Converting
    conv_per_unit = calculate_converting_cost_per_unit(gross_sqft, die_cut, settings)
    conv_total    = conv_per_unit * qty

    # Overhead
    oh_per_unit = calculate_overhead_per_unit(conv_per_unit, overhead_pct)
    oh_total    = oh_per_unit * qty

    # Amortized fixed
    amort_per_unit = calculate_amortized_fixed(tooling_cost, setup_cost, qty)
    amort_total    = amort_per_unit * qty

    # Freight
    frt_per_unit = calculate_freight_cost_per_unit(
        blank_area_sqft, board_lbs_msf,
        freight_mode, freight_manual_per_unit, settings,
    )
    frt_total = frt_per_unit * qty

    total_cogs = mat_total + conv_total + oh_total + amort_total + frt_total

    # Sell price: target-margin preferred, markup fallback
    if float(target_margin_pct or 0) > 0:
        margin = float(target_margin_pct) / 100.0
        sell_total = total_cogs / (1.0 - margin) if margin < 1.0 else total_cogs * 2.0
    else:
        sell_total = total_cogs * (1.0 + float(markup_pct or 30) / 100.0)

    sell_per_unit = sell_total / qty if qty > 0 else 0.0

    # Legacy simplified total
    legacy_total = (mat_total
                    + float(plate_charges or 0)
                    + float(die_charge or 0)
                    + float(setup_charge_legacy or 0))

    return {
        "material_cost":   round(mat_total, 2),
        "converting_cost": round(conv_total, 2),
        "overhead_cost":   round(oh_total, 2),
        "amort_fixed":     round(amort_total, 2),
        "freight_cost":    round(frt_total, 2),
        "total_cogs":      round(total_cogs, 2),
        "total_cost":      round(legacy_total, 2),
        "plate_charges":   round(float(plate_charges or 0), 2),
        "sell_price_m":    round(sell_per_unit * 1000, 2),
        "sell_price_unit": round(sell_per_unit, 6),
        "extended_total":  round(sell_total, 2),
    }


# ── Sensitivity Matrix ───────────────────────────────────────────────────────

def calculate_sensitivity_matrix(
        blank_area_sqft,
        num_colors=0, print_addon_per_color_msf=4.0,
        waste_pct=8.0, overhead_pct=15.0, target_margin_pct=35.0,
        tooling_cost=0.0, setup_cost=0.0,
        freight_mode="LTL", freight_manual_per_unit=0.0,
        board_lbs_msf=90.0, wax_treat=False, die_cut=False,
        board_costs=None, quantities=None, settings=None):
    """
    Build a sell-price sensitivity matrix: rows = board costs, cols = quantities.

    Returns dict:  { board_costs, quantities, matrix }
    matrix[i][j] = sell_price_unit for board_costs[i] × quantities[j]
    """
    if settings is None:
        settings = get_settings()

    if board_costs is None:
        board_costs = [140, 160, 180, 200, 220, 240, 260]
    if quantities is None:
        quantities  = [500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]

    matrix = []
    for bc in board_costs:
        row_prices = []
        for qty in quantities:
            r = calculate_full_row(
                quantity               = qty,
                blank_area_sqft        = blank_area_sqft,
                board_cost_msf         = bc,
                waste_pct              = waste_pct,
                num_colors             = num_colors,
                print_addon_per_color_msf = print_addon_per_color_msf,
                wax_treat              = wax_treat,
                die_cut                = die_cut,
                overhead_pct           = overhead_pct,
                target_margin_pct      = target_margin_pct,
                tooling_cost           = tooling_cost,
                setup_cost             = setup_cost,
                freight_mode           = freight_mode,
                freight_manual_per_unit = freight_manual_per_unit,
                board_lbs_msf          = board_lbs_msf,
                settings               = settings,
            )
            row_prices.append(round(r["sell_price_unit"], 4))
        matrix.append(row_prices)

    return {
        "board_costs": board_costs,
        "quantities":  quantities,
        "matrix":      matrix,
    }


# ── Legacy helpers ────────────────────────────────────────────────────────────

def calculate_material_cost(blank_area_sqft, board_cost_msf, quantity):
    """Simple material cost (no waste factor) — kept for backward compat."""
    if not (blank_area_sqft and board_cost_msf and quantity):
        return 0.0
    return (float(blank_area_sqft) / 1000.0) * float(board_cost_msf) * float(quantity)


def calculate_print_cost(num_colors, print_method_doc):
    """Legacy plate + setup from Corrugated Print Method doc."""
    if not print_method_doc:
        return 0.0
    plates = (int(num_colors or 0)) * float(print_method_doc.per_color_plate_charge or 0)
    return plates + float(print_method_doc.setup_charge or 0)


def calculate_sell_price(total_cost, markup_pct, quantity):
    """Legacy markup-based sell price."""
    if not quantity:
        return {"sell_price_m": 0, "sell_price_unit": 0, "extended_total": 0}
    markup     = float(markup_pct or 30) / 100.0
    sell_total = float(total_cost or 0) * (1.0 + markup)
    return {
        "sell_price_m":    round((sell_total / quantity) * 1000, 2),
        "sell_price_unit": round(sell_total / quantity, 6),
        "extended_total":  round(sell_total, 2),
    }
