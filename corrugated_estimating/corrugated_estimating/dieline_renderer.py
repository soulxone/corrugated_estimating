"""
Corrugated Box Dieline SVG Renderer
====================================
Generates SVG path/line elements for box flat patterns with industry-standard
line colors (Pacdora-style):

  CUT    — Blue (#0066CC)  solid        — outer edges, slots, hand holes
  SCORE  — Red  (#CC0000)  dashed 3,2   — fold/crease lines
  FOLD   — Green(#009933)  dotted 1,2   — bleed/fold reference
  GLUE   — Orange(#FF6600) dash-dot     — glue tab outlines

Each generator returns a list of SVG element dicts that the front-end
renders inside each blank rectangle in the Die Layout Viewer.

All coordinates are in INCHES relative to the blank origin (0,0).
The front-end scales them to match the SVG viewport.
"""

import math

# ── Constants ────────────────────────────────────────────────────────────────
JOINT = 1.25  # manufacturer's joint width (inches)

# Line style definitions (for front-end SVG rendering)
# Thinner professional line weights for clean dieline rendering
LINE_STYLES = {
    "CUT":   {"stroke": "#0066CC", "stroke_width": 0.3, "dash": ""},
    "SCORE": {"stroke": "#CC0000", "stroke_width": 0.25, "dash": "3,2"},
    "FOLD":  {"stroke": "#009933", "stroke_width": 0.2, "dash": "1,2"},
    "GLUE":  {"stroke": "#FF6600", "stroke_width": 0.25, "dash": "4,2,1,2"},
    "DIM":   {"stroke": "#666666", "stroke_width": 0.15, "dash": ""},
}


# ── SVG Element Builders ─────────────────────────────────────────────────────

def _line(x1, y1, x2, y2, line_type="CUT"):
    """Create a line element dict."""
    return {"type": "line", "x1": round(x1, 3), "y1": round(y1, 3),
            "x2": round(x2, 3), "y2": round(y2, 3), "line_type": line_type}


def _rect(x, y, w, h, line_type="CUT"):
    """Create a rectangle element dict (unfilled outline)."""
    return {"type": "rect", "x": round(x, 3), "y": round(y, 3),
            "width": round(w, 3), "height": round(h, 3), "line_type": line_type}


def _polyline(points, line_type="CUT", closed=False):
    """Create a polyline element dict."""
    return {"type": "polyline",
            "points": [(round(x, 3), round(y, 3)) for x, y in points],
            "closed": closed, "line_type": line_type}


def _circle(cx, cy, r, line_type="CUT"):
    """Create a circle element dict."""
    return {"type": "circle", "cx": round(cx, 3), "cy": round(cy, 3),
            "r": round(r, 3), "line_type": line_type}


def _ellipse(cx, cy, rx, ry, line_type="CUT"):
    """Create an ellipse element dict (for oblong hand holes)."""
    return {"type": "ellipse", "cx": round(cx, 3), "cy": round(cy, 3),
            "rx": round(rx, 3), "ry": round(ry, 3), "line_type": line_type}


def _label(x, y, text, size=0.2):
    """Create a text label element dict."""
    return {"type": "label", "x": round(x, 3), "y": round(y, 3),
            "text": text, "size": round(size, 3)}


def _dim_line(x1, y1, x2, y2, text, offset=0.4, side="outside"):
    """Dimension annotation: line with arrowhead ticks + centered text."""
    return {"type": "dimension", "x1": round(x1, 3), "y1": round(y1, 3),
            "x2": round(x2, 3), "y2": round(y2, 3),
            "text": text, "offset": round(offset, 3), "side": side,
            "line_type": "DIM"}


def _arc(cx, cy, r, start_angle, end_angle, line_type="CUT"):
    """Arc element for circular cutouts (cradle cuts, holes)."""
    return {"type": "arc", "cx": round(cx, 3), "cy": round(cy, 3),
            "r": round(r, 3), "start_angle": round(start_angle, 1),
            "end_angle": round(end_angle, 1), "line_type": line_type}


