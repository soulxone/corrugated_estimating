"""
Corrugated Estimating – Calculation Engine (Full Model v3)
==========================================================
Implements the complete Welch Wyse Box Estimator costing model:

  Material  →  Converting  →  Overhead  →  Amortized Fixed  →  Freight  →  COGS  →  Sell Price

All box dimensions are in INCHES.
Board cost is expressed as $/MSF  (dollars per 1,000 square feet).
Machine rates (converting) are also $/MSF.

New in v3 (ElkCorr Operating Plan integration):
  - Tiered board pricing from Corrugated Board Grade: <50 MSF / >50 MSF / >100 MSF
  - Board Grade Up-Charges (white liner, nomar, kemi, flute surcharges, etc.)
  - resolve_board_cost_from_grade() auto-selects tier based on order MSF
  - get_upcharges_for_grade() sums up-charge $/MSF from the grade's child table
  - Full cost breakdown now includes upcharge_cost as a separate line item
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


# ── Board Grade Pricing Resolution ───────────────────────────────────────────

def resolve_board_cost_from_grade(board_grade, blank_area_sqft, quantity,
                                   override_board_cost_msf=0.0):
    """
    Resolve the effective board cost ($/MSF) from the Corrugated Board Grade
    using ElkCorr Operating Plan tiered pricing.

    Tiers are based on total MSF of the order:
      < 50 MSF  →  price_under_50msf
      50–100 MSF → price_50_to_100msf
      > 100 MSF  →  price_over_100msf

    If the grade has no tiered pricing or is not found, falls back to
    override_board_cost_msf or the settings default.

    Returns
    -------
    dict: {
        board_cost_msf:   float  — resolved price per MSF,
        pricing_tier:     str    — which tier was selected,
        upcharges_msf:    float  — total up-charges per MSF from the grade,
        upcharge_details: list   — [{name, type, amount}] breakdown,
        board_lbs_msf:    float  — board weight for freight,
        minimum_order:    str    — grade minimum order requirement,
        run_as_note:      str    — if grade runs as another grade,
    }
    """
    result = {
        "board_cost_msf": float(override_board_cost_msf or 0),
        "pricing_tier": "Manual Override" if override_board_cost_msf else "Default",
        "upcharges_msf": 0.0,
        "upcharge_details": [],
        "board_lbs_msf": 90.0,
        "minimum_order": "",
        "run_as_note": "",
    }

    if not board_grade:
        return result

    try:
        bg = frappe.get_doc("Corrugated Board Grade", board_grade)
    except frappe.DoesNotExistError:
        return result

    # Board weight
    if bg.lbs_msf:
        result["board_lbs_msf"] = float(bg.lbs_msf)
    result["minimum_order"] = bg.minimum_order or ""
    result["run_as_note"] = bg.run_as_note or ""

    # Calculate total order MSF
    order_msf = (float(blank_area_sqft or 0) * float(quantity or 0)) / 1000.0

    # Resolve tiered pricing (only if tiers are populated and no manual override)
    if not override_board_cost_msf:
        p1 = float(bg.price_under_50msf or 0)
        p2 = float(bg.price_50_to_100msf or 0)
        p3 = float(bg.price_over_100msf or 0)

        if p1 > 0 or p2 > 0 or p3 > 0:
            if order_msf > 100 and p3 > 0:
                result["board_cost_msf"] = p3
                result["pricing_tier"] = "> 100 MSF"
            elif order_msf > 50 and p2 > 0:
                result["board_cost_msf"] = p2
                result["pricing_tier"] = "> 50 MSF"
            elif p1 > 0:
                result["board_cost_msf"] = p1
                result["pricing_tier"] = "< 50 MSF"

    # Sum up-charges from the grade's child table
    upcharges_total = 0.0
    details = []
    for uc in (bg.upcharges or []):
        amt = float(uc.amount_per_msf or 0)
        if amt > 0:
            upcharges_total += amt
            details.append({
                "name": uc.charge_name,
                "type": uc.charge_type or "",
                "amount": amt,
                "note": uc.note or "",
            })

    result["upcharges_msf"] = upcharges_total
    result["upcharge_details"] = details

    return result


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

    elif style in ("RAG", "RAGDISP"):
        # Rag Dispenser: RSC with extended 2.5" joint
        blank_length = 2 * (L + W) + 2.5
        blank_width  = 2 * D + 4 * caliper_in

    elif style in ("WORTHINGTON", "FREON", "TANK"):
        # Worthington: same as SFF
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * D + 4 * caliper_in

    else:
        # Default: RSC formula
        blank_length = 2 * (L + W) + MANUFACTURER_JOINT_INCHES
        blank_width  = 2 * D + 4 * caliper_in

    blank_area_sqft = (blank_length * blank_width) / 144.0
    return blank_length, blank_width, blank_area_sqft


# ── Material Cost (internal) ─────────────────────────────────────────────────

def calculate_effective_waste(waste_pct, quantity=0, settings=None):
    """Calculate effective waste % accounting for run-length spoilage.

    Short runs have higher effective waste due to makeready/startup spoilage.
    Formula: effective = base_waste + (spoilage_sheets / quantity) * 100

    Falls back to flat waste_pct if settings don't have spoilage fields.
    """
    base = float(waste_pct or 8.0)
    qty = int(quantity or 0)
    if qty <= 0:
        return base

    if settings is None:
        settings = get_settings()

    spoilage = float(settings.get("spoilage_sheets", 0))
    if spoilage <= 0:
        return base  # No spoilage factor configured — use flat waste

    base_trim = float(settings.get("base_waste_pct", 5.0))
    effective = base_trim + (spoilage / qty) * 100.0
    return round(min(effective, 50.0), 2)  # Cap at 50% to avoid absurd values


def _calc_material_per_unit(blank_area_sqft, board_cost_msf, waste_pct=8.0,
                             num_colors=0, print_addon_per_color_msf=4.0,
                             wax_treat=False, wax_cost_msf=0.10,
                             upcharges_msf=0.0, quantity=0, settings=None):
    """
    Full per-unit material cost with waste factor, print add-on, wax, and up-charges.

    If quantity > 0 and settings has spoilage_sheets, waste scales with run length.

    Returns
    -------
    (mat_per_unit, gross_sqft_per_unit, upcharge_per_unit)
    """
    area = float(blank_area_sqft or 0)
    if area <= 0:
        return 0.0, 0.0, 0.0

    # Use run-length-dependent waste if quantity provided
    if int(quantity or 0) > 0 and settings:
        eff_waste = calculate_effective_waste(waste_pct, quantity, settings)
    else:
        eff_waste = float(waste_pct or 8.0)

    waste      = eff_waste / 100.0
    gross_sqft = area * (1.0 + waste)
    gross_msf  = gross_sqft / 1000.0

    board  = float(board_cost_msf or 0)
    colors = int(num_colors or 0)
    addon  = float(print_addon_per_color_msf or 0)
    wax    = float(wax_cost_msf or 0.10) if wax_treat else 0.0
    upcharge = float(upcharges_msf or 0.0)

    upcharge_per_unit = upcharge * gross_msf

    mat_per_unit = (board * gross_msf
                    + colors * addon / 1000.0 * area
                    + wax * gross_msf
                    + upcharge_per_unit)
    return mat_per_unit, gross_sqft, upcharge_per_unit


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

def _estimate_boxes_per_pallet(length_in=16, width_in=12, depth_in=10,
                                pallet_l=48, pallet_w=40, max_height=48):
    """Estimate boxes per pallet from box dimensions.

    Tries both orientations, picks the one with most boxes per layer,
    then stacks layers up to max_height (minus 6" for pallet deck).
    """
    L = float(length_in or 16)
    W = float(width_in or 12)
    H = float(depth_in or 10)
    if L <= 0 or W <= 0 or H <= 0:
        return 40  # fallback

    # Try both orientations
    o1_across = int(pallet_l / L)
    o1_down = int(pallet_w / W)
    o2_across = int(pallet_l / W)
    o2_down = int(pallet_w / L)

    per_layer = max(o1_across * o1_down, o2_across * o2_down)
    usable_height = max_height - 6  # 6" pallet deck
    layers = max(1, int(usable_height / H))
    return max(1, per_layer * layers)


def _estimate_pallets_per_truck(pallet_l=48, pallet_w=40, max_height=48):
    """Estimate pallets that fit in a 53' trailer (636" long x 102" wide x 110" tall).

    Standard: pallets load 2-wide (102/48=2) x length (636/40=15) = 30 single-stack.
    If pallet height ≤ 55", can double-stack: 2 x 30 = 60 max, but usually 20-26.
    """
    trailer_l = 636  # 53' in inches
    trailer_w = 102  # 8.5' in inches
    trailer_h = 110  # internal height

    # Pallets oriented lengthwise
    along_l = int(trailer_l / pallet_w)  # 40" side along trailer length
    across_w = int(trailer_w / pallet_l)  # 48" side across trailer width
    single_stack = along_l * across_w  # typically 15 * 2 = 30

    # Can we double-stack?
    total_pallet_h = float(max_height) + 6  # stack height + deck
    if total_pallet_h * 2 <= trailer_h:
        return single_stack * 2
    return single_stack


def calculate_freight_cost_per_unit(blank_area_sqft, board_lbs_msf=90.0,
                                     freight_mode="LTL",
                                     freight_manual_per_unit=0.0,
                                     settings=None,
                                     length_in=0, width_in=0, depth_in=0,
                                     ship_distance_miles=0):
    """
    Freight cost per unit with palletization-based truck loading.

    Modes:
      None   — no freight cost
      LTL    — box_weight_lbs / 100 × ltl_rate_cwt × distance_factor
      TL     — (tl_rate × haul_miles) / pieces_per_truck (palletization-based)
      Manual — flat per-unit value
    """
    if settings is None:
        settings = get_settings()

    if not freight_mode or freight_mode == "None":
        return 0.0

    if freight_mode == "Manual":
        return float(freight_manual_per_unit or 0)

    box_wt_lbs = float(board_lbs_msf or 90.0) / 1000.0 * float(blank_area_sqft or 0)
    distance = float(ship_distance_miles or 0) or settings.get("default_ship_distance_miles", 500)

    if freight_mode == "LTL":
        # Distance factor: base rate at 500 miles, scale proportionally
        base_distance = 500.0
        distance_factor = max(0.5, distance / base_distance)
        return box_wt_lbs / 100.0 * settings["ltl_rate_cwt"] * distance_factor

    if freight_mode == "TL":
        # Use actual palletization if box dimensions provided
        L = float(length_in or 0)
        W = float(width_in or 0)
        D = float(depth_in or 0)

        if L > 0 and W > 0 and D > 0:
            boxes_per_pallet = _estimate_boxes_per_pallet(L, W, D)
            pallets_per_truck = _estimate_pallets_per_truck(max_height=48)
            pieces_per_truck = boxes_per_pallet  # per pallet already includes layers
            # Actually: total per truck = boxes_per_pallet * pallets_per_truck / layers
            # Simplified: use boxes_per_pallet for full pallet, scale by truck pallets
            bpp = _estimate_boxes_per_pallet(L, W, D, max_height=48)
            ppt = _estimate_pallets_per_truck(max_height=48)
            pieces_per_truck = bpp * ppt
        else:
            pieces_per_truck = settings["boxes_per_pallet"] * 26  # realistic default

        haul_miles = distance or settings["tl_haul_miles"]
        tl_total = settings["tl_rate_mile"] * haul_miles
        return tl_total / pieces_per_truck if pieces_per_truck > 0 else 0.0

    return 0.0


# ── Routing-based Converting Cost ───────────────────────────────────────────

def calculate_converting_cost_from_routing(routing_steps, blank_area_sqft, quantity):
    """
    Sum converting cost from actual routing steps instead of flat $/MSF rates.

    Each step: (rate_msf / 1000 * gross_sqft) * quantity + setup_cost
    Returns per-unit converting cost and total setup cost.
    """
    if not routing_steps or not quantity:
        return 0.0, 0.0

    msf_per_unit = float(blank_area_sqft or 0) / 1000.0
    total_run_cost = 0.0
    total_setup = 0.0

    for step in routing_steps:
        rate = float(step.get("rate_msf", 0))
        setup = float(step.get("setup_cost", 0))
        total_run_cost += rate * msf_per_unit * int(quantity)
        total_setup += setup

    total = total_run_cost + total_setup
    per_unit = total / int(quantity) if int(quantity) > 0 else 0
    return per_unit, total_setup


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
        settings=None,
        routing_steps=None,
        die_layout_outs=0,
        upcharges_msf=0.0,
        pricing_tier="",
        upcharge_details=None):
    """
    Calculate the complete cost breakdown for a single quantity row.

    Returns a dict with all cost component keys matching the child DocType fields,
    plus upcharge_cost, pricing_tier, and upcharge_details for the report.
    """
    if settings is None:
        settings = get_settings()

    qty = int(quantity or 0)
    if qty <= 0:
        return {
            "material_cost":   0.0, "converting_cost": 0.0,
            "overhead_cost":   0.0, "amort_fixed":      0.0,
            "freight_cost":    0.0, "upcharge_cost":    0.0,
            "total_cogs":      0.0, "total_cost":       0.0,
            "plate_charges":   0.0,
            "sell_price_m":    0.0, "sell_price_unit":  0.0,
            "extended_total":  0.0,
            "board_cost_resolved_msf": 0.0,
            "pricing_tier":    "",
            "upcharge_details": [],
        }

    # Material (includes up-charges in the material line)
    mat_per_unit, gross_sqft, upcharge_per_unit = _calc_material_per_unit(
        blank_area_sqft, board_cost_msf,
        waste_pct, num_colors, print_addon_per_color_msf,
        wax_treat, settings.get("wax_cost_msf", 0.10),
        upcharges_msf=float(upcharges_msf or 0),
        quantity=qty, settings=settings,
    )
    mat_total = mat_per_unit * qty
    upcharge_total = upcharge_per_unit * qty

    # Converting — use routing-based cost if routing steps provided
    if routing_steps:
        conv_per_unit, routing_setup_total = calculate_converting_cost_from_routing(
            routing_steps, blank_area_sqft, qty
        )
        conv_total = conv_per_unit * qty
    else:
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
        "upcharge_cost":   round(upcharge_total, 2),
        "total_cogs":      round(total_cogs, 2),
        "total_cost":      round(legacy_total, 2),
        "plate_charges":   round(float(plate_charges or 0), 2),
        "sell_price_m":    round(sell_per_unit * 1000, 2),
        "sell_price_unit": round(sell_per_unit, 6),
        "extended_total":  round(sell_total, 2),
        "board_cost_resolved_msf": round(float(board_cost_msf or 0), 2),
        "pricing_tier":    pricing_tier or "",
        "upcharge_details": upcharge_details or [],
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
