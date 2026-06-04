# core/drawing_generator.py
"""
Universal Engineering Drawing Generator  — A3 landscape, 3rd-angle projection
==============================================================================

Layout contract (3rd-angle):

        ┌──────────┐  ┌──────────┐
        │  TOP     │  │          │
        │  (plan)  │  │  (spare) │
        ├──────────┤  ├──────────┤
        │  FRONT   │  │  RIGHT   │
        │  (elev.) │  │  (side)  │
        └──────────┘  └──────────┘

  • Top view is ABOVE front, aligned on X.
  • Right view is RIGHT of front, aligned on Y.
  • All annotation space is pre-reserved so nothing ever escapes the border.
  • A uniform scale-to-fit is applied when the layout is too large for the sheet.
"""

import datetime
import math


# ── Sheet geometry ────────────────────────────────────────────────────────────
SHEET_W  = 420.0
SHEET_H  = 297.0
MARGIN   =  10.0

INNER_X0 = MARGIN
INNER_Y0 = MARGIN
INNER_X1 = SHEET_W - MARGIN
INNER_Y1 = SHEET_H - MARGIN

# Title block — bottom-right corner of inner frame
TB_W  = 150.0
TB_H  =  45.0
TB_X0 = INNER_X1 - TB_W
TB_Y0 = INNER_Y0
TB_X1 = INNER_X1
TB_Y1 = INNER_Y0 + TB_H

# Notes — top-left corner of inner frame
NOTES_H  =  45.0
NOTES_Y0 = INNER_Y1 - NOTES_H
NOTES_Y1 = INNER_Y1

# Canvas for views: full inner frame minus title block row at bottom
# and notes row at top.  We accept both corners are occupied by fixed elements
# so views must avoid them.
CANVAS_X0 = INNER_X0
CANVAS_X1 = INNER_X1
CANVAS_Y0 = INNER_Y0 + TB_H + 5     # above title block
CANVAS_Y1 = INNER_Y1 - NOTES_H - 5  # below notes

# ── Annotation clearance per view (MODEL units @ scale 1:1) ──────────────────
ANN_LEFT   = 30.0   # left  → vertical overall + staircase dims
ANN_BOTTOM = 28.0   # below → horizontal overall + staircase dims
ANN_RIGHT  =  8.0   # right → small overrun for leaders
ANN_TOP    =  6.0   # above → breathing room

VIEW_GAP   = 20.0   # gap between adjacent annotated boxes

MIN_FEATURE_RATIO = 0.12   # min fraction of view diagonal to earn its own dim

# Fixed text heights in SHEET mm (constant regardless of scale)
TXT_H_DIM   = 1.8
TXT_H_SMALL = 1.6


# ─────────────────────────────────────────────────────────────────────────────

