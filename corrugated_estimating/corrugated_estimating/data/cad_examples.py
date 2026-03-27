"""
CAD Box Style Examples — Generate DXF files + Frappe Estimates
==============================================================
Creates one example estimate per box style with realistic dimensions,
generates the DXF CAD file, and attaches it to the estimate.

Run from bench console:
    bench --site <site> execute corrugated_estimating.corrugated_estimating.data.cad_examples.generate_all

Or generate DXF files locally (no Frappe required):
    python -m corrugated_estimating.corrugated_estimating.data.cad_examples --local
"""

# ── Example definitions ──────────────────────────────────────────────────────
# (style_code, description, L, W, D, flute, wall_type, board_grade, customer_note)

EXAMPLES = [
    {
        "style": "RSC",
        "name": "RSC — Shipping Box",
        "description": "Standard RSC shipping box for general merchandise",
        "L": 16, "W": 12, "D": 10,
        "flute": "C-Flute",
        "wall": "Single Wall",
        "grade": "SW 32 ECT",
        "colors": 2,
        "quantity": 5000,
    },
    {
        "style": "FOL",
        "name": "FOL — Full Overlap",
        "description": "Full overlap slotted container for heavy auto parts",
        "L": 20, "W": 14, "D": 12,
        "flute": "C-Flute",
        "wall": "Single Wall",
        "grade": "SW 44 ECT",
        "colors": 1,
        "quantity": 2500,
    },
    {
        "style": "HSC",
        "name": "HSC — Half Slotted",
        "description": "Half slotted container for lid/tray combos",
        "L": 18, "W": 14, "D": 6,
        "flute": "B-Flute",
        "wall": "Single Wall",
        "grade": "SW 32 ECT",
        "colors": 3,
        "quantity": 10000,
    },
    {
        "style": "TRAY",
        "name": "TRAY — Display Tray",
        "description": "Open-top display tray for retail point-of-sale",
        "L": 24, "W": 16, "D": 4,
        "flute": "B-Flute",
        "wall": "Single Wall",
        "grade": "SW 200# Mullen",
        "colors": 4,
        "quantity": 15000,
    },
    {
        "style": "BLISS",
        "name": "BLISS — Bliss Style Box",
        "description": "Three-piece bliss box for heavy industrial parts",
        "L": 30, "W": 20, "D": 18,
        "flute": "C-Flute",
        "wall": "Double Wall",
        "grade": "DW 51 ECT",
        "colors": 1,
        "quantity": 1000,
    },
    {
        "style": "DIECUT",
        "name": "DIECUT — Mailer Box",
        "description": "Die-cut mailer with tuck flaps for e-commerce",
        "L": 12, "W": 9, "D": 3,
        "flute": "E-Flute",
        "wall": "Single Wall",
        "grade": "SW 32 ECT",
        "colors": 4,
        "quantity": 25000,
    },
    {
        "style": "SFF",
        "name": "SFF — Snap Lock Bottom",
        "description": "Snap-lock four-flap bottom with auto-erect setup",
        "L": 10, "W": 8, "D": 6,
        "flute": "B-Flute",
        "wall": "Single Wall",
        "grade": "SW 200# Mullen",
        "colors": 3,
        "quantity": 8000,
    },
    {
        "style": "RAG",
        "name": "RAG — Rag Dispenser",
        "description": "Industrial rag/wipe dispenser box with pull-hole",
        "L": 14, "W": 10, "D": 10,
        "flute": "C-Flute",
        "wall": "Single Wall",
        "grade": "SW 32 ECT",
        "colors": 2,
        "quantity": 3000,
    },
    {
        "style": "WORTHINGTON",
        "name": "WORTHINGTON — Freon Tank Box",
        "description": "Cylindrical tank shipper for Worthington freon tanks",
        "L": 14, "W": 14, "D": 18,
        "flute": "C-Flute",
        "wall": "Double Wall",
        "grade": "DW 48 ECT",
        "colors": 1,
        "quantity": 2000,
    },
]


# ── Local DXF Generation (no Frappe) ─────────────────────────────────────────

