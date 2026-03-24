"""
Corrugated Box CAD Generator — DXF Flat Pattern Output
=======================================================
Generates industry-standard DXF die-cut flat patterns for corrugated boxes.
Each box style has its own generator function that draws panels, flaps,
score lines, slot cuts, and dimension annotations.

All measurements are in INCHES.

Layers:
  CUT       (red)   — outer edges, slot cuts, hand holes
  SCORE     (blue)  — fold/score lines (dashed)
  CREASE    (cyan)  — crease lines
  DIMENSION (green) — dimension annotations
  TITLE     (white) — title block, part info
"""

import os
import tempfile
import ezdxf
from ezdxf.enums import TextEntityAlignment

import frappe
from frappe.utils.file_manager import save_file

# ── Constants ────────────────────────────────────────────────────────────────
JOINT = 1.25  # manufacturer's joint in inches
MM_PER_INCH = 25.4


# ── DXF Setup ────────────────────────────────────────────────────────────────

def _setup_doc():
    """Create a new DXF document with standard corrugated layers."""
    doc = ezdxf.new(dxfversion="R2010")
    doc.layers.add("CUT", color=1)        # red
    doc.layers.add("SCORE", color=5)      # blue
    doc.layers.add("CREASE", color=4)     # cyan
    doc.layers.add("DIMENSION", color=3)  # green
    doc.layers.add("TITLE", color=7)      # white
    return doc


