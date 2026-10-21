"""Parametric CAD model of the test rig (CadQuery 2.x).

    pip install cadquery
    python3 cad/rig_cad.py          -> cad/rig.step, cad/spin_module.step, cad/rig_iso.svg, cad/rig_ga.svg,
                                       cad/spin_cutaway.svg

All sizes are in millimetres. The origin is on the floor at the front left corner of the frame;
x runs to the right, y to the back and z up. The frame has three bays: gas (left), water
(middle) and process (right). The front panels, cable ducts and small fittings are left out.
The parts are named and numbered as in the parts list on the page.
"""
import re
from pathlib import Path

import cadquery as cq
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- main dimensions
W, D, H = 1600.0, 800.0, 2000.0            # frame outside
PROF = 45.0                                # aluminium profile 45 x 45
BAYS = (0.0, 500.0, 1000.0, W)             # bay borders along x
DECK = 850.0                               # top of the work deck
UPPER = 1650.0                             # top of the upper deck (gas bay)
WAFER_Z = 1150.0                           # wafer plane
WAFER_D = 300.0
CUP_ID = 380.0                             # inside diameter of the catch cup
CHAMBER = dict(x0=1040.0, x1=1560.0, y0=120.0, y1=680.0, z0=950.0, z1=1350.0, wall=10.0)
AXIS = ((CHAMBER['x0'] + CHAMBER['x1']) / 2, (CHAMBER['y0'] + CHAMBER['y1']) / 2)   # spin axis (x, y)
NOZZLE_GAP = 15.0                          # nozzle tip above the wafer (10 to 20)


