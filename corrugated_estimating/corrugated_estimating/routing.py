"""
Machine Routing Engine for Corrugated Estimating.

Given a box specification (style, blank size, panel dims, print/glue/die-cut needs),
determines which Lexington machines can run the job and builds the optimal
multi-step routing sequence with cost estimates.
"""
import frappe
from frappe import _

# ── Box style → required operations mapping ─────────────────────────────────

# Operations: Print, Score/Slot, Die Cut, Fold/Glue, Specialty Fold, Stitch
STYLE_OPERATIONS = {
    # Standard RSC / FOL / HSC → inline FFG (print + score + fold + glue)
    "RSC":     ["Print", "Score/Slot", "Fold/Glue"],
    "FOL":     ["Print", "Score/Slot", "Fold/Glue"],
    "HSC":     ["Print", "Score/Slot", "Fold/Glue"],
    "CSSC":    ["Print", "Score/Slot", "Fold/Glue"],
    "OPF":     ["Print", "Score/Slot", "Fold/Glue"],
    # Die-cut styles → need die cutter
    "DIE-CUT": ["Print", "Die Cut", "Fold/Glue"],
    "DC":      ["Print", "Die Cut", "Fold/Glue"],
    "MAILER":  ["Print", "Die Cut", "Fold/Glue"],
    "PIZZA":   ["Print", "Die Cut"],
    # Specialty fold styles → J&L specialty folder
    "TRAY":    ["Print", "Die Cut", "Specialty Fold"],
    "SFF":     ["Print", "Die Cut", "Specialty Fold"],
    "SNAP":    ["Print", "Die Cut", "Specialty Fold"],
    "LOCK":    ["Print", "Die Cut", "Specialty Fold"],
    # Bliss → no fold/glue (wrap-around)
    "BLISS":   ["Print", "Score/Slot"],
    # Five-panel folder
    "5PF":     ["Print", "Score/Slot", "Fold/Glue"],
    # Telescope → two pieces, each may need separate routing
    "TELESCOPE": ["Print", "Score/Slot", "Fold/Glue"],
}

# Operations → which machine departments handle them
OPERATION_DEPARTMENTS = {
    "Print":          ["Print", "Fold/Glue", "Die Cut"],  # FFGs and RDC have print stations
    "Score/Slot":     ["Score/Slot", "Fold/Glue", "Auto Box"],  # FFGs score inline
    "Die Cut":        ["Die Cut", "Fold/Glue"],  # Machine 148 has inline die cut
    "Fold/Glue":      ["Fold/Glue"],
    "Specialty Fold": ["Specialty"],
    "Stitch":         ["Stitch"],
}

# Machines that can consolidate multiple operations inline
INLINE_MACHINES = {
    "146": {"Print", "Score/Slot", "Fold/Glue"},
    "148": {"Print", "Score/Slot", "Die Cut", "Fold/Glue"},
}


def get_all_machines(enabled_only=True):
    """Fetch all Corrugated Machine documents."""
    filters = {"enabled": 1} if enabled_only else {}
    names = frappe.get_all("Corrugated Machine", filters=filters, pluck="name")
    return [frappe.get_doc("Corrugated Machine", n) for n in names]


