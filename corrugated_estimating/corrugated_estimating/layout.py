"""
Die Cut Layout Calculator for Corrugated Estimating.

Calculates optimal nesting of blanks into a die cutter's usable area,
determining number of outs, waste percentage, and generating position
data for SVG visualization.
"""
import math
import frappe


def calculate_die_layout(
    blank_length,
    blank_width,
    machine_id=None,
    sheet_length=None,
    sheet_width=None,
    trim_allowance=0.5,
    gripper_edge=1.0,
    gutter=0.75,
):
    """
    Calculate optimal nesting of blanks on a die cutter sheet.

    If machine_id is provided, uses machine's constraints (cutting surface,
    max blank size, trim). Otherwise uses sheet_length/width directly.

    Args:
        blank_length: blank length in inches
        blank_width: blank width in inches
        machine_id: optional Corrugated Machine ID (e.g. "130")
        sheet_length: manual sheet length in inches (used if no machine_id)
        sheet_width: manual sheet width in inches (used if no machine_id)
        trim_allowance: trim per side in inches (default 0.5)
        gripper_edge: leading edge grip in inches (default 1.0)
        gutter: space between blanks in inches (default 0.75)

    Returns dict with layout data including positions for SVG rendering.
    """
    blank_length = float(blank_length or 0)
    blank_width = float(blank_width or 0)

    if blank_length <= 0 or blank_width <= 0:
        return _empty_layout("Blank dimensions must be positive")

    # ── Determine sheet/usable area ────────────────────────────────────────
    machine = None
    if machine_id:
        try:
            machine = frappe.get_doc("Corrugated Machine", machine_id)
        except frappe.DoesNotExistError:
            pass

    if machine:
        trim_allowance = machine.trim_allowance or trim_allowance
        s_length = machine.blank_max_width or sheet_length or 110
        s_width = machine.cutting_surface_width or machine.blank_max_length or sheet_width or 80

        # For rotary die cutters, the cutting surface width IS the usable width
        if machine.cutting_surface_width:
            usable_width = machine.cutting_surface_width - (2 * trim_allowance)
        else:
            usable_width = s_width - (2 * trim_allowance)

        usable_length = s_length - (2 * trim_allowance) - gripper_edge
    else:
        s_length = float(sheet_length or 110)
        s_width = float(sheet_width or 80)
        usable_length = s_length - (2 * trim_allowance) - gripper_edge
        usable_width = s_width - (2 * trim_allowance)

    if usable_length <= 0 or usable_width <= 0:
        return _empty_layout("Usable area is zero after trim/gripper")

    # ── Try both orientations ──────────────────────────────────────────────
    layout_0 = _calc_outs_for_orientation(
        blank_length, blank_width, usable_length, usable_width, gutter
    )
    layout_90 = _calc_outs_for_orientation(
        blank_width, blank_length, usable_length, usable_width, gutter
    )

    if layout_0["total_outs"] >= layout_90["total_outs"]:
        best = layout_0
        orientation = "0deg"
        eff_blank_l = blank_length
        eff_blank_w = blank_width
    else:
        best = layout_90
        orientation = "90deg"
        eff_blank_l = blank_width
        eff_blank_w = blank_length

    if best["total_outs"] == 0:
        return _empty_layout(
            f"Blank {blank_length}x{blank_width} does not fit in usable area "
            f"{usable_length:.1f}x{usable_width:.1f}"
        )

    # ── Generate layout positions ──────────────────────────────────────────
    positions = []
    x_start = trim_allowance + gripper_edge
    y_start = trim_allowance

    for row in range(best["outs_down"]):
        for col in range(best["outs_across"]):
            x = x_start + col * (eff_blank_l + gutter)
            y = y_start + row * (eff_blank_w + gutter)
            positions.append({
                "row": row,
                "col": col,
                "x": round(x, 3),
                "y": round(y, 3),
                "width": round(eff_blank_l, 3),
                "height": round(eff_blank_w, 3),
            })

    # ── Calculate waste ────────────────────────────────────────────────────
    blank_area = blank_length * blank_width
    total_blank_area = best["total_outs"] * blank_area
    sheet_area = s_length * s_width
    waste_pct = (1 - total_blank_area / sheet_area) * 100 if sheet_area else 100
    utilization_pct = 100 - waste_pct

    return {
        "outs_across": best["outs_across"],
        "outs_down": best["outs_down"],
        "total_outs": best["total_outs"],
        "blank_orientation": orientation,
        "blank_length": blank_length,
        "blank_width": blank_width,
        "effective_blank_l": eff_blank_l,
        "effective_blank_w": eff_blank_w,
        "usable_length": round(usable_length, 3),
        "usable_width": round(usable_width, 3),
        "sheet_length": round(s_length, 3),
        "sheet_width": round(s_width, 3),
        "trim_allowance": trim_allowance,
        "gripper_edge": gripper_edge,
        "gutter": gutter,
        "total_blank_area_sqin": round(total_blank_area, 2),
        "total_blank_area_sqft": round(total_blank_area / 144, 4),
        "sheet_area_sqin": round(sheet_area, 2),
        "sheet_area_sqft": round(sheet_area / 144, 4),
        "waste_pct": round(waste_pct, 1),
        "utilization_pct": round(utilization_pct, 1),
        "layout_positions": positions,
        "machine_id": machine_id or "",
        "machine_name": machine.machine_name if machine else "Manual",
        "error": "",
    }


