"""Section A-A of the spin module: a 2D engineering drawing from the same dimensions as the CAD model.

    python3 cad/drawings.py      -> cad/spin_section.svg

The section plane contains the spin axis and runs from left to right across the front of the
chamber. Cut parts are hatched by material; parts behind the plane are drawn dashed. Item
numbers follow the parts list of the rig, with letters for details of an item.
"""
from pathlib import Path

import rig_cad as C

HERE = Path(__file__).resolve().parent
S = 0.72                     # px per mm
X0, ZREF, Y0 = 330.0, 540.0, 712.0
WATER_BLUE = '#9ab0d8'


def X(x):
    return X0 + S * x


def Y(z):
    return Y0 - S * (z - ZREF)


class Section(C.Sheet):
    def poly(self, pts, fill='url(#sec-pvdf)', stroke=0.9, mirror=True, dash=None):
        for sign in ((1, -1) if mirror else (1,)):
            d = 'M' + ' L'.join(f'{X(sign * x):.1f},{Y(z):.1f}' for x, z in pts) + ' Z'
            da = f' stroke-dasharray="{dash}"' if dash else ''
            self.items.append(f'<path d="{d}" fill="{fill}" stroke="#000000" stroke-width="{stroke}"{da}/>')

    def rect(self, x0, z0, x1, z1, fill='url(#sec-pvdf)', mirror=False, stroke=0.9, dash=None):
        self.poly([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], fill, stroke, mirror, dash)

    def mm_dim_h(self, x0, x1, z, text):
        self.dim((X(x0), Y(z)), (X(x1), Y(z)), 0.0001, text, horizontal=True, ext=False)

    def svg(self, svg_id=None):
        out = super().svg(svg_id)
        pats = ('<pattern id="sec-pvdf" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                '<rect width="7" height="7" fill="#ffffff"/><line x1="0" y1="0" x2="0" y2="7" stroke="#000000" stroke-width="0.6"/></pattern>'
                '<pattern id="sec-steel" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">'
                '<rect width="4" height="4" fill="#ffffff"/><line x1="0" y1="0" x2="0" y2="4" stroke="#000000" stroke-width="0.6"/></pattern>'
                '<pattern id="sec-alu" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                '<rect width="9" height="9" fill="#ffffff"/><line x1="0" y1="0" x2="0" y2="9" stroke="#000000" stroke-width="0.5"/>'
                '<line x1="3" y1="0" x2="3" y2="9" stroke="#000000" stroke-width="0.5"/></pattern>')
        return out.replace('</defs>', pats + '</defs>', 1)


