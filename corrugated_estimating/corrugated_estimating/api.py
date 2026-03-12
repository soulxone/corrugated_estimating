"""
Corrugated Estimating – Whitelisted API Endpoints
==================================================
Called from corrugated_estimate.js on the Frappe form.
"""

import frappe
from corrugated_estimating.corrugated_estimating.utils import calculate_blank_size


@frappe.whitelist()
def get_blank_size(box_style, length_inside, width_inside, depth_inside, flute_type=None):
    """
    Return corrugated blank dimensions for the given box style and inside dims.
    Called client-side on every dimension change so the form updates in real-time.

    Returns a dict:
        {blank_length, blank_width, blank_area_sqft}
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
        "blank_length":    round(bl, 4),
        "blank_width":     round(bw, 4),
        "blank_area_sqft": round(area, 6),
    }