def _path(d, line_type="CUT"):
    """SVG path element for complex shapes."""
    return {"type": "path", "d": d, "line_type": line_type}


# ── Dimension Measurement Generator ──────────────────────────────────────────

def generate_measurements(result):
    """
    Append outside and inside dimension annotations to a render result.

    Outside: overall blank_length (bottom) and blank_width (left side).
    Inside: per-panel widths (top) and flap heights (right side) for RSC-family styles.
    """
    elements = result["elements"]
    bl = result["blank_length"]
    bw = result["blank_width"]
    style = result.get("style", "RSC").upper()

    # Outside dimensions
    elements.append(_dim_line(0, bw, bl, bw, f'{bl:.2f}"', offset=1.2, side="outside"))
    elements.append(_dim_line(0, 0, 0, bw, f'{bw:.2f}"', offset=-1.2, side="outside"))

    # Inside panel dimensions (RSC-family: JOINT + W + L + W + L)
    if style in ("RSC", "FOL", "HSC", "SFF", "SNAP", "LOCK", "OPF", "CSSC", "RAG", "RAGDISP"):
        cal = 0.146  # approximate
        flap_h = bw / 2 if style != "HSC" else bw * 0.4
        body_top = bw - flap_h if style != "HSC" else bw

        # Panel widths along top
        joint_w = JOINT if style not in ("RAG", "RAGDISP") else 2.5
        # We can't recover exact L,W from blank dims alone, so use label positions
        # Instead, add a simplified "inside dims" label
        elements.append(_dim_line(0, 0, joint_w, 0, f'{joint_w:.1f}"', offset=-0.6, side="inside"))

    elif style in ("TRAY", "FTC", "HTC", "DST"):
        # Tray: cross-shaped — show center panel + side wall dims
        pass  # measurements built into the cross shape labels

    elif style in ("BLISS", "BLI", "ROLLA"):
        # Bliss: wrap-around panels
        pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
# BOX STYLE SVG GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

def render_rsc(L, W, D, caliper_in=0.146):
    """
    RSC (Regular Slotted Container) — FEFCO 0201

    Layout (left→right): [Joint 1.25"] [W] [L] [W] [L]
    Vertical: [Bottom flaps D/2] [Body D] [Top flaps D/2]
    """
    cal = caliper_in
    elements = []

    # Panel x-boundaries
    x0 = 0
    x1 = JOINT
    x2 = JOINT + W
    x3 = JOINT + W + L
    x4 = JOINT + 2 * W + L
    x5 = JOINT + 2 * W + 2 * L  # blank_length

    # Flap y-boundaries
    flap_h = D / 2 + 2 * cal
    y0 = 0
    y1 = flap_h
    y2 = flap_h + D
    y3 = 2 * flap_h + D  # blank_width

    # Outer boundary (CUT)
    elements.append(_rect(x0, y0, x5, y3, "CUT"))

    # Vertical score lines between panels (body zone)
    for x in [x1, x2, x3, x4]:
        elements.append(_line(x, y1, x, y2, "SCORE"))

    # Horizontal score lines (flap junctions)
    elements.append(_line(x0, y1, x5, y1, "SCORE"))
    elements.append(_line(x0, y2, x5, y2, "SCORE"))

    # Slot cuts (separate flaps)
    for x in [x2, x3, x4]:
        elements.append(_line(x, y0, x, y1, "CUT"))  # bottom
        elements.append(_line(x, y2, x, y3, "CUT"))  # top

    # Panel labels
    body_cy = (y1 + y2) / 2
    elements.append(_label((x0 + x1) / 2, body_cy, "JNT", 0.15))
    elements.append(_label((x1 + x2) / 2, body_cy, f"W", 0.18))
    elements.append(_label((x2 + x3) / 2, body_cy, f"L", 0.18))
    elements.append(_label((x3 + x4) / 2, body_cy, f"W", 0.18))
    elements.append(_label((x4 + x5) / 2, body_cy, f"L", 0.18))

    return {
        "elements": elements,
        "blank_length": round(x5, 3),
        "blank_width": round(y3, 3),
        "style": "RSC",
        "fefco": "0201",
    }


