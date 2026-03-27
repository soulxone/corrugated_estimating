"""Job Card Bridge — Create ERPNext Job Cards from Corrugated Estimate routing.

Each routing step becomes a Job Card linked to the Sales Order / Work Order.
"""
import frappe
from frappe.utils import flt, today, add_days


def estimate_to_job_cards(estimate_name, sales_order=None):
    """Create Job Cards from routing steps of a Corrugated Estimate.

    Returns list of created Job Card names.
    """
    est = frappe.get_doc("Corrugated Estimate", estimate_name)

    if not est.routing_steps:
        frappe.throw("No routing steps on this estimate. Run 'Compute Routing' first.")

    # Determine quantity from the accepted/selected quantity row
    quantity = 0
    if est.quantities:
        # Use the first quantity row, or the one linked to the SO
        quantity = int(est.quantities[0].quantity or 0)

    if quantity <= 0:
        frappe.throw("No quantity rows on this estimate.")

    company = frappe.defaults.get_global_default("company")
    created = []
    planned_start = today()

    for i, step in enumerate(est.routing_steps):
        # Find or create Workstation from machine
        workstation = _get_or_create_workstation(step.machine, company)

        # Find or create Operation
        operation = _get_or_create_operation(step.operation)

        jc = frappe.new_doc("Job Card")
        jc.company = company
        jc.posting_date = planned_start

        # Link to production
        if sales_order:
            jc.sales_order = sales_order

        jc.operation = operation
        jc.workstation = workstation
        jc.for_quantity = quantity
        jc.wip_warehouse = _get_default_warehouse(company)

        # Time estimates from routing
        setup_mins = flt(step.setup_time or 0)
        run_mins = flt(step.run_time or 0)
        total_mins = setup_mins + run_mins

        jc.append("time_logs", {
            "from_time": f"{planned_start} 08:00:00",
            "to_time": f"{planned_start} {8 + int(total_mins / 60):02d}:{int(total_mins % 60):02d}:00",
            "time_in_mins": total_mins,
            "completed_qty": 0,
        })

        # Custom fields for corrugated tracking
        jc.remarks = (
            f"Estimate: {estimate_name}\n"
            f"Step {i + 1}: {step.operation}\n"
            f"Machine: {step.machine or 'TBD'}\n"
            f"Rate: ${flt(step.rate_msf or 0):.2f}/MSF\n"
            f"Setup: ${flt(step.setup_cost or 0):.2f}\n"
            f"Run Cost: ${flt(step.run_cost or 0):.2f}"
        )

        jc.insert(ignore_permissions=True)
        created.append(jc.name)

        # Advance planned start by run time for sequential scheduling
        if total_mins > 480:  # > 8 hours, push to next day
            planned_start = add_days(planned_start, 1)

    frappe.db.commit()

    return {
        "status": "success",
        "job_cards": created,
        "count": len(created),
        "message": f"{len(created)} Job Cards created from {estimate_name}.",
    }


def _get_or_create_workstation(machine_name, company):
    """Map a Corrugated Machine to an ERPNext Workstation."""
    if not machine_name:
        return ""

    # Check if workstation exists with same name
    if frappe.db.exists("Workstation", machine_name):
        return machine_name

    # Check if there's a Corrugated Machine with a workstation link
    ws = frappe.db.get_value("Corrugated Machine", machine_name, "workstation")
    if ws and frappe.db.exists("Workstation", ws):
        return ws

    # Auto-create workstation
    try:
        doc = frappe.get_doc({
            "doctype": "Workstation",
            "workstation_name": machine_name,
            "company": company,
        })
        doc.insert(ignore_permissions=True)
        return doc.name
    except Exception:
        return ""


def _get_or_create_operation(operation_name):
    """Ensure an ERPNext Operation exists."""
    if not operation_name:
        operation_name = "Converting"

    if frappe.db.exists("Operation", operation_name):
        return operation_name

    try:
        doc = frappe.get_doc({
            "doctype": "Operation",
            "name": operation_name,
        })
        doc.insert(ignore_permissions=True)
        return operation_name
    except Exception:
        return "Converting"


def _get_default_warehouse(company):
    """Get the default WIP warehouse for the company."""
    wh = frappe.db.get_value("Company", company, "default_warehouse")
    if wh:
        return wh
    # Fallback: find any warehouse
    wh = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
    return wh or ""