def _rect(msp, x0, y0, x1, y1, layer="CUT", close=True):
    """Draw a rectangle as a closed polyline."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    msp.add_lwpolyline(pts, close=close, dxfattribs={"layer": layer})


def _line(msp, x0, y0, x1, y1, layer="SCORE"):
    """Draw a single line."""
    msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": layer})


def _hdim(msp, x0, x1, y, offset=-1.5):
    """Horizontal dimension."""
    try:
        dim = msp.add_linear_dim(
            base=(x0, y + offset), p1=(x0, y), p2=(x1, y),
            dxfattribs={"layer": "DIMENSION"}
        )
        dim.render()
    except Exception:
        pass  # dimension rendering can fail in headless envs


def _vdim(msp, y0, y1, x, offset=-1.5):
    """Vertical dimension."""
    try:
        dim = msp.add_linear_dim(
            base=(x + offset, y0), p1=(x, y0), p2=(x, y1), angle=90,
            dxfattribs={"layer": "DIMENSION"}
        )
        dim.render()
    except Exception:
        pass


def _title_block(msp, x, y, lines):
    """Add title block text."""
    for i, text in enumerate(lines):
        height = 0.35 if i == 0 else 0.25
        msp.add_text(
            text, height=height,
            dxfattribs={"layer": "TITLE"}
        ).set_placement((x, y - i * 0.55), align=TextEntityAlignment.LEFT)


def _label(msp, x, y, text, height=0.3, layer="TITLE"):
    """Add a centered label."""
    msp.add_text(
        text, height=height,
        dxfattribs={"layer": layer}
    ).set_placement((x, y), align=TextEntityAlignment.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# BOX STYLE GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

def generate_rsc_dxf(L, W, D, caliper_in=0.146, estimate_name=""):
    """
    RSC (Regular Slotted Container) — FEFCO 0201
    Most common corrugated box. 4 panels + manufacturer's joint.
    Top and bottom flaps each D/2 high.
    Slot cuts between flaps so they fold independently.

    Layout (left to right):
        [Joint 1.25"] [Panel W] [Panel L] [Panel W] [Panel L]

    Vertical structure:
        [Bottom flaps D/2] [Body D] [Top flaps D/2]
    """
    doc = _setup_doc()
    msp = doc.modelspace()
    cal = caliper_in

    # Panel x-boundaries
    x0 = 0
    x1 = JOINT                    # joint to first panel
    x2 = JOINT + W                # end of first W panel
    x3 = JOINT + W + L            # end of first L panel
    x4 = JOINT + 2 * W + L        # end of second W panel
    x5 = JOINT + 2 * W + 2 * L    # right edge = blank_length

    # Flap y-boundaries
    flap_h = D / 2 + 2 * cal      # flap height with caliper allowance
    y0 = 0                         # bottom edge
    y1 = flap_h                    # bottom flap top / body bottom
    y2 = flap_h + D                # body top / top flap bottom
    y3 = 2 * flap_h + D           # top edge = blank_width

    # ── Outer boundary (CUT) ──────────────────────────────────────────
    _rect(msp, x0, y0, x5, y3, "CUT")

    # ── Vertical score lines between panels (body zone only) ─────────
    for x in [x1, x2, x3, x4]:
        _line(msp, x, y1, x, y2, "SCORE")

    # ── Horizontal score lines (flap junctions) ──────────────────────
    _line(msp, x0, y1, x5, y1, "SCORE")
    _line(msp, x0, y2, x5, y2, "SCORE")

    # ── Slot cuts (separate flaps) ───────────────────────────────────
    # Bottom flap slots
    for x in [x2, x3, x4]:
        _line(msp, x, y0, x, y1, "CUT")
    # Top flap slots
    for x in [x2, x3, x4]:
        _line(msp, x, y2, x, y3, "CUT")

    # ── Panel labels ─────────────────────────────────────────────────
    body_cy = (y1 + y2) / 2
    _label(msp, (x0 + x1) / 2, body_cy, "JOINT", 0.2)
    _label(msp, (x1 + x2) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x2 + x3) / 2, body_cy, f"L={L}\"", 0.25)
    _label(msp, (x3 + x4) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x4 + x5) / 2, body_cy, f"L={L}\"", 0.25)

    # Flap labels
    _label(msp, x5 / 2, (y0 + y1) / 2, f"BOTTOM FLAPS (D/2={D/2}\")", 0.2)
    _label(msp, x5 / 2, (y2 + y3) / 2, f"TOP FLAPS (D/2={D/2}\")", 0.2)

    # ── Dimensions ───────────────────────────────────────────────────
    _hdim(msp, x0, x5, y0, -2.0)  # overall length
    _hdim(msp, x1, x2, y3, 1.0)   # W panel
    _hdim(msp, x2, x3, y3, 1.0)   # L panel
    _vdim(msp, y0, y3, x0, -2.0)  # overall width
    _vdim(msp, y0, y1, x5, 1.5)   # bottom flap
    _vdim(msp, y1, y2, x5, 1.5)   # body depth

    # ── Title block ──────────────────────────────────────────────────
    _title_block(msp, x0, y0 - 3, [
        f"RSC (FEFCO 0201) — {estimate_name}",
        f"Inside: {L}\" x {W}\" x {D}\"  |  Blank: {x5:.2f}\" x {y3:.2f}\"",
        f"Flute caliper: {caliper_in:.3f}\"  |  Joint: {JOINT}\"",
    ])

    return doc


def generate_fol_dxf(L, W, D, caliper_in=0.146, estimate_name=""):
    """
    FOL (Full Overlap) — FEFCO 0203
    Like RSC but outer flaps (L-panel flaps) extend to full W width,
    overlapping completely. Inner flaps (W-panel) stay at D/2.
    """
    doc = _setup_doc()
    msp = doc.modelspace()
    cal = caliper_in

    x0, x1, x2, x3, x4, x5 = 0, JOINT, JOINT+W, JOINT+W+L, JOINT+2*W+L, JOINT+2*W+2*L
    flap_h = D / 2 + 2 * cal
    y0, y1, y2, y3 = 0, flap_h, flap_h + D, 2 * flap_h + D

    # Outer boundary
    _rect(msp, x0, y0, x5, y3, "CUT")

    # Panel scores (body zone)
    for x in [x1, x2, x3, x4]:
        _line(msp, x, y1, x, y2, "SCORE")

    # Flap junction scores
    _line(msp, x0, y1, x5, y1, "SCORE")
    _line(msp, x0, y2, x5, y2, "SCORE")

    # Slot cuts
    for x in [x2, x3, x4]:
        _line(msp, x, y0, x, y1, "CUT")
        _line(msp, x, y2, x, y3, "CUT")

    # FOL annotation: mark outer flaps as full overlap
    body_cy = (y1 + y2) / 2
    _label(msp, (x0 + x1) / 2, body_cy, "JOINT", 0.2)
    _label(msp, (x1 + x2) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x2 + x3) / 2, body_cy, f"L={L}\"", 0.25)
    _label(msp, (x3 + x4) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x4 + x5) / 2, body_cy, f"L={L}\"", 0.25)

    _label(msp, x5 / 2, (y0 + y1) / 2, "BOTTOM FLAPS (FULL OVERLAP)", 0.2)
    _label(msp, x5 / 2, (y2 + y3) / 2, "TOP FLAPS (FULL OVERLAP)", 0.2)

    # Overlap indicator: dashed lines showing where outer flaps meet
    mid_flap_bot = (y0 + y1) / 2
    mid_flap_top = (y2 + y3) / 2
    _line(msp, x2, mid_flap_bot, x3, mid_flap_bot, "CREASE")
    _line(msp, x2, mid_flap_top, x3, mid_flap_top, "CREASE")

    _hdim(msp, x0, x5, y0, -2.0)
    _vdim(msp, y0, y3, x0, -2.0)

    _title_block(msp, x0, y0 - 3, [
        f"FOL (FEFCO 0203) — {estimate_name}",
        f"Inside: {L}\" x {W}\" x {D}\"  |  Blank: {x5:.2f}\" x {y3:.2f}\"",
        f"Full Overlap — outer flaps extend full width",
    ])
    return doc


def generate_hsc_dxf(L, W, D, caliper_in=0.146, estimate_name=""):
    """
    HSC (Half Slotted Container) — FEFCO 0202
    Like RSC but only bottom flaps (open top).
    blank_width = D + D/2 + 2*caliper
    """
    doc = _setup_doc()
    msp = doc.modelspace()
    cal = caliper_in

    x0, x1, x2, x3, x4, x5 = 0, JOINT, JOINT+W, JOINT+W+L, JOINT+2*W+L, JOINT+2*W+2*L
    flap_h = D / 2 + cal
    y0 = 0
    y1 = flap_h              # bottom flap to body
    y2 = flap_h + D          # body top (= blank top, no top flaps)

    # Outer boundary
    _rect(msp, x0, y0, x5, y2, "CUT")

    # Panel scores
    for x in [x1, x2, x3, x4]:
        _line(msp, x, y1, x, y2, "SCORE")

    # Bottom flap junction
    _line(msp, x0, y1, x5, y1, "SCORE")

    # Bottom slot cuts
    for x in [x2, x3, x4]:
        _line(msp, x, y0, x, y1, "CUT")

    body_cy = (y1 + y2) / 2
    _label(msp, (x1 + x2) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x2 + x3) / 2, body_cy, f"L={L}\"", 0.25)
    _label(msp, (x3 + x4) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x4 + x5) / 2, body_cy, f"L={L}\"", 0.25)
    _label(msp, x5 / 2, (y0 + y1) / 2, f"BOTTOM FLAPS (D/2={D/2}\")", 0.2)
    _label(msp, x5 / 2, y2 + 0.5, "OPEN TOP", 0.25, "CUT")

    _hdim(msp, x0, x5, y0, -2.0)
    _vdim(msp, y0, y2, x0, -2.0)

    _title_block(msp, x0, y0 - 3, [
        f"HSC (FEFCO 0202) — {estimate_name}",
        f"Inside: {L}\" x {W}\" x {D}\"  |  Blank: {x5:.2f}\" x {y2:.2f}\"",
        f"Half Slotted — open top, bottom flaps only",
    ])
    return doc


def generate_tray_dxf(L, W, D, caliper_in=0.146, estimate_name=""):
    """
    TRAY — Open-top container with folding side walls.
    Cross-shaped flat pattern.
    blank_length = L + 2D + 2*JOINT
    blank_width  = W + 2D + 2*caliper
    """
    doc = _setup_doc()
    msp = doc.modelspace()
    cal = caliper_in

    total_l = L + 2 * D + 2 * JOINT
    total_w = W + 2 * D + 2 * cal

    # Center panel boundaries
    cx0 = D + JOINT          # left edge of center
    cx1 = cx0 + L            # right edge of center
    cy0 = D + cal            # bottom edge of center
    cy1 = cy0 + W            # top edge of center

    # ── Center panel ─────────────────────────────────────────────────
    _rect(msp, cx0, cy0, cx1, cy1, "SCORE")

    # ── Side walls (fold up) ─────────────────────────────────────────
    # Left wall
    _rect(msp, 0, cy0, cx0, cy1, "CUT")
    _line(msp, cx0, cy0, cx0, cy1, "SCORE")

    # Right wall
    _rect(msp, cx1, cy0, total_l, cy1, "CUT")
    _line(msp, cx1, cy0, cx1, cy1, "SCORE")

    # Bottom wall
    _rect(msp, cx0, 0, cx1, cy0, "CUT")
    _line(msp, cx0, cy0, cx1, cy0, "SCORE")

    # Top wall
    _rect(msp, cx0, cy1, cx1, total_w, "CUT")
    _line(msp, cx0, cy1, cx1, cy1, "SCORE")

    # ── Corner ears (fold and tuck) ──────────────────────────────────
    corners = [
        (0, 0, cx0, cy0),                    # bottom-left
        (cx1, 0, total_l, cy0),              # bottom-right
        (0, cy1, cx0, total_w),              # top-left
        (cx1, cy1, total_l, total_w),        # top-right
    ]
    for (ex0, ey0, ex1, ey1) in corners:
        _rect(msp, ex0, ey0, ex1, ey1, "CUT")
        # Diagonal score for ear fold
        _line(msp, ex0, ey0, ex1, ey1, "SCORE")

    # Labels
    _label(msp, (cx0 + cx1) / 2, (cy0 + cy1) / 2, f"BASE\n{L}\" x {W}\"", 0.3)
    _label(msp, cx0 / 2, (cy0 + cy1) / 2, f"D={D}\"", 0.2)
    _label(msp, (cx1 + total_l) / 2, (cy0 + cy1) / 2, f"D={D}\"", 0.2)
    _label(msp, (cx0 + cx1) / 2, cy0 / 2, f"D={D}\"", 0.2)
    _label(msp, (cx0 + cx1) / 2, (cy1 + total_w) / 2, f"D={D}\"", 0.2)

    _hdim(msp, 0, total_l, 0, -2.0)
    _vdim(msp, 0, total_w, 0, -2.0)

    _title_block(msp, 0, -3, [
        f"TRAY — {estimate_name}",
        f"Inside: {L}\" x {W}\" x {D}\"  |  Blank: {total_l:.2f}\" x {total_w:.2f}\"",
        f"Cross-shaped flat pattern with corner ears",
    ])
    return doc


def generate_bliss_dxf(L, W, D, caliper_in=0.146, estimate_name=""):
    """
    BLISS — Wrap-around box, no manufacturer's joint in traditional sense.
    blank_length = 2*(L+D) + JOINT
    blank_width  = W + D + 2*caliper

    Panels (left to right): [End D] [Body L] [End D] [Body L] [Joint]
    No top/bottom flaps — ends fold over to close.
    """
    doc = _setup_doc()
    msp = doc.modelspace()
    cal = caliper_in

    x0 = 0
    x1 = D                        # first end panel
    x2 = D + L                    # first body panel
    x3 = 2 * D + L                # second end panel
    x4 = 2 * D + 2 * L            # second body panel
    x5 = 2 * D + 2 * L + JOINT    # joint tab

    y0 = 0
    y1 = D + cal                   # lower fold
    y2 = D + cal + W               # body top = blank top (approx)
    blank_w = W + D + 2 * cal

    # Outer boundary
    _rect(msp, x0, y0, x5, blank_w, "CUT")

    # Panel scores
    for x in [x1, x2, x3, x4]:
        _line(msp, x, y0, x, blank_w, "SCORE")

    # Body/end fold score
    _line(msp, x0, y1, x5, y1, "SCORE")

    body_cy = (y1 + blank_w) / 2
    _label(msp, (x0 + x1) / 2, body_cy, f"END\nD={D}\"", 0.2)
    _label(msp, (x1 + x2) / 2, body_cy, f"BODY\nL={L}\"", 0.25)
    _label(msp, (x2 + x3) / 2, body_cy, f"END\nD={D}\"", 0.2)
    _label(msp, (x3 + x4) / 2, body_cy, f"BODY\nL={L}\"", 0.25)
    _label(msp, (x4 + x5) / 2, body_cy, "JNT", 0.15)
    _label(msp, x5 / 2, y1 / 2, f"BOTTOM FOLD (D={D}\")", 0.2)

    _hdim(msp, x0, x5, y0, -2.0)
    _vdim(msp, y0, blank_w, x0, -2.0)

    _title_block(msp, x0, y0 - 3, [
        f"BLISS — {estimate_name}",
        f"Inside: {L}\" x {W}\" x {D}\"  |  Blank: {x5:.2f}\" x {blank_w:.2f}\"",
        f"Wrap-around style — no flaps, ends fold over",
    ])
    return doc


def generate_diecut_dxf(L, W, D, caliper_in=0.146, estimate_name=""):
    """
    DIE-CUT — Generic custom die shape.
    blank_length = L + 2D + JOINT
    blank_width  = W + 2D

    Draws a simple rectangular outline with fold scores.
    Custom die shapes require separate die drawings.
    """
    doc = _setup_doc()
    msp = doc.modelspace()

    bl = L + 2 * D + JOINT
    bw = W + 2 * D

    # Outer boundary
    _rect(msp, 0, 0, bl, bw, "CUT")

    # Basic fold scores
    _line(msp, D, 0, D, bw, "SCORE")             # left fold
    _line(msp, D + L, 0, D + L, bw, "SCORE")     # right fold
    _line(msp, 0, D, bl, D, "SCORE")              # bottom fold
    _line(msp, 0, D + W, bl, D + W, "SCORE")      # top fold

    _label(msp, bl / 2, bw / 2, "CUSTOM DIE SHAPE", 0.4)
    _label(msp, bl / 2, bw / 2 - 0.8, "Refer to die drawing for details", 0.2)

    _label(msp, (D + D + L) / 2, (D + D + W) / 2, f"{L}\" x {W}\" x {D}\"", 0.25)

    _hdim(msp, 0, bl, 0, -2.0)
    _vdim(msp, 0, bw, 0, -2.0)

    _title_block(msp, 0, -3, [
        f"DIE-CUT — {estimate_name}",
        f"Inside: {L}\" x {W}\" x {D}\"  |  Blank: {bl:.2f}\" x {bw:.2f}\"",
        f"Custom die shape — see separate die drawing",
    ])
    return doc


def generate_sff_dxf(L, W, D, caliper_in=0.146, estimate_name=""):
    """
    SFF (Snap/Lock Bottom) — FEFCO 0210
    Same body panels as RSC. Top flaps standard.
    Bottom flaps have interlocking lock tabs.

    Blank formula same as RSC: 2*(L+W) + 1.25 x 2*D + 4*caliper
    """
    doc = _setup_doc()
    msp = doc.modelspace()
    cal = caliper_in

    x0, x1, x2, x3, x4, x5 = 0, JOINT, JOINT+W, JOINT+W+L, JOINT+2*W+L, JOINT+2*W+2*L
    flap_h = D / 2 + 2 * cal
    y0, y1, y2, y3 = 0, flap_h, flap_h + D, 2 * flap_h + D

    # Outer boundary
    _rect(msp, x0, y0, x5, y3, "CUT")

    # Panel scores
    for x in [x1, x2, x3, x4]:
        _line(msp, x, y1, x, y2, "SCORE")

    # Flap junction scores
    _line(msp, x0, y1, x5, y1, "SCORE")
    _line(msp, x0, y2, x5, y2, "SCORE")

    # Top flap slots (standard, same as RSC)
    for x in [x2, x3, x4]:
        _line(msp, x, y2, x, y3, "CUT")

    # Bottom flap slots
    for x in [x2, x3, x4]:
        _line(msp, x, y0, x, y1, "CUT")

    # Lock tab indicators on bottom flaps (L-panel flaps)
    # Draw small notches on the inner flaps and tabs on outer flaps
    tab_w = 0.75  # tab width
    tab_h = 0.5   # tab depth

    # Lock tabs on L-panel bottom flaps (at x2-x3 and x4-x5)
    for fx0, fx1 in [(x2, x3), (x4, x5)]:
        mid = (fx0 + fx1) / 2
        # Tab cutout
        _rect(msp, mid - tab_w, y0, mid + tab_w, y0 + tab_h, "CUT")
        # Lock notch on adjacent W-panel flap
        _line(msp, mid - tab_w, y0 + tab_h, mid + tab_w, y0 + tab_h, "SCORE")

    # W-panel bottom flaps get lock slots
    for fx0, fx1 in [(x1, x2), (x3, x4)]:
        mid = (fx0 + fx1) / 2
        # Slot opening for tab
        _rect(msp, mid - tab_w * 0.8, y1 - tab_h, mid + tab_w * 0.8, y1, "CUT")

    # Labels
    body_cy = (y1 + y2) / 2
    _label(msp, (x0 + x1) / 2, body_cy, "JNT", 0.15)
    _label(msp, (x1 + x2) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x2 + x3) / 2, body_cy, f"L={L}\"", 0.25)
    _label(msp, (x3 + x4) / 2, body_cy, f"W={W}\"", 0.25)
    _label(msp, (x4 + x5) / 2, body_cy, f"L={L}\"", 0.25)

    _label(msp, x5 / 2, (y0 + y1) / 2, "LOCK BOTTOM", 0.2)
    _label(msp, x5 / 2, (y2 + y3) / 2, f"TOP FLAPS (D/2={D/2}\")", 0.2)

    _hdim(msp, x0, x5, y0, -2.5)
    _vdim(msp, y0, y3, x0, -2.0)

    _title_block(msp, x0, y0 - 3.5, [
        f"SFF / Snap Lock Bottom (FEFCO 0210) — {estimate_name}",
        f"Inside: {L}\" x {W}\" x {D}\"  |  Blank: {x5:.2f}\" x {y3:.2f}\"",
        f"Lock tab bottom — auto-erect design",
    ])
    return doc


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER + FRAPPE INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

GENERATORS = {
    "RSC":    generate_rsc_dxf,
    "FOL":    generate_fol_dxf,
    "HSC":    generate_hsc_dxf,
    "TRAY":   generate_tray_dxf,
    "BLISS":  generate_bliss_dxf,
    "DIECUT": generate_diecut_dxf,
    "DIE":    generate_diecut_dxf,
    "DC":     generate_diecut_dxf,
    "SFF":    generate_sff_dxf,
    "SNAP":   generate_sff_dxf,
    "LOCK":   generate_sff_dxf,
}


def generate_cad_for_estimate(estimate_name):
    """
    Main entry point: load estimate, generate DXF, attach to cad_file field.

    Returns the file URL or None.
    """
    doc = frappe.get_doc("Corrugated Estimate", estimate_name)

    L = float(doc.length_inside or 0)
    W = float(doc.width_inside or 0)
    D = float(doc.depth_inside or 0)

    if not (L and W and D):
        return None

    # Get caliper from flute
    caliper_in = 0.0
    if doc.flute_type:
        try:
            flute = frappe.get_doc("Corrugated Flute", doc.flute_type)
            caliper_in = float(flute.caliper_mm or 0) / MM_PER_INCH
        except frappe.DoesNotExistError:
            caliper_in = 3.7 / MM_PER_INCH  # default C-flute

    if not caliper_in:
        caliper_in = 3.7 / MM_PER_INCH

    # Resolve style
    style = (doc.box_style or "RSC").upper().replace("-", "").replace(" ", "")
    generator = GENERATORS.get(style, generate_rsc_dxf)

    # Generate DXF
    dxf_doc = generator(L, W, D, caliper_in, estimate_name)

    # Save to temp file
    filename = f"{estimate_name}_{style}.dxf"
    tmp_path = os.path.join(tempfile.gettempdir(), filename)
    dxf_doc.saveas(tmp_path)

    # Remove old CAD file if exists
    if doc.cad_file:
        old_files = frappe.get_all(
            "File",
            filters={"file_url": doc.cad_file, "attached_to_name": estimate_name},
            pluck="name",
        )
        for f in old_files:
            frappe.delete_doc("File", f, ignore_permissions=True)

    # Attach new file
    with open(tmp_path, "rb") as f:
        file_doc = save_file(
            filename, f.read(),
            "Corrugated Estimate", estimate_name,
            is_private=1,
        )

    # Clean up temp
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    # Update cad_file field
    frappe.db.set_value(
        "Corrugated Estimate", estimate_name,
        "cad_file", file_doc.file_url,
    )

    return file_doc.file_url
