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
    resolve_board_cost_from_grade,
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

    Uses ElkCorr Operating Plan tiered pricing when a board grade is selected.
    The per-row board_cost_msf acts as a manual override — if 0, the grade's
    tiered price is used based on total order MSF.

    Returns the same field keys as the Corrugated Estimate Quantity child DocType,
    plus board_cost_resolved_msf, pricing_tier, upcharge_cost, and upcharge_details.
    """
    settings = get_settings()
    qty = int(float(quantity or 0))
    area = float(blank_area_sqft or 0)
    manual_board_cost = float(board_cost_msf or 0)

    # Resolve board cost from grade tiered pricing + up-charges
    grade_info = resolve_board_cost_from_grade(
        board_grade=board_grade,
        blank_area_sqft=area,
        quantity=qty,
        override_board_cost_msf=manual_board_cost,
    )

    # Fallback chain: grade tiered price → manual override → settings default
    effective_board_cost = grade_info["board_cost_msf"] or manual_board_cost or settings.get("default_board_cost_msf", 180.0)
    board_lbs_msf = grade_info["board_lbs_msf"]

    return calculate_full_row(
        quantity               = qty,
        blank_area_sqft        = area,
        board_cost_msf         = effective_board_cost,
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
        upcharges_msf          = grade_info["upcharges_msf"],
        pricing_tier           = grade_info["pricing_tier"],
        upcharge_details       = grade_info["upcharge_details"],
    )


# ── Sensitivity Matrix ────────────────────────────────────────────────────────

@frappe.whitelist()
def get_sensitivity_matrix(estimate_name):
    """
    Return a sell-price sensitivity matrix for the given estimate.
    Rows = board costs centered around the grade's price, cols = quantities (500–100K).
    Called when user clicks the Sensitivity Analysis button on the form.
    """
    est = frappe.get_doc("Corrugated Estimate", estimate_name)
    settings = get_settings()

    board_lbs_msf = 90.0
    board_costs = None  # use default range

    if est.board_grade:
        grade_info = resolve_board_cost_from_grade(
            board_grade=est.board_grade,
            blank_area_sqft=float(est.blank_area_sqft or 0),
            quantity=int(est.annual_quantity or 5000),
        )
        board_lbs_msf = grade_info["board_lbs_msf"]

        # Center the sensitivity range around the grade's mid-tier price
        mid_price = grade_info["board_cost_msf"]
        if mid_price > 0:
            step = 10
            board_costs = [
                round(mid_price - 3 * step, 2),
                round(mid_price - 2 * step, 2),
                round(mid_price - step, 2),
                round(mid_price, 2),
                round(mid_price + step, 2),
                round(mid_price + 2 * step, 2),
                round(mid_price + 3 * step, 2),
            ]

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
        board_costs            = board_costs,
    )


# ── Board Grade Pricing Info (for JS) ────────────────────────────────────────

@frappe.whitelist()
def get_grade_pricing(board_grade, blank_area_sqft=0, quantity=0, board_cost_msf=0):
    """
    Return resolved board grade pricing info for the JS form.
    Shows the user which tier was selected and any applicable up-charges.
    """
    return resolve_board_cost_from_grade(
        board_grade=board_grade,
        blank_area_sqft=float(blank_area_sqft or 0),
        quantity=int(float(quantity or 0)),
        override_board_cost_msf=float(board_cost_msf or 0),
    )


# ── Settings Reader (for JS) ──────────────────────────────────────────────────

@frappe.whitelist()
def get_estimating_settings():
    """
    Return the Corrugated Estimating Settings as a plain dict for the JS client.
    Used to pre-populate cost model defaults on new estimate creation.
    """
    return get_settings()


# ── Machine Routing API ──────────────────────────────────────────────────────

@frappe.whitelist()
def get_machine_routing(estimate_name):
    """
    Compute routing for an estimate (triggers save which auto-calcs routing).
    Returns routing summary, steps, and die layout info.
    """
    doc = frappe.get_doc("Corrugated Estimate", estimate_name)
    doc.save()
    frappe.db.commit()

    return {
        "routing": doc.recommended_routing,
        "steps": [
            {
                "sequence": s.sequence,
                "operation": s.operation,
                "machine": s.machine,
                "machine_name": s.machine_name,
                "speed_per_hour": s.speed_per_hour,
                "rate_msf": s.rate_msf,
                "setup_time_min": s.setup_time_min,
                "setup_cost": float(s.setup_cost or 0),
                "run_cost": float(s.run_cost or 0),
                "run_time_hours": s.run_time_hours,
                "total_step_cost": float(s.total_step_cost or 0),
                "notes": s.step_notes,
            }
            for s in (doc.routing_steps or [])
        ],
        "die_layout": {
            "outs": doc.die_layout_outs,
            "waste_pct": doc.die_layout_waste_pct,
            "machine": doc.die_layout_machine,
            "orientation": doc.die_layout_orientation,
        },
    }


@frappe.whitelist()
def get_capable_machines_for_estimate(estimate_name):
    """Return ranked machine list for an estimate's spec."""
    from corrugated_estimating.corrugated_estimating.routing import get_capable_machines

    doc = frappe.get_doc("Corrugated Estimate", estimate_name)
    return get_capable_machines(
        blank_length=float(doc.blank_length or 0),
        blank_width=float(doc.blank_width or 0),
        box_style=doc.box_style or "RSC",
        panel_l=float(doc.length_inside or 0),
        panel_w=float(doc.width_inside or 0),
        panel_d=float(doc.depth_inside or 0),
        num_colors=int(doc.num_colors or 0),
        needs_glue=True,
        needs_die_cut=bool(doc.die_cut_special),
        wall_type=doc.wall_type or "Single Wall",
    )