def render_fol(L, W, D, caliper_in=0.146):
    """
    FOL (Full Overlap) — FEFCO 0203
    Like RSC but outer flaps extend full W width.
    """
    cal = caliper_in
    elements = []

    x0, x1, x2, x3, x4, x5 = 0, JOINT, JOINT+W, JOINT+W+L, JOINT+2*W+L, JOINT+2*W+2*L
    flap_h = D / 2 + 2 * cal
    y0, y1, y2, y3 = 0, flap_h, flap_h + D, 2 * flap_h + D

    # Outer boundary
    elements.append(_rect(x0, y0, x5, y3, "CUT"))

    # Panel scores (body)
    for x in [x1, x2, x3, x4]:
        elements.append(_line(x, y1, x, y2, "SCORE"))

    # Flap junctions
    elements.append(_line(x0, y1, x5, y1, "SCORE"))
    elements.append(_line(x0, y2, x5, y2, "SCORE"))

    # Slot cuts
    for x in [x2, x3, x4]:
        elements.append(_line(x, y0, x, y1, "CUT"))
        elements.append(_line(x, y2, x, y3, "CUT"))

    # Overlap indicator lines (FOLD)
    mid_bot = (y0 + y1) / 2
    mid_top = (y2 + y3) / 2
    elements.append(_line(x2, mid_bot, x3, mid_bot, "FOLD"))
    elements.append(_line(x2, mid_top, x3, mid_top, "FOLD"))

    # Labels
    body_cy = (y1 + y2) / 2
    elements.append(_label((x0 + x1) / 2, body_cy, "JNT", 0.15))
    elements.append(_label((x1 + x2) / 2, body_cy, "W", 0.18))
    elements.append(_label((x2 + x3) / 2, body_cy, "L", 0.18))
    elements.append(_label((x3 + x4) / 2, body_cy, "W", 0.18))
    elements.append(_label((x4 + x5) / 2, body_cy, "L", 0.18))

    return {
        "elements": elements,
        "blank_length": round(x5, 3),
        "blank_width": round(y3, 3),
        "style": "FOL",
        "fefco": "0203",
    }


def render_hsc(L, W, D, caliper_in=0.146):
    """
    HSC (Half Slotted Container) — FEFCO 0202
    Like RSC but only bottom flaps (open top).
    """
    cal = caliper_in
    elements = []

    x0, x1, x2, x3, x4, x5 = 0, JOINT, JOINT+W, JOINT+W+L, JOINT+2*W+L, JOINT+2*W+2*L
    flap_h = D / 2 + cal
    y0 = 0
    y1 = flap_h
    y2 = flap_h + D  # top edge

    # Outer boundary
    elements.append(_rect(x0, y0, x5, y2, "CUT"))

    # Panel scores
    for x in [x1, x2, x3, x4]:
        elements.append(_line(x, y1, x, y2, "SCORE"))

    # Bottom flap junction
    elements.append(_line(x0, y1, x5, y1, "SCORE"))

    # Bottom slot cuts
    for x in [x2, x3, x4]:
        elements.append(_line(x, y0, x, y1, "CUT"))

    # Open top indicator
    elements.append(_line(x0, y2, x5, y2, "FOLD"))

    body_cy = (y1 + y2) / 2
    elements.append(_label((x1 + x2) / 2, body_cy, "W", 0.18))
    elements.append(_label((x2 + x3) / 2, body_cy, "L", 0.18))
    elements.append(_label((x3 + x4) / 2, body_cy, "W", 0.18))
    elements.append(_label((x4 + x5) / 2, body_cy, "L", 0.18))
    elements.append(_label(x5 / 2, y2 + 0.3, "OPEN", 0.12))

    return {
        "elements": elements,
        "blank_length": round(x5, 3),
        "blank_width": round(y2, 3),
        "style": "HSC",
        "fefco": "0202",
    }