class DrawingGenerator:

    def __init__(self, output_path=None):
        import ezdxf
        self.output_path  = output_path
        self.doc          = ezdxf.new('R2010')
        self.msp          = self.doc.modelspace()
        self.scale_factor = 1.0
        self._setup_layers()

    # ── Layers ───────────────────────────────────────────────────────────────

    def _setup_layers(self):
        # Ensure the document knows how to draw a dashed line pattern
        if 'DASHED' not in self.doc.linetypes:
            self.doc.linetypes.new('DASHED', dxfattribs={
                'description': 'Hidden Line __ __ __ __ __',
                'pattern': [4.0, -2.0]  # 4mm dash, 2mm space
            })
        
        # Set global linetype scale so dashes scale beautifully on an A3 sheet
        self.doc.header['$LTSCALE'] = 0.5

        def ensure(name, color, linetype='Continuous'):
            if name not in self.doc.layers:
                self.doc.layers.new(name=name, dxfattribs={'color': color, 'linetype': linetype})
        
        ensure('BORDER',        7)
        ensure('GEOMETRY',      7)
        ensure('HIDDEN_LINES',  8, linetype='DASHED')  # Color 8 = Dark Gray / Slender
        ensure('CENTER_LINES',  1)
        ensure('DIMENSIONS',    2)
        ensure('NOTES',         3)
    # ── Sheet frame ──────────────────────────────────────────────────────────

    def create_sheet_layout(self):
        def poly(pts, layer='BORDER'):
            self.msp.add_lwpolyline(
                pts, dxfattribs={'layer': layer, 'closed': True})

        poly([(0,0),(SHEET_W,0),(SHEET_W,SHEET_H),(0,SHEET_H)])
        poly([(INNER_X0,INNER_Y0),(INNER_X1,INNER_Y0),
              (INNER_X1,INNER_Y1),(INNER_X0,INNER_Y1)])
        poly([(TB_X0,TB_Y0),(TB_X1,TB_Y0),(TB_X1,TB_Y1),(TB_X0,TB_Y1)])
        self.msp.add_line((TB_X0, TB_Y0+13), (TB_X1, TB_Y0+13),
                          dxfattribs={'layer': 'BORDER'})
        self.msp.add_line((TB_X0, TB_Y0+26), (TB_X1, TB_Y0+26),
                          dxfattribs={'layer': 'BORDER'})

    # ── Title block ──────────────────────────────────────────────────────────

    def populate_title_block(self, filename='Part.STEP',
                            custom_title=None, unit='MM'):
        def t(s, x, y, h, color=7):
            txt = self.msp.add_text(
                s, dxfattribs={'height': h, 'layer': 'DIMENSIONS',
                               'color': color})
            txt.set_placement((x, y))

        tx    = TB_X0 + 4
        title = (custom_title or filename.rsplit('.', 1)[0]).upper()
        t(f'PART: {title}', tx, TB_Y0+29, 3.0, color=3)
        t(f'UNITS: {unit}', tx, TB_Y0+15, 2.0)
        t(f'SCALE  {self.scale_factor:.2f} : 1' if self.scale_factor != 1.0 else 'SCALE  1 : 1', tx, TB_Y0+4, 2.0)
        t(f"DATE: {datetime.date.today().strftime('%Y-%m-%d')}",
          tx+80, TB_Y0+4, 2.0)

    # ── Notes ─────────────────────────────────────────────────────────────────

    def write_manufacturing_notes(self, notes_list):
        x = INNER_X0 + 3
        y = NOTES_Y1 - 6

        def t(s, cy, h, color=7):
            txt = self.msp.add_text(
                s, dxfattribs={'height': h, 'layer': 'NOTES', 'color': color})
            txt.set_placement((x, cy))
            return cy

        y = t('MANUFACTURING NOTES:', y, 2.5, color=3) - 5
        for i, note in enumerate(notes_list, 1):
            line = f'{i}. {note.upper()}'
            if len(line) > 70:
                t(line[:70], y, 1.8);  y -= 4.0
                t('   ' + line[70:], y, 1.8)
            else:
                t(line, y, 1.8)
            y -= 4.5

    # ── Public entry point ───────────────────────────────────────────────────

    def populate_views(self, views):
        """
        Compute geometry bounds → annotated box sizes → uniform scale-to-fit →
        centred placement → draw geometry → draw annotations.

        3rd-angle layout:
            top view   ABOVE front (same left edge, X-aligned)
            right view RIGHT of front (same bottom edge, Y-aligned)
        """

        # 1. Raw geometry bounds
        raw = {}
        for vname, ents in views.items():
            xs, ys = [], []
            for e in ents:
                if e.get('hidden'):
                    continue
                if e['type'] == 'line':
                    for p in e['pts']:
                        xs.append(p[0]); ys.append(p[1])
                elif e['type'] == 'circle':
                    cx, cy = e['center']; r = e['radius']
                    xs += [cx-r, cx+r]; ys += [cy-r, cy+r]
            if xs and ys:
                raw[vname] = dict(
                    min_x=min(xs), max_x=max(xs),
                    min_y=min(ys), max_y=max(ys),
                    w=max(xs)-min(xs), h=max(ys)-min(ys))

        if 'front' not in raw:
            return

        # 2. Annotated box sizes (model units)
        def abox(b):
            return (b['w'] + ANN_LEFT + ANN_RIGHT,
                    b['h'] + ANN_BOTTOM + ANN_TOP)

        fb   = raw['front']
        tb   = raw.get('top')
        rb   = raw.get('right')
        fa_w, fa_h = abox(fb)
        ta_w, ta_h = abox(tb) if tb else (0.0, 0.0)
        ra_w, ra_h = abox(rb) if rb else (0.0, 0.0)

        # 3. Layout footprint in model units
        col1_w  = max(fa_w, ta_w) if tb else fa_w
        col2_w  = ra_w if rb else 0.0
        total_w = col1_w + (VIEW_GAP + col2_w if rb else 0.0)

        # Top row holds the top view; bottom row holds front view
        top_row_h   = ta_h if tb else 0.0
        total_h     = top_row_h + (VIEW_GAP if tb else 0.0) + fa_h

        # 4. Scale-to-fit
        avail_w = CANVAS_X1 - CANVAS_X0
        avail_h = CANVAS_Y1 - CANVAS_Y0

        if avail_w <= 0 or avail_h <= 0 or total_w <= 0 or total_h <= 0:
            return

        scale = min(1.0, avail_w / total_w, avail_h / total_h)
        self.scale_factor = scale

        # 5. Centred layout origin (bottom-left of layout block in sheet space)
        scaled_w = total_w * scale
        scaled_h = total_h * scale
        ox = CANVAS_X0 + (avail_w - scaled_w) / 2.0
        oy = CANVAS_Y0 + (avail_h - scaled_h) / 2.0

        # ==========================================
        # 6. Corrected 3rd Angle Grid Matrix Mapping
        # ==========================================
        # Front view area occupies the absolute bottom anchor row
        front_ann_ox = ox
        front_ann_oy = oy

        # Top view sits strictly in the row ABOVE the Front view
        top_ann_ox   = ox
        top_ann_oy   = oy + fa_h * scale + VIEW_GAP * scale

        # Right view sits to the right of the front view, sharing its exact Y baseline
        right_ann_ox = ox + col1_w * scale + VIEW_GAP * scale
        right_ann_oy = front_ann_oy

        ann_origins = {'front': (front_ann_ox, front_ann_oy)}
        if tb: ann_origins['top']   = (top_ann_ox, top_ann_oy)
        if rb: ann_origins['right'] = (right_ann_ox, right_ann_oy)

        # 7. Draw geometry for each view
        transformed = {}
        
        # Lock vertical base horizon tracking to the Front view's internal datum placement
        front_geo_oy = ann_origins['front'][1] + ANN_BOTTOM * scale
        
        for vname, ents in views.items():
            if vname not in ann_origins or vname not in raw:
                continue

            b  = raw[vname]
            ao = ann_origins[vname]

            # True cross-view linear alignment pass
            if vname in ["front", "right"]:
                geo_ox = ao[0] + ANN_LEFT * scale
                geo_oy = front_geo_oy  # Force side profiles to match the front view horizon
            else:
                # Top View standard tracking bounds
                geo_ox = ao[0] + ANN_LEFT   * scale
                geo_oy = ao[1] + ANN_BOTTOM * scale

            def to_sheet(pt, _b=b, _gox=geo_ox, _goy=geo_oy, _s=scale):
                return ((pt[0] - _b['min_x']) * _s + _gox,
                        (_b['min_y'] - pt[1]) * _s + _goy)

            placed = []
            for e in ents:
                # Determine layer attributes based on visibility flag from cad_processor
                is_hidden = e.get('hidden', False)
                lyr = 'HIDDEN_LINES' if is_hidden else 'GEOMETRY'

                if e['type'] == 'line':
                    p1 = to_sheet(e['pts'][0])
                    p2 = to_sheet(e['pts'][1])
                    self.msp.add_line(p1, p2, dxfattribs={'layer': lyr})
                    if not is_hidden:
                        placed.append({'type': 'line', 'pts': (p1, p2)})

                elif e['type'] == 'circle':
                    tc = to_sheet(e['center'])
                    r  = e['radius'] * scale
                    self.msp.add_circle(tc, r, dxfattribs={'layer': lyr})
                    
                    if not is_hidden:
                        cx, cy = tc
                        ext = r + max(1.5, 2.0 * scale)
                        self.msp.add_line(
                            (cx-ext, cy), (cx+ext, cy),
                            dxfattribs={'layer': 'CENTER_LINES', 'color': 1})
                        self.msp.add_line(
                            (cx, cy-ext), (cx, cy+ext),
                            dxfattribs={'layer': 'CENTER_LINES', 'color': 1})
                        placed.append({'type': 'circle', 'center': tc, 'radius': r})

            transformed[vname] = placed

        # 8. Annotate each view
        for vname, ents in transformed.items():
            self._annotate_view(ents, scale)

    # ── Annotation engine ────────────────────────────────────────────────────

    def _annotate_view(self, entities, scale):
        """
        Draws dimensions for one already-placed view.
        All coordinates are in SHEET mm.
        Dimension offsets are calculated from the pre-reserved annotation bands
        (ANN_* constants × scale), so they are guaranteed to stay inside them.
        """
        lines   = [e for e in entities if e['type'] == 'line']
        circles = [e for e in entities if e['type'] == 'circle']

        xs, ys = [], []
        for l in lines:
            for p in l['pts']:
                xs.append(p[0]); ys.append(p[1])
        for c in circles:
            cx, cy = c['center']; r = c['radius']
            xs += [cx-r, cx+r]; ys += [cy-r, cy+r]

        if not xs:
            return

        mn_x, mx_x = min(xs), max(xs)
        mn_y, mx_y = min(ys), max(ys)
        vw = mx_x - mn_x
        vh = mx_y - mn_y
        if vw < 0.5 or vh < 0.5:
            return

        # Available annotation bands in sheet mm
        h_band = ANN_BOTTOM * scale   # space below geometry
        v_band = ANN_LEFT   * scale   # space to left of geometry

        # How many staircase tiers fit without text collision?
        min_step = TXT_H_DIM + 2.5   # minimum mm between dim lines
        n_h = max(1, int(h_band / min_step) - 1)
        n_v = max(1, int(v_band / min_step) - 1)

        h_step = max(min_step, h_band / (n_h + 1))
        v_step = max(min_step, v_band / (n_v + 1))

        # Overall dimensions — placed at first tier
        h_off0 = -h_step
        v_off0 = -v_step
        self._dim_h((mn_x, mn_y), (mx_x, mn_y), h_off0, f'{vw/scale:.1f}')
        self._dim_v((mn_x, mn_y), (mn_x, mx_y), v_off0, f'{vh/scale:.1f}')

        # Collect internal feature planes
        diag    = math.sqrt(vw**2 + vh**2)
        min_seg = diag * MIN_FEATURE_RATIO

        ix, iy = [], []
        for c in circles:
            ix.append(c['center'][0])
            iy.append(c['center'][1])
        for l in lines:
            p1, p2 = l['pts']
            dx = abs(p1[0]-p2[0]); dy = abs(p1[1]-p2[1])
            seg = math.sqrt(dx**2 + dy**2)
            if seg < min_seg:
                continue
            if dx < 0.1:   ix.append(p1[0])
            if dy < 0.1:   iy.append(p1[1])

        def cluster(vals, lo, hi):
            thr = max(2.5, min(vw, vh) * 0.04)
            unique = sorted(set(round(v, 1) for v in vals))
            out = []
            for v in unique:
                if abs(v-lo) < thr or abs(v-hi) < thr:
                    continue
                if not out or abs(v - out[-1]) > thr:
                    out.append(v)
            return out

        cxp = cluster(ix, mn_x, mx_x)
        cyp = cluster(iy, mn_y, mx_y)

        # Staircase — limited to what fits in the band
        h_off = h_off0 - h_step
        for x in cxp[:max(0, n_h-1)]:
            self._dim_h((mn_x, mn_y), (x, mn_y), h_off,
                        f'{abs(x-mn_x)/scale:.1f}')
            h_off -= h_step

        v_off = v_off0 - v_step
        for y in cyp[:max(0, n_v-1)]:
            self._dim_v((mn_x, mn_y), (mn_x, y), v_off,
                        f'{abs(y-mn_y)/scale:.1f}')
            v_off -= v_step

        # Hole leaders — 45° upper-right, shelf then text
        for c in circles:
            cx, cy = c['center']; r = c['radius']
            a       = math.radians(45)
            tip_x   = cx + r * math.cos(a)
            tip_y   = cy + r * math.sin(a)
            reach   = r + max(3.0, min(ANN_RIGHT * scale * 0.5, 8.0))
            elb_x   = cx + reach * math.cos(a)
            elb_y   = cy + reach * math.sin(a)
            shelf   = max(2.5, 4.5 * scale)
            self.msp.add_line((tip_x, tip_y), (elb_x, elb_y),
                              dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
            self.msp.add_line((elb_x, elb_y), (elb_x+shelf, elb_y),
                              dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
            dia = (r / scale) * 2
            txt = self.msp.add_text(
                f'%%c{dia:.1f}',
                dxfattribs={'height': TXT_H_SMALL,
                            'layer': 'DIMENSIONS', 'color': 3})
            txt.set_placement((elb_x+shelf+0.4, elb_y+0.3))

    # ── Primitive dimension drawers ───────────────────────────────────────────

    def _dim_h(self, p1, p2, y_off, label):
        """Horizontal dimension.  y_off < 0 places it below geometry."""
        x1, y1 = p1;  x2, y2 = p2
        if abs(x2-x1) < 0.1:
            return
        dim_y = y1 + y_off
        gap   = 0.6
        sign  = 1 if y_off > 0 else -1
        self.msp.add_line((x1, y1), (x1, dim_y - sign*gap),
                          dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
        self.msp.add_line((x2, y2), (x2, dim_y - sign*gap),
                          dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
        self.msp.add_line((x1, dim_y), (x2, dim_y),
                          dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
        mid_x = (x1+x2)/2.0
        cw    = TXT_H_DIM * 0.55
        t_x   = mid_x - len(label)*cw/2.0
        t_y   = (dim_y + 0.6) if y_off > 0 else (dim_y - TXT_H_DIM - 0.5)
        txt   = self.msp.add_text(
            label, dxfattribs={'height': TXT_H_DIM,
                               'layer': 'DIMENSIONS', 'color': 7})
        txt.set_placement((t_x, t_y))

    def _dim_v(self, p1, p2, x_off, label):
        """Vertical dimension.  x_off < 0 places it left of geometry."""
        x1, y1 = p1;  x2, y2 = p2
        if abs(y2-y1) < 0.1:
            return
        dim_x = x1 + x_off
        gap   = 0.6
        sign  = 1 if x_off > 0 else -1
        self.msp.add_line((x1, y1), (dim_x - sign*gap, y1),
                          dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
        self.msp.add_line((x2, y2), (dim_x - sign*gap, y2),
                          dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
        self.msp.add_line((dim_x, y1), (dim_x, y2),
                          dxfattribs={'layer': 'DIMENSIONS', 'color': 2})
        mid_y = (y1+y2)/2.0
        cw    = TXT_H_DIM * 0.55
        t_x   = (dim_x + 0.7) if x_off > 0 else (dim_x - len(label)*cw - 0.7)
        txt   = self.msp.add_text(
            label, dxfattribs={'height': TXT_H_DIM,
                               'layer': 'DIMENSIONS', 'color': 7})
        txt.set_placement((t_x, mid_y - TXT_H_DIM/2.0))

    # ── Save ─────────────────────────────────────────────────────────────────

    def save(self, filename):
        self.doc.saveas(self.output_path or filename)