# ── Die Layout API ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_die_layout(estimate_name, machine_id=None, sheet_length=None, sheet_width=None, tight_fit=True):
    """Calculate die layout for an estimate, optionally for a specific machine.

    tight_fit=True (default) sizes the sheet to fit blanks with minimal scrap
    (0.5" trim per side = 1" total outside cuts).
    """
    from corrugated_estimating.corrugated_estimating.layout import (
        calculate_die_layout,
        calculate_layout_for_all_machines,
    )

    doc = frappe.get_doc("Corrugated Estimate", estimate_name)
    bl = float(doc.blank_length or 0)
    bw = float(doc.blank_width or 0)
    tight = True if str(tight_fit).lower() in ("true", "1", "yes") else False

    if not bl or not bw:
        return {"error": "Blank dimensions not calculated yet"}

    if machine_id:
        return calculate_die_layout(
            blank_length=bl,
            blank_width=bw,
            machine_id=machine_id,
            sheet_length=float(sheet_length) if sheet_length else None,
            sheet_width=float(sheet_width) if sheet_width else None,
            tight_fit=tight,
        )

    return calculate_layout_for_all_machines(bl, bw, tight_fit=tight)


@frappe.whitelist()
def get_routing_summary(estimate_name):
    """Return production routing summary with time/cost breakdown."""
    doc = frappe.get_doc("Corrugated Estimate", estimate_name)
    return doc.get_routing_summary()


# ── CAD File Generation API ──────────────────────────────────────────────────

@frappe.whitelist()
def generate_cad_file(estimate_name):
    """Manually trigger DXF CAD file generation for an estimate."""
    from corrugated_estimating.corrugated_estimating.cad_generator import generate_cad_for_estimate
    try:
        file_url = generate_cad_for_estimate(estimate_name)
        if file_url:
            frappe.db.commit()
            return {"status": "success", "file_url": file_url}
        return {"status": "error", "message": "Could not generate CAD file. Check box dimensions."}
    except Exception as e:
        frappe.log_error("CAD generation failed", frappe.get_traceback())
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def generate_die_board_dxf(estimate_name, machine_id=None):
    """Generate full die board DXF with nested blanks on sheet."""
    from corrugated_estimating.corrugated_estimating.cad_generator import (
        generate_die_board_dxf as _gen_die_board,
    )
    try:
        file_url = _gen_die_board(estimate_name, machine_id=machine_id)
        if file_url:
            frappe.db.commit()
            return {"status": "success", "file_url": file_url}
        return {"status": "error", "message": "Could not generate die board DXF."}
    except Exception as e:
        frappe.log_error("Die board DXF generation failed", frappe.get_traceback())
        return {"status": "error", "message": str(e)}


# ── Dieline SVG Data API ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_dieline_svg(estimate_name=None, box_style=None, length=None, width=None,
                    depth=None, flute_type=None, hand_holes=False, glue_tab=False,
                    vent_holes=False, show_dimensions=True):
    """
    Return SVG element data for a box dieline with Pacdora-style colored lines.

    Can be called with an estimate_name (pulls dims from estimate) or with
    explicit box_style + dimensions.
    """
    from corrugated_estimating.corrugated_estimating.dieline_renderer import get_dieline_data

    if estimate_name:
        doc = frappe.get_doc("Corrugated Estimate", estimate_name)
        box_style = doc.box_style or "RSC"
        length = float(doc.length_inside or 0)
        width = float(doc.width_inside or 0)
        depth = float(doc.depth_inside or 0)
        flute_type = doc.flute_type
    else:
        length = float(length or 0)
        width = float(width or 0)
        depth = float(depth or 0)

    if not (length and width and depth):
        return {"error": "Box dimensions (L, W, D) are required"}

    # Get caliper from flute
    caliper_in = 3.7 / 25.4  # default C-flute
    if flute_type:
        try:
            flute = frappe.get_doc("Corrugated Flute", flute_type)
            cal_mm = float(flute.caliper_mm or 0)
            if cal_mm > 0:
                caliper_in = cal_mm / 25.4
        except frappe.DoesNotExistError:
            pass

    hh = str(hand_holes).lower() in ("true", "1", "yes")
    gt = str(glue_tab).lower() in ("true", "1", "yes")
    vh = str(vent_holes).lower() in ("true", "1", "yes")

    return get_dieline_data(
        box_style=box_style, L=length, W=width, D=depth,
        caliper_in=caliper_in, hand_holes=hh, glue_tab=gt, vent_holes=vh,
        show_dimensions=str(show_dimensions).lower() in ("true", "1", "yes"),
    )


