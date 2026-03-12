"""
Corrugated Estimating – whitelisted API endpoints
"""
import frappe
from frappe import _
from corrugated_estimating.corrugated_estimating.utils import calculate_blank_size


@frappe.whitelist()
def get_blank_size(box_style, length_inside, width_inside, depth_inside, flute_type=""):
    """
    Return blank dimensions for the given box style and inside dimensions.
    Called from the client-side JS for live preview.
    """
    caliper_mm = 3.7  # default C-flute
    if flute_type:
        try:
            flute = frappe.get_doc("Corrugated Flute", flute_type)
            caliper_mm = flute.caliper_mm or 3.7
        except frappe.DoesNotExistError:
            pass

    bl, bw, area = calculate_blank_size(
        box_style,
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


@frappe.whitelist()
def get_estimates_for_customer(customer):
    """Return summary list of estimates for a given Customer (for Customer form tab)."""
    estimates = frappe.get_all(
        "Corrugated Estimate",
        filters={"customer": customer},
        fields=[
            "name", "estimate_date", "status", "box_style",
            "length_inside", "width_inside", "depth_inside",
            "crm_lead", "crm_deal",
        ],
        order_by="estimate_date desc",
        limit=50,
    )
    return estimates