def main():
    sh = Section(960, 760, 'Section A-A through the spin module', 'fig12')
    wz, cup_r = C.WAFER_Z, C.CUP_ID / 2
    # deck and chamber
    sh.rect(-300, C.DECK - 12, 300, C.DECK, 'url(#sec-alu)')
    sh.rect(-260, 950, -250, 1350); sh.rect(250, 950, 260, 1350)
    sh.rect(-260, 950, -35, 960); sh.rect(35, 950, 260, 960)
    # lid, viewport, gas diffuser, seal
    sh.rect(-260, 1350, -120, 1380); sh.rect(120, 1350, 260, 1380)
    sh.rect(-130, 1380, 130, 1388, '#eef3f8', stroke=0.8)
    sh.line(X(-128), Y(1384), X(128), Y(1384), 0.4)
    sh.rect(185, 1380, 215, 1400, 'url(#sec-pvdf)')
    sh.rect(170, 1340, 230, 1350, '#ffffff', dash='2 2')
    sh.rect(-258, 1350, -252, 1354, '#000000'); sh.rect(252, 1350, 258, 1354, '#000000')
    sh.rect(236, 1388, 256, 1400, '#ffffff')
    # cup: wall, lip, floor with exhaust openings and the gutter behind a weir
    lip = [(cup_r, 1000), (cup_r, wz + 25), (cup_r - 25, wz + 40), (cup_r - 25, wz + 48), (cup_r + 8, wz + 28), (cup_r + 8, 992),
           (175, 992), (175, 1000)]
    sh.poly(lip)
    sh.poly([(171, 1000), (175, 1000), (175, 1022), (171, 1022)])                        # weir
    sh.poly([(60, 992), (120, 992), (120, 1000), (60, 1000)])                             # floor inside the openings
    sh.poly([(150, 992), (171, 992), (171, 1000), (150, 1000)])
    sh.poly([(24, 992), (30, 992), (30, 1030), (24, 1030)])                               # collar of the labyrinth
    sh.rect(-30, 990, 30, 992, 'url(#sec-pvdf)')
    sh.poly([(54, 980), (60, 980), (60, 992), (54, 992)])                                 # standoff ring
    # shaft with vacuum bore, PFA sleeve, rotating skirt of the labyrinth
    sh.rect(-15, 590, -4, wz - 22, 'url(#sec-steel)'); sh.rect(4, 590, 15, wz - 22, 'url(#sec-steel)')
    sh.rect(-17, 992, -15, wz - 22, '#dddddd', stroke=0.5); sh.rect(15, 992, 17, wz - 22, '#dddddd', stroke=0.5)
    sh.poly([(17, 1040), (40, 1040), (40, 1010), (36, 1010), (36, 1036), (17, 1036)])
    # chuck, wafer, film
    sh.rect(-100, wz - 22, -4, wz - 2); sh.rect(4, wz - 22, 100, wz - 2)
    for x in (-80, -50, 50, 80):
        sh.rect(x - 2, wz - 4, x + 2, wz - 2, '#ffffff', stroke=0.5)
    sh.rect(-150, wz - 2, 150, wz, '#000000', stroke=0.3)
    sh.rect(-150, wz, 150, wz + 1.6, WATER_BLUE, stroke=0)
    # bearing housing with two bearings and a lip seal
    sh.rect(-35, C.DECK, -27, 950, 'url(#sec-steel)'); sh.rect(27, C.DECK, 35, 950, 'url(#sec-steel)')
    for z0 in (865.0, 915.0):
        for sgn in (-1, 1):
            sh.rect(sgn * 15, z0, sgn * 27, z0 + 20, '#ffffff', stroke=0.8)
            sh.line(X(sgn * 15), Y(z0), X(sgn * 27), Y(z0 + 20), 0.6)
            sh.line(X(sgn * 15), Y(z0 + 20), X(sgn * 27), Y(z0), 0.6)
    sh.rect(-27, 940, -15, 948, '#555555', stroke=0.5); sh.rect(15, 940, 27, 948, '#555555', stroke=0.5)
    # motor (in view, not cut), flange, coupling, rotary union with vacuum line
    sh.rect(-80, C.DECK - 40, 80, C.DECK - 12, '#ffffff')
    sh.rect(-60, C.DECK - 260, 60, C.DECK - 40, '#ffffff')
    sh.rect(-20, C.DECK - 300, 20, C.DECK - 260, '#ffffff')
    sh.line(X(20), Y(C.DECK - 280), X(80), Y(C.DECK - 280), 1.2)
    sh.text(X(84), Y(C.DECK - 280) + 4, 'vacuum', 11, 'start')
    # nozzle arm (cut), PFA nozzle tube, arm behind the plane dashed, megasonic option dashed
    sh.rect(-10, wz + 60, 10, wz + 80, 'url(#sec-pvdf)')
    sh.rect(-4, wz + C.NOZZLE_GAP, 4, wz + 60, '#ffffff')
    sh.rect(-115, wz + 20, -85, wz + 34, '#ffffff', dash='4 3', stroke=0.7)
    sh.line(X(-100), Y(wz + 34), X(-100), Y(1330), 0.7, dash='4 3')
    # drain line from the gutter, AIT-302 tap; exhaust port behind the plane (dashed circle)
    sh.rect(-186, 960, -178, 992, '#ffffff', stroke=0.8)
    sh.rect(-186, C.DECK - 60, -178, 950, '#ffffff', stroke=0.8)
    sh.line(X(-186), Y(905), X(-226), Y(905), 0.8)
    sh.items.append(f'<circle cx="{X(-232):.1f}" cy="{Y(905):.1f}" r="6" fill="#ffffff" stroke="#000000" stroke-width="0.8"/>')
    sh.text(X(-232), Y(905) + 3.5, 'A', 8)
    sh.items.append(f'<circle cx="{X(180):.1f}" cy="{Y(1010):.1f}" r="{S * 50:.1f}" fill="none" stroke="#000000" '
                    f'stroke-width="0.7" stroke-dasharray="4 3"/>')
    # centre line
    sh.line(X(0), Y(ZREF + 5), X(0), Y(1415), 0.5, dash='14 3 2 3')
    # dimensions
    sh.dim((X(-260), Y(1388)), (X(260), Y(1388)), -22, '520')
    sh.dim((X(-150), Y(wz)), (X(150), Y(wz)), -(S * 140), 'wafer Ø300')
    sh.dim((X(260), Y(950)), (X(260), Y(1350)), 34, '400', horizontal=False)
    sh.dim((X(-300), Y(C.DECK)), (X(-150), Y(wz)), -14, '300', horizontal=False)
    sh.line(X(-150), Y(wz), X(-306), Y(wz), 0.5)
    sh.dim((X(26), Y(wz)), (X(26), Y(wz + C.NOZZLE_GAP)), 18, '', horizontal=False, ext=False)
    sh.text(X(26) + 26, Y(wz + 12), '15 (10 to 20)', 11, 'start')
    sh.line(X(44), Y(1000), X(62), Y(975), 0.6)
    sh.text(X(64), Y(970), 'N₂ purge', 11, 'start')
    sh.text(X(-cup_r) - 12, Y(1110), 'Ø380', 11, 'end')
    # balloons
    pts = {
        '2': (X(-280), Y(C.DECK - 6)), '16': (X(-255), Y(1250)), '17': (X(-200), Y(1365)), '17a': (X(60), Y(1384)),
        '17b': (X(200), Y(1345)), '17c': (X(246), Y(1394)), '18': (X(cup_r + 4), Y(1080)), '18a': (X(cup_r - 15), Y(wz + 40)),
        '18b': (X(173), Y(1010)), '18c': (X(135), Y(996)), '19': (X(70), Y(wz - 12)), '19a': (X(-10), Y(1085)),
        '20': (X(120), Y(wz + 0.8)), '21': (X(40), Y(C.DECK - 150)), '21a': (X(21), Y(875)), '21b': (X(38), Y(1025)),
        '21c': (X(0), Y(C.DECK - 290)), '22': (X(0), Y(wz + 70)), '22a': (X(0), Y(wz + 35)), '27': (X(-100), Y(wz + 27)),
        '25': (X(-182), Y(925)), '23': (X(180 + 35), Y(1010 + 35)),
    }
    left = {k: v for k, v in pts.items() if v[0] < X(0) or k in ('22a', '21c', '19a', '22')}
    right = {k: v for k, v in pts.items() if k not in left}
    sh.balloons({k: v for k, v in left.items()}, 40, 40, 10_000, top=60, bottom=700)
    sh.balloons({k: v for k, v in right.items()}, 640, 640, -10_000, top=60, bottom=700)
    # legend and title block
    lx, ly = 690, 70
    for i, (fill, name) in enumerate((('url(#sec-pvdf)', 'PVDF'), ('url(#sec-steel)', 'stainless steel 316L'),
                                     ('url(#sec-alu)', 'aluminium, PVDF-covered'), ('#eef3f8', 'quartz'),
                                     ('#dddddd', 'PFA sleeve'), ('#555555', 'seal, FFKM'))):
        sh.items.append(f'<rect x="{lx}" y="{ly + i * 22}" width="26" height="14" fill="{fill}" stroke="#000000" stroke-width="0.8"/>')
        sh.text(lx + 34, ly + i * 22 + 11, name, 12, 'start')
    sh.text(lx, ly + 150, 'Dashed: behind the section plane', 12, 'start')
    sh.text(lx, ly + 168, '(nozzle arm, exhaust port, options).', 12, 'start')
    sh.text(lx, ly + 186, 'Detail A: AIT-302 sample tap.', 12, 'start')
    tb = [('Spin module, section A-A', 13), ('Test rig for ozonated-water resist strip', 12), ('Dimensions in mm', 12),
          ('Drawn by H. Ishaque, October 2026', 12), ('Sheet 1 of 1', 12)]
    sh.items.append('<rect x="680" y="590" width="265" height="150" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
    for i, (t, size) in enumerate(tb):
        sh.line(680, 590 + 30 * i, 945, 590 + 30 * i, 0.6) if i else None
        sh.text(690, 610 + 30 * i, t, size, 'start')
    (HERE / 'spin_section.svg').write_text(sh.svg('fig12'), encoding='utf-8')
    print('wrote spin_section.svg')


if __name__ == '__main__':
    main()