def get_capable_machines(
    blank_length,
    blank_width,
    box_style="RSC",
    panel_l=0,
    panel_w=0,
    panel_d=0,
    num_colors=0,
    needs_glue=True,
    needs_die_cut=False,
    needs_stitch=False,
    wall_type="Single Wall",
):
    """
    Return a ranked list of machines that can handle the given spec.

    Returns list of dicts sorted by: qualified first (speed desc), then disqualified.
    Each dict: machine_id, machine_name, department, fits_blank, fits_panel,
               has_capability, speed_per_hour, rate_msf, disqualify_reasons
    """
    machines = get_all_machines()
    results = []

    for m in machines:
        reasons = []

        fits_blank = m.blank_fits(blank_length, blank_width)
        if not fits_blank:
            reasons.append(
                f"Blank {blank_length}x{blank_width} outside range "
                f"{m.blank_min_length}x{m.blank_min_width} - "
                f"{m.blank_max_length}x{m.blank_max_width}"
            )

        fits_panel = m.panel_fits(panel_l, panel_w, panel_d)
        if not fits_panel:
            reasons.append(
                f"Panel {panel_l}x{panel_w}x{panel_d} outside machine panel limits"
            )

        # Check FFG unfolded width constraint
        if m.max_unfolded_width and blank_length > m.max_unfolded_width:
            reasons.append(
                f"Blank length {blank_length} exceeds max unfolded width {m.max_unfolded_width}"
            )

        # Check fold clearance for folder-gluers
        if m.fold_clearance and panel_w and panel_w < m.fold_clearance:
            reasons.append(
                f"Panel width {panel_w} less than fold clearance {m.fold_clearance}"
            )

        # Capability checks
        has_cap = True
        if needs_die_cut and not m.can_die_cut:
            has_cap = False
            reasons.append("Cannot die cut")
        if needs_stitch and not m.can_stitch:
            has_cap = False
            reasons.append("Cannot stitch")
        if needs_glue and m.department in ("Fold/Glue", "Specialty") and not m.can_glue:
            has_cap = False
            reasons.append("Cannot glue")
        if num_colors > 0 and m.department == "Print" and not m.can_print:
            has_cap = False
            reasons.append("Cannot print")

        results.append({
            "machine_id": m.machine_id,
            "machine_name": m.machine_name,
            "department": m.department,
            "fits_blank": fits_blank,
            "fits_panel": fits_panel,
            "has_capability": has_cap,
            "speed_per_hour": m.get_speed_per_hour(),
            "rate_msf": m.rate_msf or 0,
            "setup_time_min": m.setup_time_min or 0,
            "setup_cost": m.setup_cost or 0,
            "disqualify_reasons": reasons,
            "qualified": len(reasons) == 0,
        })

    # Sort: qualified first (by speed desc), disqualified after
    results.sort(key=lambda x: (not x["qualified"], -x["speed_per_hour"]))
    return results


def _find_best_machine_for_operation(
    operation, blank_length, blank_width, panel_l, panel_w, panel_d,
    num_colors=0, exclude_ids=None,
):
    """Find the best qualified machine for a specific operation."""
    departments = OPERATION_DEPARTMENTS.get(operation, [])
    machines = get_all_machines()
    exclude_ids = exclude_ids or set()

    candidates = []
    for m in machines:
        if m.machine_id in exclude_ids:
            continue
        if m.department not in departments:
            continue
        if not m.blank_fits(blank_length, blank_width):
            continue
        if not m.panel_fits(panel_l, panel_w, panel_d):
            continue

        # FFG unfolded width check
        if m.max_unfolded_width and blank_length > m.max_unfolded_width:
            continue

        # Fold clearance check
        if m.fold_clearance and panel_w and panel_w < m.fold_clearance:
            continue

        # Operation-specific capability checks
        if operation == "Print" and not m.can_print:
            continue
        if operation == "Score/Slot" and not m.can_score_slot:
            continue
        if operation == "Die Cut" and not m.can_die_cut:
            continue
        if operation in ("Fold/Glue", "Specialty Fold") and not m.can_fold and not m.can_glue:
            continue
        if operation == "Stitch" and not m.can_stitch:
            continue
        if operation == "Specialty Fold" and m.department != "Specialty":
            continue

        candidates.append({
            "machine": m,
            "speed_per_hour": m.get_speed_per_hour(),
            "rate_msf": m.rate_msf or 0,
        })

    if not candidates:
        return None

    # Prefer higher speed, then lower cost
    candidates.sort(key=lambda x: (-x["speed_per_hour"], x["rate_msf"]))
    return candidates[0]["machine"]