def _calc_outs_for_orientation(blank_l, blank_w, usable_l, usable_w, gutter):
    """
    Calculate how many blanks fit in one orientation.

    Uses: outs = floor((usable + gutter) / (blank + gutter))
    The +gutter on the numerator accounts for no gutter needed after the last blank.
    """
    if blank_l <= 0 or blank_w <= 0:
        return {"outs_across": 0, "outs_down": 0, "total_outs": 0}

    outs_across = int(math.floor((usable_l + gutter) / (blank_l + gutter)))
    outs_down = int(math.floor((usable_w + gutter) / (blank_w + gutter)))
    total = outs_across * outs_down

    return {
        "outs_across": max(outs_across, 0),
        "outs_down": max(outs_down, 0),
        "total_outs": max(total, 0),
    }


def calculate_layout_for_all_machines(blank_length, blank_width):
    """
    Calculate die layout for every capable die-cut machine.

    Returns list of layout results sorted by total_outs descending (best first).
    """
    machines = frappe.get_all(
        "Corrugated Machine",
        filters={"enabled": 1, "can_die_cut": 1},
        pluck="name",
    )

    results = []
    for mid in machines:
        layout = calculate_die_layout(
            blank_length, blank_width, machine_id=mid,
        )
        if layout["total_outs"] > 0:
            results.append(layout)

    results.sort(key=lambda x: (-x["total_outs"], x["waste_pct"]))
    return results


def calculate_optimal_sheet_size(
    blank_length,
    blank_width,
    machine_id=None,
    trim_allowance=0.5,
    gripper_edge=1.0,
    gutter=0.75,
    max_outs=20,
):
    """
    Calculate the minimum sheet size needed for a target number of outs.
    Useful for ordering corrugated sheet stock.

    Returns dict with recommended sheet dimensions and layout.
    """
    blank_length = float(blank_length or 0)
    blank_width = float(blank_width or 0)

    if blank_length <= 0 or blank_width <= 0:
        return _empty_layout("Blank dimensions must be positive")

    best_result = None

    # Try different out configurations (across x down)
    for across in range(1, max_outs + 1):
        for down in range(1, max_outs + 1):
            total = across * down
            if total < 2:
                continue

            # Calculate minimum sheet size for this configuration
            needed_l = across * blank_length + (across - 1) * gutter + 2 * trim_allowance + gripper_edge
            needed_w = down * blank_width + (down - 1) * gutter + 2 * trim_allowance

            # Check if within machine constraints
            if machine_id:
                try:
                    machine = frappe.get_doc("Corrugated Machine", machine_id)
                    if needed_l > (machine.blank_max_width or 999):
                        continue
                    if machine.cutting_surface_width and needed_w > machine.cutting_surface_width:
                        continue
                    if needed_w > (machine.blank_max_length or 999):
                        continue
                except frappe.DoesNotExistError:
                    pass

            sheet_area = needed_l * needed_w
            blank_area = total * blank_length * blank_width
            waste = (1 - blank_area / sheet_area) * 100

            result = {
                "outs_across": across,
                "outs_down": down,
                "total_outs": total,
                "sheet_length": round(needed_l, 2),
                "sheet_width": round(needed_w, 2),
                "waste_pct": round(waste, 1),
            }

            if best_result is None or (
                total > best_result["total_outs"]
                or (total == best_result["total_outs"] and waste < best_result["waste_pct"])
            ):
                best_result = result

    return best_result or _empty_layout("No valid configuration found")


def _empty_layout(reason=""):
    """Return an empty layout result with error message."""
    return {
        "outs_across": 0,
        "outs_down": 0,
        "total_outs": 0,
        "blank_orientation": "",
        "blank_length": 0,
        "blank_width": 0,
        "effective_blank_l": 0,
        "effective_blank_w": 0,
        "usable_length": 0,
        "usable_width": 0,
        "sheet_length": 0,
        "sheet_width": 0,
        "trim_allowance": 0,
        "gripper_edge": 0,
        "gutter": 0,
        "total_blank_area_sqin": 0,
        "total_blank_area_sqft": 0,
        "sheet_area_sqin": 0,
        "sheet_area_sqft": 0,
        "waste_pct": 0,
        "utilization_pct": 0,
        "layout_positions": [],
        "machine_id": "",
        "machine_name": "",
        "error": reason,
    }
