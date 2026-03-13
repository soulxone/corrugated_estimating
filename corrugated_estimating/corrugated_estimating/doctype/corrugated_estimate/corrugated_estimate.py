import frappe
from frappe.model.document import Document
from corrugated_estimating.corrugated_estimating.utils import (
    calculate_blank_size,
    calculate_full_row,
    get_settings,
)


class CorrugatedEstimate(Document):

    def before_save(self):
        """Recalculate blank size and all quantity row costs on every save."""
        if not self.estimate_no:
            self.estimate_no = self.name
        self._calc_blank_size()
        self._calc_quantities()

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
