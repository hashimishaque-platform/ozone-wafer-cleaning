"""Section B-B of the process module of the closed-loop machine, with detail C of the rim (scale 5:1).

    python3 cad/module_section.py      -> cad/module_section.svg

Drawn from the same dimensions as module_cad.py. Cut parts are hatched by material; parts behind
the section plane and options are dashed. The film is drawn far thicker than it is (about 0.03 mm).
"""
from pathlib import Path

import rig_cad as C
import module_cad as M

HERE = Path(__file__).resolve().parent
BLUE = '#9ab0d8'


class View:
    """Maps (r, z) in mm to sheet px for one view."""

    def __init__(self, sheet, x0, y0, scale, z_ref):
        self.sh, self.x0, self.y0, self.s, self.zr = sheet, x0, y0, scale, z_ref

    def X(self, r):
        return self.x0 + self.s * r

    def Y(self, z):
        return self.y0 - self.s * (z - self.zr)

    def poly(self, pts, fill='url(#sb-pvdf)', stroke=0.9, mirror=True, dash=None, clip=None):
        for sign in ((1, -1) if mirror else (1,)):
            d = 'M' + ' L'.join(f'{self.X(sign * r):.1f},{self.Y(z):.1f}' for r, z in pts) + ' Z'
            da = f' stroke-dasharray="{dash}"' if dash else ''
            cp = f' clip-path="url(#{clip})"' if clip else ''
            self.sh.items.append(f'<path d="{d}" fill="{fill}" stroke="#000000" stroke-width="{stroke}"{da}{cp}/>')

    def rect(self, r0, z0, r1, z1, fill='url(#sb-pvdf)', mirror=True, stroke=0.9, dash=None, clip=None):
        self.poly([(r0, z0), (r1, z0), (r1, z1), (r0, z1)], fill, stroke, mirror, dash, clip)


class Sheet(C.Sheet):
    def svg(self, svg_id=None):
        out = super().svg(svg_id)
        pats = ('<pattern id="sb-pvdf" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                '<rect width="7" height="7" fill="#ffffff"/><line x1="0" y1="0" x2="0" y2="7" stroke="#000000" stroke-width="0.6"/></pattern>'
                '<pattern id="sb-steel" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">'
                '<rect width="4" height="4" fill="#ffffff"/><line x1="0" y1="0" x2="0" y2="4" stroke="#000000" stroke-width="0.6"/></pattern>'
                '<pattern id="sb-alu" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                '<rect width="9" height="9" fill="#ffffff"/><line x1="0" y1="0" x2="0" y2="9" stroke="#000000" stroke-width="0.5"/>'
                '<line x1="3" y1="0" x2="3" y2="9" stroke="#000000" stroke-width="0.5"/></pattern>'
                '<clipPath id="sb-detail"><circle cx="820" cy="250" r="160"/></clipPath>')
        return out.replace('</defs>', pats + '</defs>', 1)


