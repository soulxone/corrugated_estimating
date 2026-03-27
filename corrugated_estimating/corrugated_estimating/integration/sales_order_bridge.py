"""
sales_order_bridge.py
──────────────────────────────────────────────────────────────────────────────
Converts an accepted Corrugated Estimate into an ERPNext Sales Order.
Called from the Corrugated Estimate form JS "Convert to Sales Order" button.
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, flt


@frappe.whitelist()
def estimate_to_sales_order(estimate_name, quantity_row_idx=None):
    """
    Create a Sales Order from a Corrugated Estimate.

    Args:
        estimate_name: str — Corrugated Estimate document name
        quantity_row_idx: int|None — index of the quantity break to use (0 = first row)
                          If None, uses the first row.

    Returns:
        dict with status, sales_order name, and any messages.
    """
    estimate = frappe.get_doc("Corrugated Estimate", estimate_name)

    if estimate.status not in ("Accepted", "Sent", "Draft"):
        frappe.throw(_("Can only convert Draft, Sent, or Accepted estimates to Sales Orders."))

    if not estimate.customer:
        frappe.throw(_("Estimate must have a Customer linked before creating a Sales Order."))

    if not estimate.quantities:
        frappe.throw(_("Estimate has no quantity rows — please add pricing."))

    # Select quantity row
    idx = int(quantity_row_idx or 0)
    if idx >= len(estimate.quantities):
        idx = 0
    qty_row = estimate.quantities[idx]

    # Build item description from box spec
    item_description = _build_item_description(estimate)

    # Find or create an ERPNext Item for this box style
    item_code = _get_or_create_item(estimate, item_description)

    # Build the Sales Order
    so = frappe.new_doc("Sales Order")
    so.customer       = estimate.customer
    so.delivery_date  = add_days(today(), 14)
    so.company        = frappe.defaults.get_global_default("company")

    # Custom reference fields (added via fixture)
    if hasattr(so, "corrugated_estimate_ref"):
        so.corrugated_estimate_ref = estimate_name
    if estimate.crm_deal and hasattr(so, "crm_deal"):
        so.crm_deal = estimate.crm_deal
    if estimate.crm_lead and hasattr(so, "crm_lead"):
        so.crm_lead = estimate.crm_lead

    # Sales rep
    if estimate.sales_rep:
        so.sales_person = estimate.sales_rep

    # Add item row
    item_row = so.append("items", {})
    item_row.item_code   = item_code
    item_row.item_name   = item_description[:140]
    item_row.description = item_description
    item_row.qty         = flt(qty_row.quantity)
    item_row.uom         = "Nos"
    item_row.rate        = flt(qty_row.sell_price_unit)
    item_row.delivery_date = so.delivery_date

    so.insert(ignore_permissions=True)

    # Mark estimate as linked
    frappe.db.set_value("Corrugated Estimate", estimate_name, {
        "status":          "Accepted",
        "sales_order_ref": so.name,
    })

    # ── ERPNext Integration: BOM + Tooling + Job Cards ───────────────────
    bom_result = None
    tooling_result = None
    job_cards_result = None

    # Auto-create BOM
    try:
        from corrugated_estimating.corrugated_estimating.integration.bom_bridge import estimate_to_bom
        bom_result = estimate_to_bom(estimate_name)
    except Exception as e:
        frappe.log_error(f"BOM creation failed for {estimate_name}: {e}")

    # Auto-create Tooling record if tooling cost > 0
    try:
        tooling_result = _create_tooling_record(estimate, so.name)
    except Exception as e:
        frappe.log_error(f"Tooling creation failed for {estimate_name}: {e}")

    # Auto-create Job Cards from routing
    try:
        if estimate.routing_steps:
            from corrugated_estimating.corrugated_estimating.integration.job_card_bridge import estimate_to_job_cards
            job_cards_result = estimate_to_job_cards(estimate_name, so.name)
    except Exception as e:
        frappe.log_error(f"Job Card creation failed for {estimate_name}: {e}")

    frappe.db.commit()

    msg_parts = [_("Sales Order {0} created from estimate {1}").format(so.name, estimate_name)]
    if bom_result and bom_result.get("bom_name"):
        msg_parts.append(_("BOM: {0}").format(bom_result["bom_name"]))
    if tooling_result:
        msg_parts.append(_("Tooling: {0}").format(tooling_result))
    if job_cards_result and job_cards_result.get("count"):
        msg_parts.append(_("{0} Job Cards created").format(job_cards_result["count"]))

    return {
        "status": "success",
        "sales_order": so.name,
        "bom": bom_result.get("bom_name") if bom_result else None,
        "tooling": tooling_result,
        "job_cards": job_cards_result.get("job_cards") if job_cards_result else [],
        "message": " | ".join(msg_parts),
    }


def _build_item_description(estimate):
    """Build a human-readable description of the corrugated box."""
    parts = []
    if estimate.box_style:
        parts.append(estimate.box_style)
    if estimate.flute_type:
        parts.append(estimate.flute_type)
    if estimate.board_grade:
        parts.append(estimate.board_grade)
    dims = []
    if estimate.length_inside: dims.append(f'L{estimate.length_inside}"')
    if estimate.width_inside:  dims.append(f'W{estimate.width_inside}"')
    if estimate.depth_inside:  dims.append(f'D{estimate.depth_inside}"')
    if dims:
        parts.append("×".join(dims))
    if estimate.num_colors and int(estimate.num_colors or 0) > 0:
        parts.append(f"{estimate.num_colors}C")
    return " ".join(parts) if parts else f"Corrugated Box — {estimate.name}"


def _create_tooling_record(estimate, sales_order_name):
    """Create a Corrugated Tooling record if tooling_cost > 0 and no existing tooling."""
    if not flt(estimate.tooling_cost):
        return None

    # Check if tooling already exists for this estimate
    existing = frappe.db.get_value("Corrugated Tooling",
                                    {"corrugated_estimate": estimate.name}, "name")
    if existing:
        # Update the SO link
        frappe.db.set_value("Corrugated Tooling", existing, "sales_order", sales_order_name)
        return existing

    tooling = frappe.get_doc({
        "doctype": "Corrugated Tooling",
        "tooling_name": "{style} {L}x{W}x{D} Die".format(
            style=estimate.box_style or "Box",
            L=estimate.length_inside or 0,
            W=estimate.width_inside or 0,
            D=estimate.depth_inside or 0,
        ),
        "tooling_type": "Cutting Die",
        "customer": estimate.customer,
        "corrugated_estimate": estimate.name,
        "sales_order": sales_order_name,
        "box_style": estimate.box_style,
        "length_inside": estimate.length_inside,
        "width_inside": estimate.width_inside,
        "depth_inside": estimate.depth_inside,
        "flute_type": estimate.flute_type,
        "board_grade": estimate.board_grade,
        "num_colors": estimate.num_colors,
        "cost": flt(estimate.tooling_cost),
        "status": "Active",
    })
    tooling.insert(ignore_permissions=True)
    return tooling.name


def _get_or_create_item(estimate, description):
    """
    Return an Item code for this box spec.
    Uses a generic "Corrugated Box" item if it exists, else creates one.
    In production, you'd match to actual item masters or use Item Variants.
    """
    # Try: item named after the estimate
    candidate = f"BOX-{estimate.name}"
    if frappe.db.exists("Item", candidate):
        return candidate

    # Try: generic corrugated box item
    if frappe.db.exists("Item", "Corrugated Box"):
        return "Corrugated Box"

    # Create a minimal item
    item = frappe.new_doc("Item")
    item.item_code        = candidate
    item.item_name        = description[:140]
    item.description      = description
    item.item_group       = "Products"
    item.stock_uom        = "Nos"
    item.is_stock_item    = 1
    item.is_sales_item    = 1
    item.is_purchase_item = 0
    item.insert(ignore_permissions=True)
    return candidate