def box(x0, y0, z0, x1, y1, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_z(x, y, z0, z1, d):
    return cq.Workplane('XY').circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def cyl_x(x0, x1, y, z, d):
    return cq.Workplane('YZ').circle(d / 2).extrude(x1 - x0).translate((x0, y, z))


def cyl_y(x, y0, y1, z, d):
    return cq.Workplane('XZ').circle(d / 2).extrude(-(y1 - y0)).translate((x, y0, z))


def tube_z(x, y, z0, z1, d, wall):
    return (cq.Workplane('XY').circle(d / 2).circle(d / 2 - wall).extrude(z1 - z0).translate((x, y, z0)))


# ---------------------------------------------------------------- frame
def frame():
    parts = []
    xs = [BAYS[0], BAYS[1] - PROF / 2, BAYS[2] - PROF / 2, W - PROF]
    ys = [0.0, D - PROF]
    for x in xs:
        for y in ys:
            parts.append(box(x, y, 0, x + PROF, y + PROF, H))
    for z in (100.0 - PROF, DECK - PROF, UPPER - PROF, H - PROF):
        for y in ys:
            parts.append(box(PROF, y, z, W - PROF, y + PROF, z + PROF))
        for x in xs:
            parts.append(box(x, PROF, z, x + PROF, D - PROF, z + PROF))
    f = parts[0]
    for p in parts[1:]:
        f = f.union(p)
    return f


def decks():
    return (box(BAYS[1] + PROF / 2, PROF, DECK - 12, W - PROF, D - PROF, DECK)          # work deck, water and process bays
            .union(box(PROF, PROF, UPPER - 12, BAYS[1] - PROF / 2, D - PROF, UPPER)))  # upper deck, gas bay


# ---------------------------------------------------------------- gas bay
def control_cabinet():
    return box(70, 330, 150, 450, 740, 760)


def generator():
    g = box(70, 330, UPPER, 450, 720, UPPER + 260)
    return g.union(cyl_y(150, 300, 330, UPPER + 130, 20)).union(cyl_y(370, 300, 330, UPPER + 130, 20))   # cooling water


def gas_analyser():
    return box(110, 60, UPPER, 400, 300, UPPER + 150)


def mfcs():
    m = box(90, 60, 1300, 190, 100, 1420)               # FIC-101, oxygen
    m = m.union(box(230, 60, 1300, 330, 100, 1420))     # FIC-104, chamber gas
    return m.union(box(90, 60, 1100, 190, 100, 1220))   # FIC-201, CO2


# ---------------------------------------------------------------- water bay
def contactor():
    c = cyl_z(620, 520, DECK + 60, DECK + 660, 110)
    c = c.union(cyl_z(620, 520, DECK + 660, DECK + 690, 60)).union(cyl_z(620, 520, DECK + 30, DECK + 60, 60))
    return c.union(box(590, 560, DECK, 650, 590, DECK + 60))       # bracket


def heat_exchanger():
    return box(720, 520, DECK + 40, 920, 640, DECK + 290)


def liquid_flow_controller():
    return box(560, 160, DECK, 700, 240, DECK + 100)


def heater():
    return cyl_x(720, 980, 300, DECK + 420, 70)


def bubble_trap():
    return cyl_z(900, 180, DECK + 200, DECK + 360, 60)


def ozone_monitors():
    return box(560, 80, DECK + 520, 740, 190, DECK + 680).union(box(760, 80, DECK + 520, 940, 190, DECK + 680))


def chiller():
    return box(540, 120, 110, 960, 720, 760)


def drip_tray():
    t = box(BAYS[1] + PROF / 2, PROF, DECK, BAYS[2] - PROF / 2, D - PROF, DECK + 25)
    return t.cut(box(BAYS[1] + PROF / 2 + 8, PROF + 8, DECK + 5, BAYS[2] - PROF / 2 - 8, D - PROF - 8, DECK + 26))


def supply_lines():
    """PFA lines of the water path, as tubes of 9.5 mm outside diameter (3/8 in)."""
    d = 9.5
    p = cyl_x(675, 720, 520, DECK + 600, d)                          # contactor to heat exchanger area (routing)
    p = p.union(cyl_x(700, 720, 200, DECK + 50, d))
    p = p.union(cyl_z(980, 300, DECK + 420, DECK + 470, d)).union(cyl_x(980, 1300, 300, DECK + 470, d))
    return p.union(cyl_z(1300, 300, DECK + 470, CHAMBER['z1'] + 40, d))


# ---------------------------------------------------------------- process bay: the spin module
def chamber_shell(cut_front=False):
    c = CHAMBER
    s = box(c['x0'], c['y0'], c['z0'], c['x1'], c['y1'], c['z1']).cut(
        box(c['x0'] + c['wall'], c['y0'] + c['wall'], c['z0'] + c['wall'], c['x1'] - c['wall'], c['y1'] - c['wall'], c['z1'] + 1))
    if cut_front:
        s = s.cut(box(c['x0'] - 1, c['y0'] - 1, c['z0'] - 1, c['x1'] + 1, AXIS[1], c['z1'] + 1))
    return s


def lid(cut_front=False):
    c = CHAMBER
    l = box(c['x0'], c['y0'], c['z1'], c['x1'], c['y1'], c['z1'] + 30)
    l = l.cut(box(AXIS[0] - 120, AXIS[1] - 120, c['z1'] - 1, AXIS[0] + 120, AXIS[1] + 120, c['z1'] + 31))   # viewport
    l = l.union(box(AXIS[0] - 130, AXIS[1] - 130, c['z1'] + 30, AXIS[0] + 130, AXIS[1] + 130, c['z1'] + 38))  # window frame
    l = l.union(cyl_x(c['x0'] + 40, c['x1'] - 40, c['y1'] - 10, c['z1'] + 30, 24))                          # hinge
    if cut_front:
        l = l.cut(box(c['x0'] - 1, c['y0'] - 1, c['z1'] - 1, c['x1'] + 1, AXIS[1], c['z1'] + 60))
    return l


def cup(cut_front=False):
    """Catch cup: wall at the cup diameter, inward lip above the wafer, floor with drain and exhaust."""
    ri, t = CUP_ID / 2, 8.0
    floor_z, lip_z = 1000.0, WAFER_Z + 40.0
    pts = [(ri, floor_z), (ri, lip_z - 15), (ri - 25, lip_z), (ri - 25, lip_z + t), (ri + t, lip_z - 12),
           (ri + t, floor_z - t), (60.0, floor_z - t), (60.0, floor_z)]
    prof = cq.Workplane('XZ').polyline(pts).close()
    c = prof.revolve(360, (0, 0, 0), (0, 1, 0)).translate((AXIS[0], AXIS[1], 0))
    c = c.union(tube_z(AXIS[0], AXIS[1], floor_z - t, floor_z + 30, 60, 6))            # shaft collar (labyrinth)
    if cut_front:
        c = c.cut(box(AXIS[0] - 400, AXIS[1] - 400, 0, AXIS[0] + 400, AXIS[1], 2000))
    return c


def chuck_and_wafer(cut_front=False):
    ch = cyl_z(AXIS[0], AXIS[1], WAFER_Z - 22, WAFER_Z - 2, 200)                       # vacuum chuck
    ch = ch.union(cyl_z(AXIS[0], AXIS[1], 960, WAFER_Z - 22, 30))                        # shaft
    w = cyl_z(AXIS[0], AXIS[1], WAFER_Z - 2, WAFER_Z, WAFER_D)                          # wafer, thickness exaggerated
    if cut_front:
        cutter = box(AXIS[0] - 400, AXIS[1] - 400, 0, AXIS[0] + 400, AXIS[1], 2000)
        ch, w = ch.cut(cutter), w.cut(cutter)
    return ch, w


def motor():
    m = cyl_z(AXIS[0], AXIS[1], DECK - 260, DECK - 40, 120)                             # servo motor with encoder
    m = m.union(box(AXIS[0] - 80, AXIS[1] - 80, DECK - 40, AXIS[0] + 80, AXIS[1] + 80, DECK - 12))   # flange
    m = m.union(cyl_z(AXIS[0], AXIS[1], DECK - 300, DECK - 260, 40))                    # rotary union, vacuum
    return m.union(cyl_z(AXIS[0], AXIS[1], DECK, CHAMBER['z0'], 70))                     # bearing housing


def nozzle_arm():
    c = CHAMBER
    a = box(AXIS[0] - 10, AXIS[1], WAFER_Z + 60, AXIS[0] + 10, c['y1'] - c['wall'], WAFER_Z + 80)
    a = a.union(cyl_z(AXIS[0], AXIS[1], WAFER_Z + NOZZLE_GAP, WAFER_Z + 60, 8))
    return a.union(box(AXIS[0] - 30, c['y1'] - c['wall'] - 20, WAFER_Z + 40, AXIS[0] + 30, c['y1'] - c['wall'], c['z1'] - 20))


def exhaust_duct():
    c = CHAMBER
    e = cyl_y(1480, c['y1'], 750, 1010, 100)
    e = e.union(cyl_z(1480, 750, 1010, H + 40, 100))
    return e.union(cyl_y(1480, 640, 750, H + 40, 100))


def destruct():
    return box(1150, 430, H, 1560, 760, H + 300)


def drain_tank():
    t = box(1060, 250, 110, 1360, 550, 460)
    return t.union(cyl_z(AXIS[0] - 182, AXIS[1], 460, 1000.0, 24))     # drain line from the cup gutter (r = 182)


def ambient_sensor():
    return box(CHAMBER['x1'] + 5, 300, 1200, CHAMBER['x1'] + 35, 360, 1260)


# ---------------------------------------------------------------- parts list (number, name, builder)
def parts(cut=False):
    ch, w = chuck_and_wafer(cut)
    return [
        (1, 'Frame, aluminium profile 45 x 45', frame()),
        (2, 'Decks, PVDF-covered plates', decks()),
        (3, 'Control cabinet with interlock relay', control_cabinet()),
        (4, 'Ozone generator', generator()),
        (5, 'Ozone analyser, gas (AIT-102)', gas_analyser()),
        (6, 'Mass flow controllers (FIC-101, FIC-104, FIC-201)', mfcs()),
        (7, 'Membrane contactor', contactor()),
        (8, 'PFA heat exchanger (TIC-203)', heat_exchanger()),
        (9, 'Liquid flow controller (FIC-205)', liquid_flow_controller()),
        (10, 'Inline heater (TIC-206)', heater()),
        (11, 'Bubble trap', bubble_trap()),
        (12, 'Dissolved ozone monitors (AIT-204, AIT-207)', ozone_monitors()),
        (13, 'Recirculating chiller', chiller()),
        (14, 'Drip tray with leak sensor', drip_tray()),
        (15, 'PFA supply lines', supply_lines()),
        (16, 'Chamber, PVDF', chamber_shell(cut)),
        (17, 'Lid with viewport and hinge', lid(cut)),
        (18, 'Catch cup with lip, drain and exhaust floor', cup(cut)),
        (19, 'Vacuum chuck and shaft', ch),
        (20, 'Wafer, 300 mm', w),
        (21, 'Spin motor, bearing housing, rotary union (SIC-301)', motor()),
        (22, 'Nozzle arm and centre nozzle', nozzle_arm()),
        (23, 'Exhaust duct with FT-303 and AIT-304', exhaust_duct()),
        (24, 'Ozone destruct, heated catalyst', destruct()),
        (25, 'Drain tank with AIT-302 line', drain_tank()),
        (26, 'Ambient ozone monitor (AIT-401)', ambient_sensor()),
    ]




# a point on each part where its balloon leader ends (x, y, z)
ANCHORS = {
    1: ((W - PROF / 2, 0, 400), None), 2: ((760, 400, DECK), None), 3: ((260, 330, 600), None),
    4: ((260, 330, UPPER + 200), None), 5: ((255, 60, UPPER + 120), None), 6: ((140, 60, 1360), None),
    7: ((620, 465, DECK + 450), None), 8: ((820, 520, DECK + 200), None), 9: ((630, 160, DECK + 80), None),
    10: ((850, 265, DECK + 420), None), 11: ((900, 150, DECK + 330), None), 12: ((650, 80, DECK + 640), None),
    13: ((750, 120, 500), None), 14: ((760, PROF, DECK + 20), None), 15: ((1300, 300, DECK + 470), None),
    16: ((CHAMBER['x1'], AXIS[1] + 100, 1000), None), 17: ((CHAMBER['x1'] - 60, CHAMBER['y1'], CHAMBER['z1'] + 30), None),
    18: ((AXIS[0] - CUP_ID / 2, AXIS[1], 1080), None), 19: ((AXIS[0], AXIS[1], WAFER_Z - 60), None),
    20: ((AXIS[0] + 120, AXIS[1], WAFER_Z), None), 21: ((AXIS[0], AXIS[1], DECK - 150), None),
    22: ((AXIS[0], AXIS[1] + 60, WAFER_Z + 70), None), 23: ((1480, 750, 1700), None), 24: ((1355, 430, H + 150), None),
    25: ((1210, 250, 300), None), 26: ((CHAMBER['x1'] + 35, 330, 1230), None),
}


def _unit(v):
    n = sum(c * c for c in v) ** 0.5
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def view_axes(eye):
    """Viewing direction towards the eye, and screen axes with world z kept up (x for plan views)."""
    n = _unit(eye)
    up = (0.0, 0.0, 1.0) if abs(n[2]) < 0.99 else (0.0, 1.0, 0.0)
    x = _unit(_cross(up, n)) if abs(n[2]) < 0.99 else (1.0, 0.0, 0.0)
    y = _cross(n, x)
    return n, x, y


def project(shapes, eye, deflection=0.5):
    """Hidden-line removal (OpenCascade HLR) of the shapes seen from 'eye'. Returns the visible
    edges as 2D polylines in the screen axes, and a function that projects 3D points the same way."""
    from OCP.BRepLib import BRepLib
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    n, x, y = view_axes(eye)
    comp = cq.Compound.makeCompound([s.val() if hasattr(s, 'val') else s for s in shapes])
    hlr = HLRBRep_Algo()
    hlr.Add(comp.wrapped)
    hlr.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*n), gp_Dir(*x))))
    hlr.Update()
    hlr.Hide()
    out = HLRBRep_HLRToShape(hlr)
    lines = []
    for c in (out.VCompound(), out.Rg1LineVCompound(), out.OutLineVCompound()):
        if c.IsNull():
            continue
        BRepLib.BuildCurves3d_s(c, 1e-6)
        for e in cq.Shape(c).Edges():
            curve = e._geomAdaptor()
            pts = GCPnts_QuasiUniformDeflection(curve, deflection, curve.FirstParameter(), curve.LastParameter())
            if pts.IsDone() and pts.NbPoints() > 1:
                lines.append([(pts.Value(i + 1).X(), pts.Value(i + 1).Y()) for i in range(pts.NbPoints())])
    proj = lambda p: (sum(p[i] * x[i] for i in range(3)), sum(p[i] * y[i] for i in range(3)))
    return lines, proj


