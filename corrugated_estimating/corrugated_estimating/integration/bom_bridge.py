"""BOM Bridge — Create ERPNext BOM from Corrugated Estimate.

Creates finished-good Item + BOM with board stock as raw material.
"""
import frappe
from frappe.utils import flt


def estimate_to_bom(estimate_name):
    """Create an ERPNext BOM from a Corrugated Estimate.

    Returns dict with bom_name, item_code, status.
    """
    est = frappe.get_doc("Corrugated Estimate", estimate_name)

    if not est.box_style or not est.blank_area_sqft:
        frappe.throw("Estimate must have box style and blank dimensions calculated.")

    # 1. Find or create the finished-good Item
    item_code = _get_or_create_box_item(est)

    # 2. Check if BOM already exists
    existing_bom = frappe.db.get_value("BOM", {
        "item": item_code, "is_active": 1, "is_default": 1
    }, "name")
    if existing_bom:
        return {
            "status": "exists",
            "bom_name": existing_bom,
            "item_code": item_code,
            "message": f"BOM {existing_bom} already exists for {item_code}.",
        }

    # 3. Determine raw material (board stock)
    board_item = _get_board_item(est)

    # 4. Calculate material quantity per unit
    waste_pct = flt(est.waste_pct or 8) / 100.0
    gross_sqft = flt(est.blank_area_sqft) * (1.0 + waste_pct)
    gross_msf = gross_sqft / 1000.0

    # 5. Create BOM
    bom = frappe.new_doc("BOM")
    bom.item = item_code
    bom.quantity = 1
    bom.is_active = 1
    bom.is_default = 1
    bom.company = frappe.defaults.get_global_default("company")
    bom.rm_cost_as_per = "Valuation Rate"

    # Board stock as raw material
    if board_item:
        bom.append("items", {
            "item_code": board_item,
            "qty": gross_msf,
            "uom": "Nos",  # MSF units — ideally a custom UOM
            "rate": flt(est.board_cost_default_msf or 0),
        })

    # Add operations from routing if available
    if est.routing_steps:
        for step in est.routing_steps:
            bom.append("operations", {
                "operation": step.operation or "Converting",
                "workstation": step.machine or "",
                "time_in_mins": flt(step.run_time or 0) + flt(step.setup_time or 0),
                "operating_cost": flt(step.total_step_cost or 0),
            })

    bom.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "bom_name": bom.name,
        "item_code": item_code,
        "message": f"BOM {bom.name} created for {item_code}.",
    }


def _get_or_create_box_item(est):
    """Find or create an ERPNext Item for the corrugated box."""
    # Item code pattern: BOX-{style}-{L}x{W}x{D}
    item_code = "BOX-{style}-{L}x{W}x{D}".format(
        style=(est.box_style or "BOX").upper(),
        L=int(est.length_inside or 0),
        W=int(est.width_inside or 0),
        D=int(est.depth_inside or 0),
    )

    if frappe.db.exists("Item", item_code):
        return item_code

    # Create item
    desc = "{style} {L}x{W}x{D} {wall} {flute}".format(
        style=est.box_style or "Box",
        L=est.length_inside or 0,
        W=est.width_inside or 0,
        D=est.depth_inside or 0,
        wall=est.wall_type or "Single Wall",
        flute=est.flute_type or "C",
    )

    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": desc[:140],
        "description": desc,
        "item_group": _get_or_create_item_group("Corrugated Boxes"),
        "stock_uom": "Nos",
        "is_stock_item": 1,
        "include_item_in_manufacturing": 1,
    })
    item.insert(ignore_permissions=True)
    return item_code


def _get_board_item(est):
    """Get the ERPNext Item for the board grade, if linked."""
    if not est.board_grade:
        return None

    # Check if the board grade has an item_code field
    try:
        item_code = frappe.db.get_value(
            "Corrugated Board Grade", est.board_grade, "item_code"
        )
        if item_code and frappe.db.exists("Item", item_code):
            return item_code
    except Exception:
        pass

    # Auto-create board stock item
    board_item_code = "BOARD-" + (est.board_grade or "GENERIC").upper().replace(" ", "-")
    if frappe.db.exists("Item", board_item_code):
        return board_item_code

    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": board_item_code,
        "item_name": f"Corrugated Board - {est.board_grade}",
        "description": f"Corrugated board stock grade {est.board_grade}",
        "item_group": _get_or_create_item_group("Board Stock"),
        "stock_uom": "Nos",
        "is_stock_item": 1,
    })
    item.insert(ignore_permissions=True)
    return board_item_code


def _get_or_create_item_group(group_name):
    """Ensure an Item Group exists, creating under 'All Item Groups' if needed."""
    if frappe.db.exists("Item Group", group_name):
        return group_name

    try:
        parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}, "name")
        if not parent:
            parent = "All Item Groups"

        doc = frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": group_name,
            "parent_item_group": parent,
        })
        doc.insert(ignore_permissions=True)
        return group_name
    except Exception:
        return "Products"  # fallback to a common default