def determine_routing_sequence(
    box_style,
    blank_length,
    blank_width,
    panel_l=0,
    panel_w=0,
    panel_d=0,
    num_colors=0,
    needs_glue=True,
    needs_die_cut=False,
    needs_stitch=False,
    wall_type="Single Wall",
):
    """
    Determine the optimal machine routing sequence for a box spec.

    Returns ordered list of routing steps:
    [
        {
            "sequence": 1,
            "operation": "Print + Score + Fold/Glue",
            "machine_id": "146",
            "machine_name": '37" Lang FFG',
            "speed_per_hour": 15000,
            "rate_msf": 55.0,
            "setup_time_min": 20,
            "setup_cost": 50,
            "notes": "Inline operations",
        },
    ]
    """
    style_upper = (box_style or "RSC").upper().strip()

    # Override die_cut flag for die-cut styles
    if style_upper in ("DIE-CUT", "DC", "MAILER", "PIZZA", "TRAY", "SFF", "SNAP", "LOCK"):
        needs_die_cut = True

    # Override stitch flag
    if needs_stitch:
        # Replace Fold/Glue with Stitch in required operations
        pass

    required_ops = list(STYLE_OPERATIONS.get(style_upper, ["Print", "Score/Slot", "Fold/Glue"]))

    if needs_stitch and "Fold/Glue" in required_ops:
        required_ops = [op for op in required_ops if op != "Fold/Glue"]
        required_ops.append("Stitch")

    if num_colors == 0 and "Print" in required_ops:
        required_ops.remove("Print")

    # ── Try inline consolidation first ──────────────────────────────────────
    # Check if an FFG (146 or 148) can handle all operations in one pass
    routing = _try_inline_routing(
        required_ops, blank_length, blank_width, panel_l, panel_w, panel_d,
        num_colors, needs_die_cut,
    )
    if routing:
        return routing

    # ── Fall back to separate machines per operation ────────────────────────
    routing = []
    seq = 0
    used_ids = set()

    for op in required_ops:
        machine = _find_best_machine_for_operation(
            op, blank_length, blank_width, panel_l, panel_w, panel_d,
            num_colors, exclude_ids=None,
        )

        if machine:
            seq += 1
            routing.append({
                "sequence": seq,
                "operation": op,
                "machine_id": machine.machine_id,
                "machine_name": machine.machine_name,
                "speed_per_hour": machine.get_speed_per_hour(),
                "rate_msf": machine.rate_msf or 0,
                "setup_time_min": machine.setup_time_min or 0,
                "setup_cost": float(machine.setup_cost or 0),
                "notes": "",
            })
            used_ids.add(machine.machine_id)
        else:
            seq += 1
            routing.append({
                "sequence": seq,
                "operation": op,
                "machine_id": "",
                "machine_name": "NO MACHINE FOUND",
                "speed_per_hour": 0,
                "rate_msf": 0,
                "setup_time_min": 0,
                "setup_cost": 0,
                "notes": f"No qualified machine for {op} with blank {blank_length}x{blank_width}",
            })

    return routing


def _try_inline_routing(
    required_ops, blank_length, blank_width, panel_l, panel_w, panel_d,
    num_colors, needs_die_cut,
):
    """
    Try to consolidate all operations into a single inline machine pass.
    Returns routing list if possible, None otherwise.
    """
    for machine_id, inline_ops in INLINE_MACHINES.items():
        # Check if this machine can handle ALL required operations
        ops_set = set(required_ops)
        if not ops_set.issubset(inline_ops):
            continue

        try:
            machine = frappe.get_doc("Corrugated Machine", machine_id)
        except frappe.DoesNotExistError:
            continue

        if not machine.enabled:
            continue
        if not machine.blank_fits(blank_length, blank_width):
            continue
        if not machine.panel_fits(panel_l, panel_w, panel_d):
            continue

        # FFG unfolded width check
        if machine.max_unfolded_width and blank_length > machine.max_unfolded_width:
            continue

        # Fold clearance check
        if machine.fold_clearance and panel_w and panel_w < machine.fold_clearance:
            continue

        # Print capability check
        if "Print" in ops_set and num_colors > 0:
            if not machine.can_print:
                continue
            if machine.print_stations and num_colors > machine.print_stations:
                continue

        # This machine handles everything inline
        consolidated_name = " + ".join(required_ops)
        return [{
            "sequence": 1,
            "operation": consolidated_name,
            "machine_id": machine.machine_id,
            "machine_name": machine.machine_name,
            "speed_per_hour": machine.get_speed_per_hour(),
            "rate_msf": machine.rate_msf or 0,
            "setup_time_min": machine.setup_time_min or 0,
            "setup_cost": float(machine.setup_cost or 0),
            "notes": "Inline — all operations in single pass",
        }]

    return None


