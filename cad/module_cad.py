"""Parametric CAD model of the process module of the closed-loop machine (CadQuery 2.x).

    python3 cad/module_cad.py      -> cad/module.step, cad/module_cutaway.svg

Sizes in millimetres. The spin axis is the z axis and the wafer surface is z = 0. A quartz cover
sits 3 mm above the wafer while the resist is stripped and is lifted 60 mm to change the wafer.
The off-gas of the contactor enters through the annulus of a coaxial dispenser at the centre of
the cover, flows outward with the film and leaves through the gas plenum of the rim collector;
the water is flung into the gutter below. The supply skid (generator, contactor, destruct,
dryer, blower) is a separate cabinet and is not drawn.
"""
import math
from pathlib import Path

import cadquery as cq

import rig_cad as C

HERE = Path(__file__).resolve().parent

WAFER_R = 150.0
GAP = 3.0                      # cover above the wafer while stripping
COVER_R, COVER_T = 170.0, 12.0
LIFT = 60.0                    # cover travel for the wafer change
COLLECTOR = dict(r_in=160.0, r_out=205.0, wall=8.0, floor=-90.0, top=30.0)
DECK_Z = -120.0
ENCL = dict(half=270.0, z1=300.0)


def revolve(pts):
    """Solid of revolution about the z axis from (r, z) points."""
    return cq.Workplane('XZ').polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))


def wafer():
    return C.cyl_z(0, 0, -0.8, 0.0, 2 * WAFER_R)


def chuck():
    c = C.cyl_z(0, 0, -20.8, -0.8, 200.0)
    return c.union(C.cyl_z(0, 0, DECK_Z - 40, -20.8, 40.0))           # hollow shaft (bore left out)


def motor():
    """Direct-drive hollow-shaft torque motor with encoder, under the deck."""
    m = C.tube_z(0, 0, DECK_Z - 150, DECK_Z - 30, 230.0, 80.0)
    m = m.union(C.tube_z(0, 0, DECK_Z - 30, DECK_Z, 260.0, 90.0))       # flange
    return m.union(C.cyl_z(0, 0, DECK_Z - 185, DECK_Z - 150, 60.0))      # rotary union (vacuum, purge)


def labyrinth():
    """N2-purged labyrinth between the rotating shaft and the collector floor."""
    a = C.tube_z(0, 0, COLLECTOR['floor'] + 8, -40.0, 70.0, 6.0)        # fixed collar
    return a.union(C.tube_z(0, 0, -60.0, -26.0, 96.0, 6.0))             # rotating skirt


def collector():
    """Rim collector: gutter for the water below, plenum for the gas above, in one PVDF ring."""
    k = COLLECTOR
    ri, ro, t, zf, zt = k['r_in'], k['r_out'], k['wall'], k['floor'], k['top']
    pts = [(ri, -20.0), (ri, zf), (40.0, zf), (40.0, zf - t), (ro + t, zf - t), (ro + t, zt + 6.0),
           (COVER_R + 2.0, zt + 6.0), (COVER_R + 2.0, zt), (ro, zt), (ro, zf), (ri + t, zf), (ri + t, -20.0)]
    body = revolve(pts)
    lip = revolve([(ro, 24.0), (ro, 18.0), (ro - 20.0, 9.0), (ro - 22.0, 13.0)])   # drip lip: shields the plenum, sheds spray down
    ports = C.cyl_z(ro - 10.0, 0, zt + 6.0, zt + 40.0, 18.0)            # gas outlet
    ports = ports.union(C.cyl_z(-(ro - 10.0), 0, zt + 6.0, zt + 40.0, 18.0))
    drains = C.cyl_z(0, ro - 15.0, DECK_Z - 60, zf - t, 22.0).union(C.cyl_z(0, -(ro - 15.0), DECK_Z - 60, zf - t, 22.0))
    return body.union(lip).union(ports).union(drains)


def cover(lifted=False):
    z0 = GAP + (LIFT if lifted else 0.0)
    q = C.cyl_z(0, 0, z0, z0 + COVER_T, 2 * COVER_R).cut(C.cyl_z(0, 0, z0 - 1, z0 + COVER_T + 1, 22.0))
    return q, z0


def carrier(z0):
    """PVDF carrier ring on the quartz, three lift rods and the lift plate."""
    ring = C.tube_z(0, 0, z0 + COVER_T, z0 + COVER_T + 14.0, 2 * COVER_R - 2, 34.0)
    rods = None
    for k in range(3):
        a = math.radians(90 + 120 * k)
        rod = C.cyl_z(150.0 * math.cos(a), 150.0 * math.sin(a), z0 + COVER_T + 14.0, 230.0, 16.0)
        rods = rod if rods is None else rods.union(rod)
    plate = C.tube_z(0, 0, 230.0, 242.0, 360.0, 60.0)
    return ring.union(rods).union(plate)