def render_tray(L, W, D, caliper_in=0.146):
    """
    TRAY — Cross-shaped flat pattern with corner ears.
    """
    cal = caliper_in
    elements = []

    total_l = L + 2 * D + 2 * JOINT
    total_w = W + 2 * D + 2 * cal

    # Center panel boundaries
    cx0 = D + JOINT
    cx1 = cx0 + L
    cy0 = D + cal
    cy1 = cy0 + W

    # Center panel scores
    elements.append(_rect(cx0, cy0, L, W, "SCORE"))

    # Side walls
    # Left
    elements.append(_rect(0, cy0, cx0, cy1 - cy0, "CUT"))
    elements.append(_line(cx0, cy0, cx0, cy1, "SCORE"))
    # Right
    elements.append(_rect(cx1, cy0, total_l - cx1, cy1 - cy0, "CUT"))
    elements.append(_line(cx1, cy0, cx1, cy1, "SCORE"))
    # Bottom
    elements.append(_rect(cx0, 0, L, cy0, "CUT"))
    elements.append(_line(cx0, cy0, cx1, cy0, "SCORE"))
    # Top
    elements.append(_rect(cx0, cy1, L, total_w - cy1, "CUT"))
    elements.append(_line(cx0, cy1, cx1, cy1, "SCORE"))

    # Corner ears with diagonal scores
    corners = [
        (0, 0, cx0, cy0),
        (cx1, 0, total_l, cy0),
        (0, cy1, cx0, total_w),
        (cx1, cy1, total_l, total_w),
    ]
    for (ex0, ey0, ex1, ey1) in corners:
        w = ex1 - ex0
        h = ey1 - ey0
        elements.append(_rect(ex0, ey0, w, h, "CUT"))
        elements.append(_line(ex0, ey0, ex1, ey1, "SCORE"))

    # Labels
    elements.append(_label((cx0 + cx1) / 2, (cy0 + cy1) / 2, "BASE", 0.2))

    return {
        "elements": elements,
        "blank_length": round(total_l, 3),
        "blank_width": round(total_w, 3),
        "style": "TRAY",
        "fefco": "0410",
    }


def render_bliss(L, W, D, caliper_in=0.146):
    """
    BLISS — Wrap-around, no flaps. Panels: [D] [L] [D] [L] [Joint]
    """
    cal = caliper_in
    elements = []

    x0 = 0
    x1 = D
    x2 = D + L
    x3 = 2 * D + L
    x4 = 2 * D + 2 * L
    x5 = 2 * D + 2 * L + JOINT
    blank_w = W + D + 2 * cal
    y1 = D + cal

    # Outer boundary
    elements.append(_rect(x0, 0, x5, blank_w, "CUT"))

    # Panel scores
    for x in [x1, x2, x3, x4]:
        elements.append(_line(x, 0, x, blank_w, "SCORE"))

    # Body/end fold
    elements.append(_line(x0, y1, x5, y1, "SCORE"))

    # Labels
    body_cy = (y1 + blank_w) / 2
    elements.append(_label((x0 + x1) / 2, body_cy, "END", 0.15))
    elements.append(_label((x1 + x2) / 2, body_cy, "BODY", 0.15))
    elements.append(_label((x2 + x3) / 2, body_cy, "END", 0.15))
    elements.append(_label((x3 + x4) / 2, body_cy, "BODY", 0.15))
    elements.append(_label((x4 + x5) / 2, body_cy, "J", 0.12))

    return {
        "elements": elements,
        "blank_length": round(x5, 3),
        "blank_width": round(blank_w, 3),
        "style": "BLISS",
        "fefco": "0301",
    }