def module(v, clip=None, detail=False):
    """Everything in the section plane, for either view."""
    k, zg, ct = M.COLLECTOR, M.GAP, M.COVER_T
    ri, ro, t, zf, zt = k['r_in'], k['r_out'], k['wall'], k['floor'], k['top']
    film = 0.6 if detail else 1.6                     # drawn thickness, mm (real: about 0.03)
    # deck
    if not detail:
        v.rect(120, M.DECK_Z - 15, 300, M.DECK_Z, 'url(#sb-alu)', clip=clip)
    # collector: gutter, outer wall, plenum ceiling and gas port, baffle
    v.poly([(ri, -20.0), (ri, zf), (40.0, zf), (40.0, zf - t), (ro + t, zf - t), (ro + t, zt + 6.0),
            (M.COVER_R + 2.0, zt + 6.0), (M.COVER_R + 2.0, zt), (ro, zt), (ro, zf), (ri + t, zf), (ri + t, -20.0)], clip=clip)
    v.poly([(ro, 24.0), (ro, 18.0), (ro - 20.0, 9.0), (ro - 22.0, 13.0)], clip=clip)          # drip lip
    v.rect(ro - 19.0, zt + 6.0, ro - 1.0, zt + 40.0, '#ffffff', clip=clip)
    v.rect(ro - 17.0, zt + 6.0, ro - 3.0, zt + 40.0, '#ffffff', stroke=0.6, clip=clip)
    # chuck and shaft (steel core, PVDF chuck), wafer, film
    v.rect(0, -20.8, 100, -0.8, clip=clip)
    if not detail:
        v.rect(0, M.DECK_Z - 40, 20, -20.8, 'url(#sb-steel)')
        v.rect(29, zf + 8, 35, -40.0)                 # labyrinth collar
        v.rect(42, -60, 48, -26.0, 'url(#sb-steel)')    # rotating skirt
        # motor in view, with a break line
        v.rect(40, M.DECK_Z - 150, 115, M.DECK_Z - 30, '#ffffff')
        v.rect(45, M.DECK_Z - 30, 130, M.DECK_Z, '#ffffff')
        v.rect(0, M.DECK_Z - 185, 30, M.DECK_Z - 150, '#ffffff')
    v.rect(0, -0.8, M.WAFER_R, 0.0, '#000000', stroke=0.3, clip=clip)
    v.rect(0, 0.0, M.WAFER_R, film, BLUE, stroke=0, clip=clip)
    # cover (quartz), carrier ring, UV option (dashed), dispenser
    v.rect(11, zg, M.COVER_R, zg + ct, '#e6eef5', clip=clip)
    v.rect(17, zg + ct, M.COVER_R - 1, zg + ct + 14, clip=clip)
    if not detail:
        v.rect(23, zg + ct + 16, 145, zg + ct + 46, '#ffffff', dash='4 3', stroke=0.7)
        v.rect(8, zg, 10, 140, '#ffffff', stroke=0.7)
        v.rect(2.2, zg - 1, 3.2, 150, '#dddddd', stroke=0.5)


