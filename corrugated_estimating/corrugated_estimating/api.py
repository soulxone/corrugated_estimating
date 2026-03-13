"""
Corrugated Estimating – Whitelisted API Endpoints
==================================================
Called from corrugated_estimate.js on the Frappe form (client-side AJAX).
"""

import frappe
from corrugated_estimating.corrugated_estimating.utils import (
    calculate_blank_size,
    calculate_full_row,
    calculate_sensitivity_matrix,
    get_settings,
)


# ── Blank Size ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_blank_size(box_style, length_inside, width_inside, depth_inside, flute_type=None):
    """
    Return corrugated blank dimensions for the given box style and inside dims.
    Called client-side on every dimension change so the form updates in real-time.
    """
    caliper_mm = 0.0
    if flute_type:
        try:
            flute = frappe.get_doc("Corrugated Flute", flute_type)
            caliper_mm = float(flute.caliper_mm or 0)
        except frappe.DoesNotExistError:
            pass

    bl, bw, area = calculate_blank_size(
        box_style or "RSC",
        float(length_inside),
        float(width_inside),
        float(depth_inside),
        caliper_mm,
    )
    return {
        "blank_length":    round(bl,   4),
        "blank_width":     round(bw,   4),
        "blank_area_sqft": round(area, 6),
    }


# ── Full Row Cost ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def calculate_row(
        quantity, blank_area_sqft, board_cost_msf,
        waste_pct=8, num_colors=0, print_addon_per_color_msf=4,
        wax_treat=0, die_cut=0,
        overhead_pct=15, target_margin_pct=35,
        tooling_cost=0, setup_cost=0,
        freight_mode="LTL", freight_manual_per_unit=0,
        board_grade=None, markup_pct=30,
        plate_charges=0, die_charge=0, setup_charge=0):
    """
    Full cost calculation for a single quantity row.
    Called from corrugated_estimate.js whenever any cost-driver changes.

    Returns the same field keys as the Corrugated Estimate Quantity child DocType.
    """
    settings = get_settings()

    # Resolve board weight from board grade master
    board_lbs_msf = 90.0
    if board_grade:
        try:
            bg = frappe.get_doc("Corrugated Board Grade", board_grade)
            if bg.lbs_msf:
                board_lbs_msf = float(bg.lbs_msf)
        except frappe.DoesNotExistError:
            pass

    return calculate_full_row(
        quantity               = int(float(quantity or 0)),
        blank_area_sqft        = float(blank_area_sqft or 0),
        board_cost_msf         = float(board_cost_msf or 0),
        waste_pct              = float(waste_pct or 8),
        num_colors             = int(float(num_colors or 0)),
        print_addon_per_color_msf = float(print_addon_per_color_msf or 4),
        wax_treat              = bool(int(wax_treat or 0)),
        die_cut                = bool(int(die_cut or 0)),
        overhead_pct           = float(overhead_pct or 15),
        target_margin_pct      = float(target_margin_pct or 35),
        tooling_cost           = float(tooling_cost or 0),
        setup_cost             = float(setup_cost or 0),
        freight_mode           = freight_mode or "LTL",
        freight_manual_per_unit = float(freight_manual_per_unit or 0),
        board_lbs_msf          = board_lbs_msf,
        plate_charges          = float(plate_charges or 0),
        die_charge             = float(die_charge or 0),
        setup_charge_legacy    = float(setup_charge or 0),
        markup_pct             = float(markup_pct or 30),
        settings               = settings,
    )


# ── Sensitivity Matrix ────────────────────────────────────────────────────────

@frappe.whitelist()
def get_sensitivity_matrix(estimate_name):
    """
    Return a sell-price sensitivity matrix for the given estimate.
    Rows = board costs ($140–$260), cols = quantities (500–100K).
    Called when user clicks the Sensitivity Analysis button on the form.
    """
    est = frappe.get_doc("Corrugated Estimate", estimate_name)
    settings = get_settings()

    board_lbs_msf = 90.0
    if est.board_grade:
        try:
            bg = frappe.get_doc("Corrugated Board Grade", est.board_grade)
            if bg.lbs_msf:
                board_lbs_msf = float(bg.lbs_msf)
        except frappe.DoesNotExistError:
            pass

    return calculate_sensitivity_matrix(
        blank_area_sqft        = float(est.blank_area_sqft or 0),
        num_colors             = int(est.num_colors or 0),
        print_addon_per_color_msf = float(est.print_addon_per_color_msf or 4),
        waste_pct              = float(est.waste_pct or 8),
        overhead_pct           = float(est.overhead_pct or 15),
        target_margin_pct      = float(est.target_margin_pct or 35),
        tooling_cost           = float(est.tooling_cost or 0),
        setup_cost             = float(est.setup_cost or 0),
        freight_mode           = est.freight_mode or "LTL",
        freight_manual_per_unit = float(est.freight_manual_per_unit or 0),
        board_lbs_msf          = board_lbs_msf,
        wax_treat              = bool(est.wax_water_resist),
        die_cut                = bool(est.die_cut_special),
        settings               = settings,
    )


# ── Settings Reader (for JS) ──────────────────────────────────────────────────

@frappe.whitelist()
def get_estimating_settings():
    """
    Return the Corrugated Estimating Settings as a plain dict for the JS client.
    Used to pre-populate cost model defaults on new estimate creation.
    """
    return get_settings()