def render_diecut(L, W, D, caliper_in=0.146):
    """
    DIE-CUT — Generic die-cut box with fold scores.
    """
    elements = []
    bl = L + 2 * D + JOINT
    bw = W + 2 * D

    # Outer boundary
    elements.append(_rect(0, 0, bl, bw, "CUT"))

    # Fold scores
    elements.append(_line(D, 0, D, bw, "SCORE"))
    elements.append(_line(D + L, 0, D + L, bw, "SCORE"))
    elements.append(_line(0, D, bl, D, "SCORE"))
    elements.append(_line(0, D + W, bl, D + W, "SCORE"))

    # Center label
    elements.append(_label(bl / 2, bw / 2, "DIE CUT", 0.2))

    return {
        "elements": elements,
        "blank_length": round(bl, 3),
        "blank_width": round(bw, 3),
        "style": "DIE-CUT",
        "fefco": "0427",
    }


def render_sff(L, W, D, caliper_in=0.146):
    """
    SFF (Snap/Lock Bottom) — FEFCO 0210
    RSC body with lock tabs on bottom flaps.
    """
    cal = caliper_in
    elements = []

    x0, x1, x2, x3, x4, x5 = 0, JOINT, JOINT+W, JOINT+W+L, JOINT+2*W+L, JOINT+2*W+2*L
    flap_h = D / 2 + 2 * cal
    y0, y1, y2, y3 = 0, flap_h, flap_h + D, 2 * flap_h + D

    # Outer boundary
    elements.append(_rect(x0, y0, x5, y3, "CUT"))

    # Panel scores
    for x in [x1, x2, x3, x4]:
        elements.append(_line(x, y1, x, y2, "SCORE"))

    # Flap junctions
    elements.append(_line(x0, y1, x5, y1, "SCORE"))
    elements.append(_line(x0, y2, x5, y2, "SCORE"))

    # Top flap slots
    for x in [x2, x3, x4]:
        elements.append(_line(x, y2, x, y3, "CUT"))

    # Bottom flap slots
    for x in [x2, x3, x4]:
        elements.append(_line(x, y0, x, y1, "CUT"))

    # Lock tab indicators on L-panel bottom flaps
    tab_w = 0.75
    tab_h = 0.5
    for fx0, fx1 in [(x2, x3), (x4, x5)]:
        mid = (fx0 + fx1) / 2
        elements.append(_rect(mid - tab_w, y0, 2 * tab_w, tab_h, "CUT"))
        elements.append(_line(mid - tab_w, y0 + tab_h, mid + tab_w, y0 + tab_h, "SCORE"))

    # Lock slots on W-panel bottom flaps
    for fx0, fx1 in [(x1, x2), (x3, x4)]:
        mid = (fx0 + fx1) / 2
        elements.append(_rect(mid - tab_w * 0.8, y1 - tab_h, 2 * tab_w * 0.8, tab_h, "CUT"))

    # Labels
    body_cy = (y1 + y2) / 2
    elements.append(_label((x0 + x1) / 2, body_cy, "JNT", 0.12))
    elements.append(_label((x1 + x2) / 2, body_cy, "W", 0.18))
    elements.append(_label((x2 + x3) / 2, body_cy, "L", 0.18))
    elements.append(_label((x3 + x4) / 2, body_cy, "W", 0.18))
    elements.append(_label((x4 + x5) / 2, body_cy, "L", 0.18))

    return {
        "elements": elements,
        "blank_length": round(x5, 3),
        "blank_width": round(y3, 3),
        "style": "SFF",
        "fefco": "0210",
    }


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE OVERLAYS — applied on top of any dieline
# ══════════════════════════════════════════════════════════════════════════════

def add_hand_holes(elements, blank_length, blank_width, hole_w=3.0, hole_h=1.5,
                   corner_r=0.5, positions=None):
    """
    Add oblong hand holes to a dieline.

    Default positions: centered on each L-panel body zone (for RSC-family).
    For other styles, provide explicit positions as list of (cx, cy) tuples.
    """
    if positions is None:
        # Default: center of body zone, roughly where L panels are
        body_cy = blank_width / 2
        # Approximate L-panel centers (assume RSC layout)
        x2 = JOINT + blank_length * 0.2  # rough center of second panel
        x4 = JOINT + blank_length * 0.7  # rough center of fourth panel
        positions = [(x2, body_cy), (x4, body_cy)]

    for cx, cy in positions:
        # Draw oblong cutout as rounded rectangle (approximated with ellipse)
        elements.append(_ellipse(cx, cy, hole_w / 2, hole_h / 2, "CUT"))

    return elements