def main():
    sh = Sheet(1000, 760, 'Section B-B through the process module of the closed-loop machine, with detail C', 'fig16')
    main_v = View(sh, 300.0, 300.0, 1.18, 0.0)
    module(main_v)
    X, Y = main_v.X, main_v.Y
    # centre line, break line of the motor
    sh.line(X(0), Y(160), X(0), Y(M.DECK_Z - 195), 0.5, dash='14 3 2 3')
    # lift rods behind the plane (dashed), lift stroke
    for r in (130.0, -130.0):
        sh.line(X(r), Y(M.GAP + M.COVER_T + 14), X(r), Y(150), 0.7, dash='4 3')
    # dimensions (radii from the axis, on the right half)
    ro = M.COLLECTOR['r_out'] + M.COLLECTOR['wall']
    sh.dim((X(0), Y(80)), (X(M.COVER_R), Y(80)), 0.0001, 'R170 (quartz Ø340 × 12)', ext=False)
    sh.line(X(M.COVER_R), Y(M.GAP + M.COVER_T), X(M.COVER_R), Y(84), 0.5)
    sh.dim((X(0), Y(-108)), (X(ro), Y(-108)), 0.0001, 'R213', ext=False)
    sh.line(X(ro), Y(M.COLLECTOR['floor'] - 8), X(ro), Y(-112), 0.5)
    sh.dim((X(ro), Y(0)), (X(ro), Y(M.DECK_Z)), 44, '120', horizontal=False)
    sh.line(X(M.WAFER_R), Y(0), X(ro + 48), Y(0), 0.5)
    sh.text(X(-25), Y(150) - 6, 'coaxial dispenser', 11, 'end')
    sh.line(X(-24), Y(150) - 4, X(-6), Y(120), 0.6)
    sh.text(X(-84), Y(70), 'UV source (option)', 11, 'middle')
    sh.text(X(-180), Y(M.DECK_Z - 100), 'direct-drive motor', 11, 'middle')
    sh.text(X(-180), Y(M.DECK_Z - 114), 'with encoder', 11, 'middle')
    sh.text(X(60), Y(-50), 'N₂ purge', 11, 'start')
    sh.line(X(58), Y(-48), X(45), Y(-40), 0.6)
    sh.text(X(150), Y(150) - 6, 'lift 60 mm for the wafer change', 11, 'middle')
    # detail C marker
    sh.items.append(f'<circle cx="{X(181):.1f}" cy="{Y(5):.1f}" r="{1.18 * 32:.1f}" fill="none" stroke="#000000" '
                    'stroke-width="0.8" stroke-dasharray="6 3"/>')
    sh.text(X(181) + 30, Y(5) - 38, 'C', 13)
    # ---- detail C, scale 5:1
    dv = View(sh, 820.0 - 5.0 * 181.0, 250.0, 5.0, 5.0)
    sh.items.append('<circle cx="820" cy="250" r="160" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
    module(dv, clip='sb-detail', detail=True)
    # flows in the detail: water (solid) and cover gas (dashed)
    arr = 'marker-end="url(#fig16-arrow)"'
    def flow(pts, gas=False):
        d = 'M' + ' L'.join(f'{dv.X(r):.1f},{dv.Y(z):.1f}' for r, z in pts)
        dash = ' stroke-dasharray="5 3"' if gas else ''
        sh.items.append(f'<path d="{d}" fill="none" stroke="#0000cc" stroke-width="1.4"{dash} {arr} clip-path="url(#sb-detail)"/>')
    flow([(151.0, 0.6), (186.0, -2.0), (203.0, -8.0)])
    flow([(203.0, -12.0), (203.0, -26.0)])
    flow([(152.0, 2.0), (168.0, 2.0), (176.0, 8.0), (180.0, 20.0), (194.0, 28.0)], gas=True)
    sh.text(820, 430, 'Detail C, scale 5:1', 13)
    sh.text(820, 448, 'water (solid) into the gutter, cover gas (dashed) up into the plenum', 11)
    dx, dy = dv.X, dv.Y
    sh.dim((dx(156), dy(0)), (dx(156), dy(M.GAP)), -16, '', horizontal=False, ext=False)
    sh.text(dx(156) - 24, dy(1.5) + 4, '3', 11, 'end')
    sh.text(dx(153), dy(-6), 'wafer', 10, 'start')
    sh.text(dx(153), dy(11), 'quartz', 10, 'start')
    sh.text(dx(171), dy(-14), 'spray', 10, 'start')
    sh.text(dx(186), dy(33), 'plenum', 10, 'start')
    sh.text(dx(178), dy(-22), 'gutter', 10, 'start')
    sh.text(dx(191), dy(5), 'drip lip', 10, 'start')
    # balloons for the main view
    pts = {'4': (X(-60), Y(-12)), '5': (X(-120), Y(-0.4)), '6': (X(-32), Y(-60)), '7': (X(-150), Y(-94)),
           '8': (X(-100), Y(M.GAP + 6)), '9': (X(-90), Y(M.GAP + M.COVER_T + 7)), '11': (X(0), Y(100)),
           '3': (X(-80), Y(M.DECK_Z - 90)), '1': (X(-270), Y(M.DECK_Z - 7))}
    sh.balloons(pts, 30, 30, 10_000, top=120, bottom=700)
    # legend and title block
    lx, ly = 600, 500
    for i, (fill, name) in enumerate((('url(#sb-pvdf)', 'PVDF'), ('url(#sb-steel)', 'stainless steel 316L'),
                                     ('url(#sb-alu)', 'aluminium, PVDF-covered'), ('#e6eef5', 'quartz'),
                                     ('#dddddd', 'PFA'), (BLUE, 'film (not to scale)'))):
        col, row = i % 2, i // 2
        x, y = lx + col * 200, ly + row * 22
        sh.items.append(f'<rect x="{x}" y="{y}" width="26" height="14" fill="{fill}" stroke="#000000" stroke-width="0.8"/>')
        sh.text(x + 34, y + 11, name, 12, 'start')
    tb = [('Process module, section B-B', 13), ('Closed-loop machine for ozonated-water resist strip', 12),
          ('Dimensions in mm; item numbers as in the parts list', 12), ('Drawn by H. Ishaque, October 2026', 12)]
    sh.items.append('<rect x="600" y="590" width="380" height="132" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
    for i, (t, size) in enumerate(tb):
        if i:
            sh.line(600, 590 + 33 * i, 980, 590 + 33 * i, 0.6)
        sh.text(610, 612 + 33 * i, t, size, 'start')
    (HERE / 'module_section.svg').write_text(sh.svg('fig16'), encoding='utf-8')
    print('wrote module_section.svg')


if __name__ == '__main__':
    main()