def generate_local(output_dir=None):
    """Generate DXF files locally without Frappe. Returns list of file paths."""
    import os
    import sys

    # Add the parent package to sys.path so we can import cad_generator
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

    # We need to mock frappe since cad_generator imports it at module level
    import types
    if 'frappe' not in sys.modules:
        fm = types.ModuleType('frappe')
        fm.DoesNotExistError = type('DoesNotExistError', (Exception,), {})
        fm.whitelist = lambda: (lambda f: f)
        fm.utils = types.ModuleType('frappe.utils')
        fm.utils.file_manager = types.ModuleType('frappe.utils.file_manager')
        fm.utils.file_manager.save_file = lambda *a, **k: None
        sys.modules['frappe'] = fm
        sys.modules['frappe.utils'] = fm.utils
        sys.modules['frappe.utils.file_manager'] = fm.utils.file_manager

    from cad_generator import (
        generate_rsc_dxf, generate_fol_dxf, generate_hsc_dxf,
        generate_tray_dxf, generate_bliss_dxf, generate_diecut_dxf,
        generate_sff_dxf, generate_rag_dispenser_dxf, generate_worthington_dxf,
        GENERATORS,
    )

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '..', '..', '..', 'cad_examples')
    os.makedirs(output_dir, exist_ok=True)

    # Flute caliper lookup (inches)
    CALIPER = {
        "A-Flute": 4.8 / 25.4,
        "B-Flute": 3.0 / 25.4,
        "C-Flute": 3.7 / 25.4,
        "E-Flute": 1.6 / 25.4,
        "F-Flute": 0.8 / 25.4,
        "BC-Flute": 6.5 / 25.4,
    }

    files = []
    for ex in EXAMPLES:
        style = ex["style"]
        L, W, D = ex["L"], ex["W"], ex["D"]
        cal = CALIPER.get(ex["flute"], 3.7 / 25.4)
        est_name = f"EXAMPLE-{style}"

        generator = GENERATORS.get(style, generate_rsc_dxf)
        dxf_doc = generator(L, W, D, cal, est_name)

        filename = f"{style}_{L}x{W}x{D}.dxf"
        filepath = os.path.join(output_dir, filename)
        dxf_doc.saveas(filepath)
        files.append(filepath)
        print(f"  Generated: {filename}  ({ex['name']})")

    print(f"\n  {len(files)} DXF files saved to: {output_dir}")
    return files


# ── Frappe Estimate + CAD Generation ─────────────────────────────────────────

def generate_all():
    """
    Create example estimates in Frappe and generate CAD files for each.
    Run via: bench --site <site> execute
        corrugated_estimating.corrugated_estimating.data.cad_examples.generate_all
    """
    import frappe
    from corrugated_estimating.corrugated_estimating.cad_generator import (
        generate_cad_for_estimate,
    )

    created = []
    for ex in EXAMPLES:
        style = ex["style"]
        est_name_tag = f"CAD-EXAMPLE-{style}"

        # Check if example already exists (by customer note convention)
        existing = frappe.db.get_all(
            "Corrugated Estimate",
            filters={"customer": est_name_tag},
            pluck="name",
            limit=1,
        )

        if existing:
            est_name = existing[0]
            print(f"  Updating existing: {est_name} ({style})")
            doc = frappe.get_doc("Corrugated Estimate", est_name)
        else:
            print(f"  Creating new estimate for: {style}")
            doc = frappe.new_doc("Corrugated Estimate")

        # Set fields
        doc.customer = est_name_tag
        doc.box_style = style
        doc.length_inside = ex["L"]
        doc.width_inside = ex["W"]
        doc.depth_inside = ex["D"]
        doc.wall_type = ex["wall"]
        doc.num_colors = ex.get("colors", 1)

        # Set flute if the doctype record exists
        if frappe.db.exists("Corrugated Flute", ex["flute"]):
            doc.flute_type = ex["flute"]

        # Set board grade if it exists
        if ex.get("grade") and frappe.db.exists("Corrugated Board Grade", ex["grade"]):
            doc.board_grade = ex["grade"]

        doc.save(ignore_permissions=True)
        est_name = doc.name

        # Add a quantity row
        if not doc.get("quantity_breaks"):
            row = doc.append("quantity_breaks", {})
            row.quantity = ex.get("quantity", 5000)
            doc.save(ignore_permissions=True)

        # Generate CAD file
        try:
            file_url = generate_cad_for_estimate(est_name)
            if file_url:
                print(f"    CAD: {file_url}")
            else:
                print(f"    CAD: generation returned None (check dimensions)")
        except Exception as e:
            print(f"    CAD ERROR: {e}")

        created.append({
            "estimate": est_name,
            "style": style,
            "description": ex["name"],
            "dimensions": f"{ex['L']}x{ex['W']}x{ex['D']}",
        })

    frappe.db.commit()

    print(f"\n{'='*60}")
    print(f"  Created {len(created)} example estimates with CAD files:")
    print(f"{'='*60}")
    for c in created:
        print(f"  {c['estimate']:20s}  {c['style']:15s}  {c['dimensions']:12s}  {c['description']}")

    return created


# ── CLI Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if "--local" in sys.argv:
        output = None
        for i, arg in enumerate(sys.argv):
            if arg == "--output" and i + 1 < len(sys.argv):
                output = sys.argv[i + 1]
        print("Generating CAD examples (local mode)...")
        generate_local(output)
    else:
        print("Usage:")
        print("  Local:  python cad_examples.py --local [--output DIR]")
        print("  Frappe: bench --site <site> execute corrugated_estimating.corrugated_estimating.data.cad_examples.generate_all")