class Sheet:
    """An SVG drawing sheet in the style of the page: black lines on white, Times."""

    def __init__(self, width, height, label, ident='cad'):
        self.w, self.h, self.items = width, height, []
        self.label, self.ident = label, ident

    def view(self, lines, proj, box_px, stroke=0.8):
        """Place a projected view inside box_px = (x0, y0, x1, y1); returns the 3D-to-px mapping."""
        xs = [p[0] for l in lines for p in l]
        ys = [p[1] for l in lines for p in l]
        x0, y0, x1, y1 = box_px
        s = min((x1 - x0) / (max(xs) - min(xs)), (y1 - y0) / (max(ys) - min(ys)))
        ox = x0 + ((x1 - x0) - s * (max(xs) - min(xs))) / 2 - s * min(xs)
        oy = y0 + ((y1 - y0) - s * (max(ys) - min(ys))) / 2 + s * max(ys)
        to = lambda u, v: (ox + s * u, oy - s * v)
        d = []
        for l in lines:
            pts = [to(*p) for p in l]
            d.append('M' + ' L'.join(f'{a:.1f},{b:.1f}' for a, b in pts))
        self.items.append(f'<path d="{" ".join(d)}" fill="none" stroke="#000000" stroke-width="{stroke}" '
                          f'stroke-linejoin="round" stroke-linecap="round"/>')
        return lambda p: to(*proj(p)), s

    def text(self, x, y, t, size=12, anchor='middle', extra=''):
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}"{extra}>{t}</text>')

    def line(self, x1, y1, x2, y2, w=0.7, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ''
        self.items.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#000000" stroke-width="{w}"{da}/>')

    def balloons(self, points, left_x, right_x, split_x, top=30, bottom=None, gap=26):
        """Numbered balloons in two columns at left_x and right_x, joined to their anchor points."""
        bottom = bottom or self.h - 30
        for side, col in (('l', left_x), ('r', right_x)):
            group = sorted([(n, p) for n, p in points.items() if (p[0] < split_x) == (side == 'l')], key=lambda q: q[1][1])
            ys, last = [], top - gap
            for _, p in group:
                last = max(p[1], last + gap)
                ys.append(last)
            over = ys[-1] - bottom if ys else 0
            if over > 0:
                ys = [y - over for y in ys]
                for i in range(len(ys) - 2, -1, -1):
                    ys[i] = min(ys[i], ys[i + 1] - gap)
            for (n, p), y in zip(group, ys):
                self.line(p[0], p[1], col, y, 0.6)
                self.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="1.8" fill="#000000"/>'
                                  f'<circle cx="{col:.1f}" cy="{y:.1f}" r="11" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
                self.text(col, y + 4, str(n), 12)

    def dim(self, a, b, offset, text, horizontal=True, ext=True):
        """Dimension line between screen points a and b, offset in px (sign gives the side)."""
        (ax, ay), (bx, by) = a, b
        if horizontal:
            y = min(ay, by) + offset if offset > 0 else min(ay, by) + offset
            y = (max(ay, by) + offset) if offset > 0 else (min(ay, by) + offset)
            if ext:
                self.line(ax, ay, ax, y + (4 if offset > 0 else -4), 0.5)
                self.line(bx, by, bx, y + (4 if offset > 0 else -4), 0.5)
            self.items.append(f'<line x1="{ax:.1f}" y1="{y:.1f}" x2="{bx:.1f}" y2="{y:.1f}" stroke="#000000" stroke-width="0.7" '
                              f'marker-start="url(#{self.ident}-arrow)" marker-end="url(#{self.ident}-arrow)"/>')
            self.text((ax + bx) / 2, y - 4, text, 11)
        else:
            x = (max(ax, bx) + offset) if offset > 0 else (min(ax, bx) + offset)
            if ext:
                self.line(ax, ay, x + (4 if offset > 0 else -4), ay, 0.5)
                self.line(bx, by, x + (4 if offset > 0 else -4), by, 0.5)
            self.items.append(f'<line x1="{x:.1f}" y1="{ay:.1f}" x2="{x:.1f}" y2="{by:.1f}" stroke="#000000" stroke-width="0.7" '
                              f'marker-start="url(#{self.ident}-arrow)" marker-end="url(#{self.ident}-arrow)"/>')
            ym = (ay + by) / 2
            self.items.append(f'<text x="{x - 4:.1f}" y="{ym:.1f}" font-size="11" text-anchor="middle" '
                              f'transform="rotate(-90 {x - 4:.1f} {ym:.1f})">{text}</text>')

    def svg(self, svg_id=None):
        ident = f' id="{svg_id or self.ident}"'
        head = (f'<svg{ident} class="plot wide" viewBox="0 0 {self.w} {self.h}" xmlns="http://www.w3.org/2000/svg" role="img" '
                f'aria-label="{self.label}" font-family="\'Times New Roman\', Times, \'Liberation Serif\', serif">'
                f'<defs><marker id="{self.ident}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" '
                'markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="#000000"/>'
                '</marker></defs>'
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#ffffff"/>')
        return head + ''.join(self.items) + '</svg>\n'


def main():
    full = parts(cut=False)
    assy = cq.Assembly(name='ozone_wafer_cleaning_test_rig')
    for n, name, shape in full:
        assy.add(shape, name=f'{n:02d} {name}')
    assy.save(str(HERE / 'rig.step'))
    spin = cq.Assembly(name='spin_module')
    for n, name, shape in full:
        if n >= 16 and n not in (23, 24, 25, 26):
            spin.add(shape, name=f'{n:02d} {name}')
    spin.save(str(HERE / 'spin_module.step'))

    eye = (1.0, -1.35, 0.85)
    cut = parts(cut=True)
    # Figure: isometric assembly with balloons
    lines, proj = project([sh for _, _, sh in cut], eye)
    sheet = Sheet(1100, 980, 'Isometric view of the test rig with numbered parts', 'fig9')
    to_px, _ = sheet.view(lines, proj, (150, 30, 950, 950))
    pts = {n: to_px(a) for n, (a, _) in ANCHORS.items()}
    sheet.balloons(pts, 60, 1040, 520, top=40, bottom=940)
    sheet.text(550, 972, 'Front panels, cabling and small fittings left out. Process bay shown cut along the spin axis.', 12)
    (HERE / 'rig_iso.svg').write_text(sheet.svg('fig9'), encoding='utf-8')

    # Figure: general arrangement, front view and plan view, with main dimensions
    full = parts(cut=False)
    shapes = [sh for _, _, sh in full]
    ga = Sheet(1100, 800, 'General arrangement of the test rig, front view and plan view', 'fig10')
    fl, fp = project(shapes, (0.0, -1.0, 0.0))
    front, sf = ga.view(fl, fp, (150, 40, 610, 700))
    pl, pp = project(shapes, (0.0, 0.0, 1.0))
    plan, sp = ga.view(pl, pp, (680, 300, 1060, 700))
    ga.text(380, 785, 'Front view', 13)
    ga.text(870, 785, 'Plan view', 13)
    ga.dim(front((0, 0, 0)), front((W, 0, 0)), 26, f'{W:.0f}')
    ga.dim(front((0, 0, 0)), front((0, 0, H)), -78, f'{H:.0f}', horizontal=False)
    ga.dim(front((W, 0, 0)), front((W, 0, H + 300)), 34, f'{H + 300:.0f}', horizontal=False)
    for z, name in ((DECK, 'deck'), (WAFER_Z, 'wafer')):
        q = front((0, 0, z))
        ga.line(q[0] - 6, q[1], q[0] - 20, q[1], 0.6)
        ga.text(q[0] - 24, q[1] + 4, f'{name} {z:.0f}', 11, 'end')
    ga.dim(plan((0, 0, 0)), plan((W, 0, 0)), 24, f'{W:.0f}')
    ga.dim(plan((W, 0, 0)), plan((W, D, 0)), 24, f'{D:.0f}', horizontal=False)
    for i, name in enumerate(('gas bay', 'water bay', 'process bay')):
        a, b = front((BAYS[i], 0, H)), front((BAYS[i + 1], 0, H))
        ga.text((a[0] + b[0]) / 2, a[1] - 8, name, 12, extra=' font-style="italic"')
    ga.text(870, 60, 'All dimensions in mm.', 12)
    ga.text(870, 80, 'Third-angle projection.', 12)
    ga.text(870, 120, 'Wafer loaded by hand through the lid;', 12)
    ga.text(870, 140, 'wafer plane at 1150 mm, deck at 850 mm.', 12)
    (HERE / 'rig_ga.svg').write_text(ga.svg('fig10'), encoding='utf-8')

    # cut-away of the spin module
    near = {16, 17, 18, 19, 20, 21, 22}
    lines, proj = project([sh for n, _, sh in cut if n in near], eye)
    cs = Sheet(560, 620, 'Cut-away view of the spin module', 'fig11')
    to_px, _ = cs.view(lines, proj, (70, 20, 490, 600))
    zoom = {16: (CHAMBER['x1'], AXIS[1], 1000), 17: (CHAMBER['x1'] - 60, CHAMBER['y1'], CHAMBER['z1'] + 30),
            18: (AXIS[0] - CUP_ID / 2, AXIS[1], 1080), 19: (AXIS[0], AXIS[1], WAFER_Z - 60), 20: (AXIS[0] + 120, AXIS[1], WAFER_Z),
            21: (AXIS[0], AXIS[1], DECK - 150), 22: (AXIS[0], AXIS[1] + 80, WAFER_Z + 70)}
    cs.balloons({n: to_px(p) for n, p in zoom.items()}, 30, 530, 280, top=40, bottom=590)
    (HERE / 'spin_cutaway.svg').write_text(cs.svg('fig11'), encoding='utf-8')
    print('wrote rig.step, spin_module.step, rig_iso.svg, rig_ga.svg, spin_cutaway.svg')
    return full


if __name__ == '__main__':
    main()
