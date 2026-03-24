import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from corrugated_estimating.corrugated_estimating.utils import (
    calculate_blank_size,
    calculate_full_row,
    get_settings,
)


class CorrugatedEstimate(Document):

    def before_save(self):
        """Recalculate blank size, routing, die layout, and all quantity row costs."""
        if not self.estimate_no:
            self.estimate_no = self.name
        self._calc_blank_size()
        self._calc_routing()
        self._calc_die_layout()
        self._calc_quantities()

    def on_update(self):
        """Post-save: generate CAD file if dimensions are available."""
        self._generate_cad_file()

    def _generate_cad_file(self):
        """Auto-generate DXF CAD file when blank dims are available."""
        if not (self.blank_length and self.blank_width and self.name):
            return
        try:
            from corrugated_estimating.corrugated_estimating.cad_generator import (
                generate_cad_for_estimate,
            )
            generate_cad_for_estimate(self.name)
        except Exception:
            frappe.log_error("CAD auto-generation failed", frappe.get_traceback())

    # ── Blank Size ─────────────────────────────────────────────────────────────
    def _calc_blank_size(self):
        if not (self.length_inside and self.width_inside and self.depth_inside):
            return

        caliper_mm = 0.0
        if self.flute_type:
            try:
                flute = frappe.get_doc("Corrugated Flute", self.flute_type)
                caliper_mm = float(flute.caliper_mm or 0)
            except frappe.DoesNotExistError:
                pass

        bl, bw, area = calculate_blank_size(
            self.box_style or "RSC",
            float(self.length_inside),
            float(self.width_inside),
            float(self.depth_inside),
            caliper_mm,
        )
        self.blank_length     = round(bl,   4)
        self.blank_width      = round(bw,   4)
        self.blank_area_sqft  = round(area, 6)

    # ── Machine Routing ────────────────────────────────────────────────────────
    def _calc_routing(self):
        """Compute machine routing and populate routing_steps child table."""
        if not (self.blank_length and self.blank_width):
            return

        try:
            from corrugated_estimating.corrugated_estimating.routing import (
                determine_routing_sequence,
                format_routing_summary,
            )
        except ImportError:
            return

        style = self.box_style or "RSC"
        needs_die_cut = bool(self.die_cut_special)
        num_colors = int(self.num_colors or 0)

        routing = determine_routing_sequence(
            box_style=style,
            blank_length=float(self.blank_length),
            blank_width=float(self.blank_width),
            panel_l=float(self.length_inside or 0),
            panel_w=float(self.width_inside or 0),
            panel_d=float(self.depth_inside or 0),
            num_colors=num_colors,
            needs_glue=True,
            needs_die_cut=needs_die_cut,
            wall_type=self.wall_type or "Single Wall",
        )

        # Clear and repopulate routing_steps
        self.routing_steps = []
        for step in routing:
            self.append("routing_steps", {
                "sequence": step["sequence"],
                "operation": step["operation"],
                "machine": step["machine_id"] if step["machine_id"] else None,
                "machine_name": step["machine_name"],
                "speed_per_hour": step["speed_per_hour"],
                "rate_msf": step["rate_msf"],
                "setup_time_min": step["setup_time_min"],
                "setup_cost": step["setup_cost"],
                "step_notes": step.get("notes", ""),
            })

        self.recommended_routing = format_routing_summary(routing)
        self.routing_computed_on = now_datetime()

    # ── Die Layout ─────────────────────────────────────────────────────────────
    def _calc_die_layout(self):
        """Compute die layout if routing includes a die cut step."""
        if not (self.blank_length and self.blank_width):
            self.die_layout_outs = 0
            self.die_layout_waste_pct = 0
            self.die_layout_machine = None
            self.die_layout_orientation = ""
            return

        # Find die cut machine from routing steps
        die_cut_machine = None
        for step in (self.routing_steps or []):
            op = (step.operation or "").lower()
            if "die cut" in op or "die-cut" in op:
                die_cut_machine = step.machine
                break

        if not die_cut_machine:
            # Check if box style implies die cut
            style_upper = (self.box_style or "").upper().strip()
            if style_upper in ("DIE-CUT", "DC", "MAILER", "PIZZA", "TRAY", "SFF", "SNAP", "LOCK") or self.die_cut_special:
                # Try to find best die cut machine
                try:
                    from corrugated_estimating.corrugated_estimating.layout import calculate_layout_for_all_machines
                    layouts = calculate_layout_for_all_machines(
                        float(self.blank_length), float(self.blank_width)
                    )
                    if layouts:
                        best = layouts[0]
                        self.die_layout_outs = best["total_outs"]
                        self.die_layout_waste_pct = best["waste_pct"]
                        self.die_layout_machine = best["machine_id"]
                        self.die_layout_orientation = best["blank_orientation"]
                        return
                except ImportError:
                    pass

            self.die_layout_outs = 0
            self.die_layout_waste_pct = 0
            self.die_layout_machine = None
            self.die_layout_orientation = ""
            return

        try:
            from corrugated_estimating.corrugated_estimating.layout import calculate_die_layout
        except ImportError:
            return

        layout = calculate_die_layout(
            blank_length=float(self.blank_length),
            blank_width=float(self.blank_width),
            machine_id=die_cut_machine,
        )

        self.die_layout_outs = layout["total_outs"]
        self.die_layout_waste_pct = layout["waste_pct"]
        self.die_layout_machine = layout["machine_id"] or None
        self.die_layout_orientation = layout["blank_orientation"]

    # ── Quantity Rows ──────────────────────────────────────────────────────────
    def _calc_quantities(self):
        settings = get_settings()

        # Fetch board weight for freight calculation
        board_lbs_msf = 90.0
        if self.board_grade:
            try:
                bg = frappe.get_doc("Corrugated Board Grade", self.board_grade)
                if bg.lbs_msf:
                    board_lbs_msf = float(bg.lbs_msf)
            except frappe.DoesNotExistError:
                pass

        blank_area            = float(self.blank_area_sqft or 0)
        num_colors            = int(self.num_colors or 0)
        waste_pct             = float(self.waste_pct or 8)
        overhead_pct          = float(self.overhead_pct or 15)
        target_margin_pct     = float(self.target_margin_pct or 35)
        print_addon           = float(self.print_addon_per_color_msf or 4)
        tooling_cost          = float(self.tooling_cost or 0)
        setup_cost            = float(self.setup_cost or 0)
        freight_mode          = self.freight_mode or "LTL"
        freight_manual        = float(self.freight_manual_per_unit or 0)
        wax_treat             = bool(self.wax_water_resist)
        die_cut               = bool(self.die_cut_special)
        board_cost_default    = float(self.board_cost_default_msf or 180)

        # Build routing steps list for routing-based cost calculation
        routing_step_data = []
        for step in (self.routing_steps or []):
            routing_step_data.append({
                "operation": step.operation,
                "machine_id": step.machine or "",
                "machine_name": step.machine_name or "",
                "rate_msf": float(step.rate_msf or 0),
                "setup_cost": float(step.setup_cost or 0),
                "speed_per_hour": float(step.speed_per_hour or 0),
                "setup_time_min": float(step.setup_time_min or 0),
            })

        for row in self.quantities:
            qty            = int(row.quantity or 0)
            board_cost_msf = float(row.board_cost_msf or 0) or board_cost_default

            result = calculate_full_row(
                quantity               = qty,
                blank_area_sqft        = blank_area,
                board_cost_msf         = board_cost_msf,
                waste_pct              = waste_pct,
                num_colors             = num_colors,
                print_addon_per_color_msf = print_addon,
                wax_treat              = wax_treat,
                die_cut                = die_cut,
                overhead_pct           = overhead_pct,
                target_margin_pct      = target_margin_pct,
                tooling_cost           = tooling_cost,
                setup_cost             = setup_cost,
                freight_mode           = freight_mode,
                freight_manual_per_unit = freight_manual,
                board_lbs_msf          = board_lbs_msf,
                plate_charges          = float(row.plate_charges or 0),
                die_charge             = float(row.die_charge or 0),
                setup_charge_legacy    = float(row.setup_charge or 0),
                markup_pct             = float(row.markup_pct or 30),
                settings               = settings,
                routing_steps          = routing_step_data if routing_step_data else None,
                die_layout_outs        = int(self.die_layout_outs or 0),
            )

            row.material_cost   = result["material_cost"]
            row.converting_cost = result["converting_cost"]
            row.overhead_cost   = result["overhead_cost"]
            row.amort_fixed     = result["amort_fixed"]
            row.freight_cost    = result["freight_cost"]
            row.total_cogs      = result["total_cogs"]
            row.total_cost      = result["total_cost"]
            row.plate_charges   = result["plate_charges"]
            row.sell_price_m    = result["sell_price_m"]
            row.sell_price_unit = result["sell_price_unit"]
            row.extended_total  = result["extended_total"]

            # Populate routing time/cost on routing steps for this quantity
            if routing_step_data and qty > 0:
                self._update_routing_step_costs(qty, blank_area)

    def _update_routing_step_costs(self, quantity, blank_area_sqft):
        """Update run_time, total_time, and costs on routing step rows."""
        try:
            from corrugated_estimating.corrugated_estimating.routing import calculate_routing_cost
        except ImportError:
            return

        step_data = []
        for step in (self.routing_steps or []):
            step_data.append({
                "operation": step.operation,
                "machine_id": step.machine or "",
                "rate_msf": float(step.rate_msf or 0),
                "setup_cost": float(step.setup_cost or 0),
                "speed_per_hour": float(step.speed_per_hour or 0),
                "setup_time_min": float(step.setup_time_min or 0),
            })

        result = calculate_routing_cost(step_data, blank_area_sqft, quantity)

        for i, costed in enumerate(result.get("steps", [])):
            if i < len(self.routing_steps):
                self.routing_steps[i].run_cost = costed["run_cost"]
                self.routing_steps[i].run_time_hours = costed["run_time_hours"]
                self.routing_steps[i].total_time_hours = costed["total_time_hours"]
                self.routing_steps[i].total_step_cost = costed["total_step_cost"]

    def get_routing_summary(self):
        """Return a production routing summary dict."""
        total_setup_min = 0
        total_run_hrs = 0
        total_cost = 0
        bottleneck = None
        max_time = 0

        steps = []
        for step in (self.routing_steps or []):
            setup = float(step.setup_time_min or 0)
            run = float(step.run_time_hours or 0)
            cost = float(step.total_step_cost or 0)

            total_setup_min += setup
            total_run_hrs += run
            total_cost += cost

            if run > max_time:
                max_time = run
                bottleneck = step.machine_name or step.machine or ""

            steps.append({
                "sequence": step.sequence,
                "operation": step.operation,
                "machine": step.machine,
                "machine_name": step.machine_name,
                "setup_min": setup,
                "run_hours": run,
                "total_hours": float(step.total_time_hours or 0),
                "cost": cost,
            })

        return {
            "total_setup_minutes": total_setup_min,
            "total_run_hours": round(total_run_hrs, 2),
            "total_machine_cost": round(total_cost, 2),
            "bottleneck_machine": bottleneck or "",
            "steps": steps,
        }
