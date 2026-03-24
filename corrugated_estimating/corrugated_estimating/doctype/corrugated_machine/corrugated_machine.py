import frappe
from frappe.model.document import Document


class CorrugatedMachine(Document):
    def validate(self):
        self._validate_size_ranges()

    def _validate_size_ranges(self):
        pairs = [
            ("blank_min_length", "blank_max_length", "Blank Length"),
            ("blank_min_width", "blank_max_width", "Blank Width"),
            ("panel_min_length", "panel_max_length", "Panel Length"),
            ("panel_min_width", "panel_max_width", "Panel Width"),
            ("panel_min_depth", "panel_max_depth", "Panel Depth"),
        ]
        for min_f, max_f, label in pairs:
            min_v = self.get(min_f) or 0
            max_v = self.get(max_f) or 0
            if min_v and max_v and min_v > max_v:
                frappe.throw(f"{label}: minimum ({min_v}) cannot exceed maximum ({max_v})")

    def get_speed_per_hour(self):
        """Normalize speed to per-hour regardless of stored unit."""
        if not self.speed_value:
            return 0
        if self.speed_unit == "per minute":
            return self.speed_value * 60
        return self.speed_value

    def blank_fits(self, blank_length, blank_width):
        """Check if a blank fits within this machine's size envelope."""
        if not all([self.blank_min_length, self.blank_min_width,
                    self.blank_max_length, self.blank_max_width]):
            return True  # no constraints defined

        # Try both orientations (L x W) and (W x L)
        fits_normal = (
            self.blank_min_length <= blank_length <= self.blank_max_length
            and self.blank_min_width <= blank_width <= self.blank_max_width
        )
        fits_rotated = (
            self.blank_min_length <= blank_width <= self.blank_max_length
            and self.blank_min_width <= blank_length <= self.blank_max_width
        )
        return fits_normal or fits_rotated

    def panel_fits(self, panel_l, panel_w, panel_d):
        """Check if panel dimensions fit within this machine's panel constraints."""
        checks = []
        if self.panel_min_length and panel_l:
            checks.append(panel_l >= self.panel_min_length)
        if self.panel_max_length and panel_l:
            checks.append(panel_l <= self.panel_max_length)
        if self.panel_min_width and panel_w:
            checks.append(panel_w >= self.panel_min_width)
        if self.panel_max_width and panel_w:
            checks.append(panel_w <= self.panel_max_width)
        if self.panel_min_depth and panel_d:
            checks.append(panel_d >= self.panel_min_depth)
        if self.panel_max_depth and panel_d:
            checks.append(panel_d <= self.panel_max_depth)
        return all(checks) if checks else True