def calculate_routing_cost(routing_steps, blank_area_sqft, quantity):
    """
    Calculate total converting cost from routing steps.

    Args:
        routing_steps: list of routing step dicts (from determine_routing_sequence)
        blank_area_sqft: area of one blank in sq ft
        quantity: number of pieces

    Returns dict:
        {
            "total_converting_cost_per_unit": float,
            "total_setup_cost": float,
            "total_run_cost": float,
            "steps": [
                {
                    "operation": str,
                    "machine_id": str,
                    "setup_cost": float,
                    "run_cost_per_unit": float,
                    "run_time_hours": float,
                    "total_step_cost": float,
                    "total_time_hours": float,
                }
            ]
        }
    """
    if not routing_steps or not quantity:
        return {
            "total_converting_cost_per_unit": 0,
            "total_setup_cost": 0,
            "total_run_cost": 0,
            "steps": [],
        }

    msf_per_unit = blank_area_sqft / 1000  # convert sq ft to MSF
    total_setup = 0
    total_run = 0
    costed_steps = []

    for step in routing_steps:
        rate = step.get("rate_msf", 0)
        setup = step.get("setup_cost", 0)
        speed = step.get("speed_per_hour", 0)
        setup_min = step.get("setup_time_min", 0)

        # Run cost = rate per MSF * MSF per unit * quantity
        run_cost_total = rate * msf_per_unit * quantity
        run_cost_per_unit = rate * msf_per_unit

        # Time calculations
        run_time_hours = (quantity / speed) if speed > 0 else 0
        setup_hours = setup_min / 60 if setup_min else 0
        total_time = setup_hours + run_time_hours

        total_setup += setup
        total_run += run_cost_total

        costed_steps.append({
            "operation": step.get("operation", ""),
            "machine_id": step.get("machine_id", ""),
            "machine_name": step.get("machine_name", ""),
            "setup_cost": setup,
            "run_cost": round(run_cost_total, 2),
            "run_cost_per_unit": round(run_cost_per_unit, 4),
            "run_time_hours": round(run_time_hours, 2),
            "setup_time_min": setup_min,
            "total_time_hours": round(total_time, 2),
            "total_step_cost": round(setup + run_cost_total, 2),
        })

    total_converting = total_setup + total_run
    converting_per_unit = total_converting / quantity if quantity else 0

    return {
        "total_converting_cost_per_unit": round(converting_per_unit, 4),
        "total_setup_cost": round(total_setup, 2),
        "total_run_cost": round(total_run, 2),
        "total_converting_cost": round(total_converting, 2),
        "steps": costed_steps,
    }


def format_routing_summary(routing_steps):
    """Format routing steps into a human-readable summary string."""
    if not routing_steps:
        return "No routing determined"

    lines = []
    for step in routing_steps:
        line = f"Step {step['sequence']}: {step['operation']} → Machine {step['machine_id']} ({step['machine_name']})"
        if step.get("speed_per_hour"):
            line += f" @ {step['speed_per_hour']:,.0f}/hr"
        if step.get("notes"):
            line += f" [{step['notes']}]"
        lines.append(line)

    return "\n".join(lines)