def lift_cylinders():
    c = None
    for k in range(3):
        a = math.radians(90 + 120 * k)
        x, y = 150.0 * math.cos(a), 150.0 * math.sin(a)
        cy = C.cyl_z(x, y, 242.0, ENCL['z1'] - 10, 36.0)
        c = cy if c is None else c.union(cy)
    return c


def uv_housing(z0):
    """Option: mercury-free UV source above the quartz (LED tiles or 222 nm lamps), with its heat sink."""
    return C.tube_z(0, 0, z0 + COVER_T + 16.0, z0 + COVER_T + 46.0, 290.0, 46.0)


def dispenser(z0):
    """Coaxial dispenser: ozone water in the PFA core, cover gas in the annulus."""
    outer = C.tube_z(0, 0, z0, 260.0, 20.0, 2.0)
    inner = C.tube_z(0, 0, z0 - 1.0, 275.0, 6.35, 1.0)
    tee = C.cyl_x(0, 60, 0, 200.0, 12.0)
    return outer.union(inner).union(tee)


def heat_exchanger():
    """Counterflow tube-in-tube exchanger (drain to ozone water), coiled, under the deck."""
    coil = None
    for k in range(6):
        ring = C.tube_z(330.0, -120.0, DECK_Z - 60 - 26 * k, DECK_Z - 44 - 26 * k, 140.0, 14.0)
        coil = ring if coil is None else coil.union(ring)
    return coil


def deck_and_enclosure():
    h = ENCL['half']
    deck = C.box(-h, -h, DECK_Z - 15, h + 160, h, DECK_Z).cut(C.cyl_z(0, 0, DECK_Z - 20, DECK_Z + 5, 240.0))
    walls = C.box(-h, -h, DECK_Z, h, h, ENCL['z1']).cut(C.box(-h + 10, -h + 10, DECK_Z - 1, h - 10, h - 10, ENCL['z1'] - 10))
    return deck, walls


def parts(cut=False, lifted=False):
    q, z0 = cover(lifted)
    deck, walls = deck_and_enclosure()
    items = [
        (1, 'Deck plate', deck),
        (2, 'Enclosure, PVDF panels, purged', walls),
        (3, 'Direct-drive hollow-shaft motor with encoder, rotary union', motor()),
        (4, 'Vacuum chuck on the hollow shaft', chuck()),
        (5, 'Wafer, 300 mm', wafer()),
        (6, 'Labyrinth seal, nitrogen purge', labyrinth()),
        (7, 'Rim collector: water gutter, drip lip, gas plenum', collector()),
        (8, 'Quartz cover, 340 mm by 12 mm', q),
        (9, 'Carrier ring, lift rods and plate', carrier(z0)),
        (10, 'Lift cylinders (3)', lift_cylinders()),
        (11, 'Coaxial dispenser: water core, gas annulus', dispenser(z0)),
        (12, 'UV source above the quartz (option)', uv_housing(z0)),
        (13, 'Heat-recovery exchanger', heat_exchanger()),
    ]
    if cut:
        cutter = C.box(-1000, -1000, -1000, 1000, 0.0, 1000)
        items = [(n, name, s.cut(cutter) if n not in (13,) else s) for n, name, s in items]
    return items


ANCHORS = {
    1: (350.0, 200.0, DECK_Z), 3: (0.0, 115.0, DECK_Z - 100), 4: (60.0, 0.0, -12.0),
    5: (120.0, 0.0, 0.0), 6: (0.0, 48.0, -45.0), 7: (COLLECTOR['r_out'] + 8, 0.0, -40.0), 8: (120.0, 0.0, GAP + 6),
    9: (0.0, 150.0, 120.0), 10: (0.0, 150.0, 270.0), 11: (0.0, 10.0, 200.0), 12: (-100.0, 0.0, GAP + 45),
    13: (330.0, -50.0, DECK_Z - 100),
}


def main():
    full = parts()
    assy = cq.Assembly(name='closed_loop_process_module')
    for n, name, shape in full:
        assy.add(shape, name=f'{n:02d} {name}')
    assy.save(str(HERE / 'module.step'))

    eye = (0.9, -1.6, 0.6)
    cut = parts(cut=True)
    lines, proj = C.project([sh for n, _, sh in cut if n != 2], eye)
    sheet = C.Sheet(1000, 860, 'Cut-away view of the process module of the closed-loop machine', 'fig15')
    to_px, _ = sheet.view(lines, proj, (150, 30, 850, 820))
    pts = {n: to_px(a) for n, a in ANCHORS.items()}
    sheet.balloons(pts, 60, 940, 480, top=50, bottom=820)
    sheet.text(500, 850, 'Cut along the spin axis; enclosure left out. The cover is down, 3 mm above the wafer.', 12)
    (HERE / 'module_cutaway.svg').write_text(sheet.svg('fig15'), encoding='utf-8')
    print('wrote module.step, module_cutaway.svg')


if __name__ == '__main__':
    main()