def add_glue_tab(elements, blank_length, blank_width, tab_width=1.0,
                 edge="left", angle=15):
    """
    Add angled manufacturer's joint glue tab.

    Draws a trapezoidal tab on the specified edge.
    """
    inset = tab_width * math.tan(math.radians(angle))

    if edge == "left":
        pts = [
            (0, 0),
            (tab_width, inset),
            (tab_width, blank_width - inset),
            (0, blank_width),
        ]
    elif edge == "right":
        x = blank_length
        pts = [
            (x, 0),
            (x - tab_width, inset),
            (x - tab_width, blank_width - inset),
            (x, blank_width),
        ]
    else:
        return elements

    elements.append(_polyline(pts, "GLUE", closed=True))
    return elements


def add_vent_holes(elements, positions, diameter=0.375):
    """
    Add circular vent/breathing holes.
    positions: list of (cx, cy) center coordinates.
    """
    r = diameter / 2
    for cx, cy in positions:
        elements.append(_circle(cx, cy, r, "CUT"))
    return elements


def add_thumb_notch(elements, cx, cy, width=1.5, depth=0.75):
    """
    Add semicircular thumb notch cutout.
    """
    elements.append(_ellipse(cx, cy, width / 2, depth, "CUT"))
    return elements


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

RENDERERS = {
    "RSC":    render_rsc,
    "FOL":    render_fol,
    "HSC":    render_hsc,
    "TRAY":   render_tray,
    "BLISS":  render_bliss,
    "DIECUT": render_diecut,
    "DIE":    render_diecut,
    "DC":     render_diecut,
    "DIECUT": render_diecut,
    "SFF":    render_sff,
    "SNAP":   render_sff,
    "LOCK":   render_sff,
    # Aliases
    "BLI":    render_bliss,
    "ROLLA":  render_bliss,
    "FTC":    render_tray,
    "HTC":    render_tray,
    "DST":    render_tray,
    "OPF":    render_rsc,
    "CSSC":   render_rsc,
    "TELESCOPE": render_rsc,
    "ROLL":   render_rsc,
    "5PF":    render_rsc,
    "SEF":    render_rsc,
    "SEAL":   render_rsc,
    "WRT":    render_bliss,
    "WRAP":   render_bliss,
    "WPF":    render_bliss,
    "FPF":    render_bliss,
    "RPT":    render_bliss,
    "MAILER": render_diecut,
    "PIZZA":  render_diecut,
}


def get_dieline_data(box_style, L, W, D, caliper_in=0.146,
                     hand_holes=False, glue_tab=False, vent_holes=False,
                     show_dimensions=True):
    """
    Main entry point: render dieline SVG data for a box style.

    Returns dict with:
      - elements: list of SVG element dicts
      - blank_length, blank_width: calculated blank dimensions
      - style, fefco: style identifiers
      - line_styles: color/dash definitions for front-end rendering
    """
    style = (box_style or "RSC").upper().replace("-", "").replace(" ", "")
    renderer = RENDERERS.get(style, render_rsc)

    result = renderer(float(L), float(W), float(D), float(caliper_in))

    # Apply optional overlays
    if hand_holes:
        add_hand_holes(result["elements"], result["blank_length"], result["blank_width"])

    if glue_tab:
        add_glue_tab(result["elements"], result["blank_length"], result["blank_width"])

    if vent_holes:
        # Default vent positions: 4 corners of body zone
        bl, bw = result["blank_length"], result["blank_width"]
        vent_positions = [
            (bl * 0.15, bw * 0.5),
            (bl * 0.85, bw * 0.5),
        ]
        add_vent_holes(result["elements"], vent_positions)

    # Add dimension measurements
    if show_dimensions:
        generate_measurements(result)

    # Include line style definitions for front-end
    result["line_styles"] = LINE_STYLES

    return result
