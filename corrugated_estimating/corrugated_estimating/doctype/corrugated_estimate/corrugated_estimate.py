import frappe
from frappe.model.document import Document
from corrugated_estimating.corrugated_estimating.utils import (
    calculate_blank_size,
    calculate_material_cost,
    calculate_print_cost,
)


class CorrugatedEstimate(Document):

    def before_save(self):
        """Recalculate blank size and all quantity row costs on every save."""
        self._calc_blank_size()
        self._calc_quantities()

    # ── Blank Size ─────────────────────────────────────────────────────────────
    def _calc_blank_size(self):
        if not (self.length_inside and self.width_inside and self.depth_inside):
            return

        caliper_mm = 0.0
        if self.flute_type:
            flute = frappe.get_doc("Corrugated Flute", self.flute_type)
            caliper_mm = flute.caliper_mm or 0.0

        box_style = self.box_style or "RSC"
        bl, bw, area = calculate_blank_size(
            box_style,
            float(self.length_inside),
            float(self.width_inside),
            float(self.depth_inside),
            caliper_mm,
        )
        self.blank_length = round(bl, 4)
        self.blank_width = round(bw, 4)
        self.blank_area_sqft = round(area, 6)

    # ── Quantity Rows ──────────────────────────────────────────────────────────
    def _calc_quantities(self):
        print_method_doc = None
        if self.print_method:
            try:
                print_method_doc = frappe.get_doc("Corrugated Print Method", self.print_method)
            except frappe.DoesNotExistError:
                pass

        num_colors = int(self.num_colors or 0)
        blank_area = float(self.blank_area_sqft or 0)

        for row in self.quantities:
            qty = int(row.quantity or 0)
            board_cost_msf = float(row.board_cost_msf or 0)

            # Material cost
            mat_cost = calculate_material_cost(blank_area, board_cost_msf, qty)
            row.material_cost = round(mat_cost, 2)

            # Print cost (plates only per row — setup shared across qty breaks)
            print_cost = 0.0
            if print_method_doc:
                print_cost = calculate_print_cost(num_colors, print_method_doc)
            row.plate_charges = round(print_cost, 2)

            # Total cost = material + plate + die + setup
            row.total_cost = round(
                (row.material_cost or 0)
                + (row.plate_charges or 0)
                + (row.die_charge or 0)
                + (row.setup_charge or 0),
                2,
            )

            # Sell price with markup
            markup = float(row.markup_pct or 30) / 100.0
            if qty > 0:
                sell_total = row.total_cost * (1 + markup)
                row.sell_price_m = round((sell_total / qty) * 1000, 2)
                row.sell_price_unit = round(sell_total / qty, 6)
                row.extended_total = round(sell_total, 2)
            else:
                row.sell_price_m = 0
                row.sell_price_unit = 0
                row.extended_total = 0