# ── Part Kit Layout API ──────────────────────────────────────────────────────

@frappe.whitelist()
def get_part_kit_layout(kit_name):
    """Calculate multi-part die layout for a Part Kit."""
    from corrugated_estimating.corrugated_estimating.layout import (
        calculate_multi_part_layout,
    )

    doc = frappe.get_doc("Corrugated Part Kit", kit_name)

    part_specs = []
    for part in doc.parts:
        bl = float(part.blank_length or 0)
        bw = float(part.blank_width or 0)
        qty = int(part.quantity_per_kit or 1)
        if bl > 0 and bw > 0:
            part_specs.append({
                "blank_length": bl,
                "blank_width": bw,
                "quantity": qty,
                "part_type": part.part_type or "Box Body",
                "label": f"{part.part_type}: {bl:.1f}x{bw:.1f}",
            })

    if not part_specs:
        return {"error": "No parts with valid blank dimensions"}

    return calculate_multi_part_layout(part_specs)


# ── Die Line Studio API ──────────────────────────────────────────────────────

@frappe.whitelist()
def create_estimate_from_studio(box_style, length, width, depth,
                                 flute_type=None, wall_type=None,
                                 joint_width=1.25, **kwargs):
    """Create a new Corrugated Estimate from Die Line Studio parameters."""
    doc = frappe.new_doc("Corrugated Estimate")
    doc.box_style = box_style or "RSC"
    doc.length_inside = float(length or 0)
    doc.width_inside = float(width or 0)
    doc.depth_inside = float(depth or 0)
    if flute_type:
        doc.flute_type = flute_type
    if wall_type:
        doc.wall_type = wall_type
    doc.save()
    frappe.db.commit()
    return {"name": doc.name, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════
#  TOOLING INVENTORY
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def get_estimate_spec(estimate_name):
    """Return box specification fields from an estimate (used by Tooling form)."""
    est = frappe.get_doc("Corrugated Estimate", estimate_name)
    return {
        "box_style": est.box_style,
        "length_inside": est.length_inside,
        "width_inside": est.width_inside,
        "depth_inside": est.depth_inside,
        "flute_type": est.flute_type,
        "board_grade": est.board_grade,
        "num_colors": est.num_colors,
        "customer": est.customer,
    }


@frappe.whitelist()
def check_existing_tooling(customer=None, box_style=None,
                            length_inside=0, width_inside=0, depth_inside=0):
    """Check if active tooling exists for a customer + box spec.

    Returns list of matching Corrugated Tooling records, or empty list.
    """
    if not customer or not box_style:
        return []

    L = float(length_inside or 0)
    W = float(width_inside or 0)
    D = float(depth_inside or 0)

    # Tolerance: within 0.1" on each dimension
    tol = 0.1
    filters = {
        "customer": customer,
        "box_style": box_style,
        "status": "Active",
        "length_inside": ["between", [L - tol, L + tol]],
        "width_inside": ["between", [W - tol, W + tol]],
        "depth_inside": ["between", [D - tol, D + tol]],
    }

    tooling = frappe.get_all("Corrugated Tooling", filters=filters,
                              fields=["name", "tooling_name", "tooling_type",
                                       "last_used_date", "num_impressions",
                                       "storage_location"])
    return tooling


# ═══════════════════════════════════════════════════════════════════════════
#  ERPNEXT INTEGRATION — BOM + JOB CARDS
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def create_bom_from_estimate(estimate_name):
    """Create an ERPNext BOM from a Corrugated Estimate.

    Creates the finished-good Item if needed, links board grade as raw material.
    """
    from corrugated_estimating.corrugated_estimating.integration.bom_bridge import (
        estimate_to_bom,
    )
    return estimate_to_bom(estimate_name)


@frappe.whitelist()
def create_job_cards_from_estimate(estimate_name, sales_order=None):
    """Create ERPNext Job Cards from routing steps of a Corrugated Estimate."""
    from corrugated_estimating.corrugated_estimating.integration.job_card_bridge import (
        estimate_to_job_cards,
    )
    return estimate_to_job_cards(estimate_name, sales_order)
