"""
Corrugated Part Kit — groups multiple die-cut pieces (body + partitions + pads)
for nesting together on a single die sheet.
"""

import frappe
from frappe.model.document import Document
from corrugated_estimating.corrugated_estimating.utils import calculate_blank_size


class CorrugatedPartKit(Document):
    def before_save(self):
        self._calc_blank_sizes()
        self._calc_layout()

    def _calc_blank_sizes(self):
        """Calculate blank dimensions for each part."""
        for part in self.parts:
            L = float(part.length or 0)
            W = float(part.width or 0)
            D = float(part.depth or 0)
            style = part.box_style or "PAD"

            caliper_mm = 3.7  # default C-flute
            flute = part.flute_type or self.flute_type
            if flute:
                try:
                    flute_doc = frappe.get_doc("Corrugated Flute", flute)
                    caliper_mm = float(flute_doc.caliper_mm or 3.7)
                except frappe.DoesNotExistError:
                    pass

            if part.part_type in ("Pad", "Insert", "Liner", "Divider"):
                # Simple rectangle — blank = L x W
                part.blank_length = L
                part.blank_width = W
                part.blank_area_sqft = round((L * W) / 144.0, 6)
            else:
                bl, bw, area = calculate_blank_size(
                    style, L, W, D, caliper_mm
                )
                part.blank_length = round(bl, 4)
                part.blank_width = round(bw, 4)
                part.blank_area_sqft = round(area, 6)

    def _calc_layout(self):
        """Calculate multi-part die layout for the kit."""
        from corrugated_estimating.corrugated_estimating.layout import (
            calculate_multi_part_layout,
        )

        part_specs = []
        for part in self.parts:
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
            return

        result = calculate_multi_part_layout(part_specs)
        if result and not result.get("error"):
            self.layout_machine = result.get("machine_id", "")
            self.layout_outs = result.get("total_outs", 0)
            self.layout_waste_pct = result.get("waste_pct", 0)
            self.layout_sheet_length = result.get("sheet_length", 0)
            self.layout_sheet_width = result.get("sheet_width", 0)
            self.layout_utilization_pct = result.get("utilization_pct", 0)
