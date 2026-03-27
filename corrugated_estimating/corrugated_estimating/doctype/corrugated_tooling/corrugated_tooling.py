import frappe
from frappe.model.document import Document


class CorrugatedTooling(Document):
    def before_save(self):
        # Auto-generate tooling name if empty
        if not self.tooling_name and self.box_style:
            self.tooling_name = "{style} {L}x{W}x{D} {type}".format(
                style=self.box_style or "Box",
                L=self.length_inside or 0,
                W=self.width_inside or 0,
                D=self.depth_inside or 0,
                type=self.tooling_type or "Die",
            )

    def on_update(self):
        # Update last_used_date when impressions change
        if self.has_value_changed("num_impressions"):
            self.last_used_date = frappe.utils.today()
