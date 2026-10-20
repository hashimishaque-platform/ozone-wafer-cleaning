"""Draws Figure 7, the piping and instruments of the test rig, as rig.svg. The page inlines it.

    python3 rig.py      -> rig.svg

Instrument tags follow ISA-5.1. Numbers: 1xx gas, 2xx water, 3xx chamber, 4xx safety.
"""
from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1080, 620
FONT = "'Times New Roman', Times, 'Liberation Serif', serif"
STYLE = {
    'water': 'stroke="#000000" stroke-width="2" fill="none"',
    'gas': 'stroke="#000000" stroke-width="1.5" stroke-dasharray="7 4" fill="none"',
    'tap': 'stroke="#000000" stroke-width="0.8" fill="none"',
    'thin': 'stroke="#000000" stroke-width="1" fill="none"',
    'option': 'stroke="#000000" stroke-width="1" stroke-dasharray="4 3" fill="none"',
}
out = []


def add(s):
    out.append(s)


def text(x, y, s, size=13, anchor='middle', extra=''):
    add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')


def line(pts, kind='water', arrow=False):
    d = 'M' + ' L'.join(f'{x},{y}' for x, y in pts)
    end = ' marker-end="url(#ar)"' if arrow else ''
    add(f'<path d="{d}" {STYLE[kind]}{end}/>')


def box(x, y, w, h, labels=(), size=12, dashed=False, rx=0):
    dash = ' stroke-dasharray="4 3"' if dashed else ''
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#ffffff" stroke="#000000" stroke-width="1.2"{dash}/>')
    n = len(labels)
    for i, s in enumerate(labels):
        text(x + w / 2, y + h / 2 + 4 + (i - (n - 1) / 2) * (size + 2), s, size)


def bubble(cx, cy, tag, num, tap=None):
    """Instrument bubble; tap is the point on the process line or equipment it connects to."""
    if tap:
        tx, ty = tap
        if tx == cx:
            y0 = cy + 15 if ty > cy else cy - 15
            line([(cx, y0), (tx, ty)], 'tap')
        else:
            x0 = cx - 15 if tx < cx else cx + 15
            line([(x0, cy), (tx, ty)], 'tap')
    add(f'<circle cx="{cx}" cy="{cy}" r="15" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
    text(cx, cy - 1, tag, 10)
    text(cx, cy + 10, num, 10)


def valve(cx, cy, vertical=False, third=None):
    """Two-way valve as a bow tie; third = 'down' adds the third port of a three-way valve."""
    if vertical:
        a = f'{cx - 8},{cy - 10} {cx + 8},{cy - 10} {cx},{cy}'
        b = f'{cx - 8},{cy + 10} {cx + 8},{cy + 10} {cx},{cy}'
    else:
        a = f'{cx - 10},{cy - 8} {cx - 10},{cy + 8} {cx},{cy}'
        b = f'{cx + 10},{cy - 8} {cx + 10},{cy + 8} {cx},{cy}'
    for pts in (a, b):
        add(f'<polygon points="{pts}" fill="#ffffff" stroke="#000000" stroke-width="1.1"/>')
    if third == 'down':
        add(f'<polygon points="{cx - 8},{cy + 16} {cx + 8},{cy + 16} {cx},{cy}" fill="#ffffff" stroke="#000000" stroke-width="1.1"/>')


def check_valve(cx, cy):
    valve(cx, cy)
    add(f'<polygon points="{cx - 10},{cy - 8} {cx - 10},{cy + 8} {cx},{cy}" fill="#000000"/>')


def interlock(cx, cy):
    add(f'<polygon points="{cx},{cy - 9} {cx + 9},{cy} {cx},{cy + 9} {cx - 9},{cy}" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
    text(cx, cy + 4, 'I', 11)


def zigzag(x0, x1, cy, amp=9):
    n = 6
    pts = [(x0, cy)] + [(x0 + (x1 - x0) * (i + 0.5) / n, cy + (amp if i % 2 else -amp)) for i in range(n)] + [(x1, cy)]
    add('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts) + f'" {STYLE["thin"]}/>')


def cylinder(x, y, w, h, label):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" fill="#ffffff" stroke="#000000" stroke-width="1.2"/>')
    text(x + w / 2, y + h / 2 + 4, label, 12)


add(f'<svg id="fig7" class="plot wide" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
    f'aria-label="Piping and instruments of the test rig" font-family="{FONT}">')
add('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" '
    'markerHeight="10" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#000000"/></marker></defs>')
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>')

# ---------------------------------------------------------------- gas: oxygen, generator, contactor
cylinder(14, 40, 30, 62, 'O₂')
text(29, 118, 'oxygen', 11)
line([(44, 70), (72, 70)], 'gas')
box(72, 60, 36, 20, ['MFC'], 10)
bubble(90, 30, 'FIC', '101', tap=(90, 60))
line([(108, 70), (138, 70)], 'gas')
box(138, 44, 112, 52, ['Ozone', 'generator'], 13)
line([(166, 116), (166, 97)], 'thin', arrow=True)
line([(222, 96), (222, 115)], 'thin', arrow=True)
text(194, 130, 'cooling water', 11)
interlock(262, 46)
line([(250, 70), (322, 70)], 'gas')
bubble(292, 30, 'AIT', '102', tap=(292, 70))
check_valve(332, 70)
text(332, 92, 'check valve', 10.5)
line([(342, 70), (440, 70)], 'gas')
line([(390, 70), (390, 62)], 'thin')
valve(390, 52, vertical=True)
text(390, 34, 'PSV', 10.5)
add('<circle cx="440" cy="70" r="2.6" fill="#000000"/>')
line([(440, 70), (440, 199)], 'gas', arrow=True)
# chamber gas, the "process gas" option
line([(440, 70), (602, 70)], 'gas')
box(602, 60, 36, 20, ['MFC'], 10)
bubble(620, 30, 'FIC', '104', tap=(620, 60))
line([(638, 70), (1010, 70), (1010, 299)], 'gas', arrow=True)
text(820, 62, 'ozone gas to the chamber (option)', 11, extra=' font-style="italic"')

# ---------------------------------------------------------------- ozone contactor
box(405, 200, 70, 220)
for x in (429, 440, 451):
    add(f'<line x1="{x}" y1="212" x2="{x}" y2="408" stroke="#888888" stroke-width="0.8"/>')
line([(417, 396), (417, 222)], 'thin', arrow=True)
line([(463, 222), (463, 396)], 'option', arrow=True)
text(440, 438, 'membrane', 12)
text(440, 452, 'contactor', 12)
line([(475, 400), (490, 400)], 'gas')
valve(500, 400)
bubble(500, 440, 'PIC', '103', tap=(500, 408))
line([(510, 400), (620, 400), (620, 559)], 'gas', arrow=True)

# ---------------------------------------------------------------- water: CO2, resistivity, chiller
text(16, 410, 'ultrapure', 11, 'start')
text(16, 423, 'water', 11, 'start')
line([(16, 390), (70, 390)])
box(70, 372, 50, 36, ['CO₂'], 12)
text(95, 424, 'CO₂ contactor', 11)
cylinder(80, 228, 30, 56, 'CO₂')
line([(95, 284), (95, 304)], 'gas')
box(77, 304, 36, 20, ['MFC'], 10)
bubble(142, 314, 'FIC', '201', tap=(113, 314))
line([(95, 324), (95, 371)], 'gas', arrow=True)
line([(120, 390), (200, 390)])
bubble(165, 352, 'AIT', '202', tap=(165, 390))
box(200, 374, 54, 32)
zigzag(206, 248, 390)
bubble(227, 340, 'TIC', '203', tap=(227, 374))
text(227, 422, 'chiller', 11)
line([(254, 390), (404, 390)], arrow=True)

# ---------------------------------------------------------------- water: from the contactor to the nozzle
line([(475, 230), (522, 230)])
bubble(500, 192, 'AIT', '204', tap=(500, 230))
box(522, 220, 38, 20, ['LFC'], 10)
bubble(541, 156, 'FIC', '205', tap=(541, 220))
line([(560, 230), (582, 230)])
box(582, 214, 52, 32)
zigzag(588, 628, 230)
bubble(608, 192, 'TIC', '206', tap=(608, 214))
text(608, 262, 'heater', 11)
line([(634, 230), (652, 230)])
box(652, 212, 18, 40, rx=5)
line([(661, 212), (661, 190)], 'gas', arrow=True)
text(667, 184, 'vent to destruct', 10.5, 'start')
text(661, 268, 'bubble trap', 11)
line([(670, 230), (688, 230)])
add(f'<path d="M688,230 c6,-14 12,-14 12,0 c6,14 12,14 12,0 c6,-14 12,-14 12,0 c6,14 12,14 12,0" {STYLE["water"]}/>')
text(712, 254, 'supply line', 11)
line([(736, 230), (790, 230)])
line([(752, 230), (752, 244)], 'thin')
valve(752, 254, vertical=True)
text(752, 280, 'SP', 10.5)
bubble(768, 192, 'AIT', '207', tap=(768, 230))
valve(800, 230, third='down')
line([(810, 230), (930, 230), (930, 350)])
add('<polygon points="923,349 937,349 930,362" fill="#000000"/>')
line([(800, 246), (800, 519)], arrow=True)

# ---------------------------------------------------------------- spin chamber
add('<rect x="820" y="300" width="240" height="180" fill="none" stroke="#000000" stroke-width="1.2"/>')
add('<polyline points="848,338 834,348 834,466 1046,466 1046,348 1032,338" fill="none" stroke="#000000" stroke-width="1.2"/>')
add('<rect x="850" y="381" width="160" height="4" fill="#9ab0d8"/>')
add('<rect x="850" y="385" width="160" height="4" fill="#000000"/>')
add('<rect x="918" y="389" width="24" height="28" fill="#ffffff" stroke="#000000" stroke-width="1.2"/>')
add('<line x1="930" y1="417" x2="930" y2="500" stroke="#000000" stroke-width="3"/>')
box(906, 500, 48, 30, ['M'], 13)
bubble(986, 515, 'SIC', '301', tap=(954, 515))
line([(948, 375), (994, 375)], 'thin', arrow=True)
line([(912, 375), (866, 375)], 'thin', arrow=True)
text(1028, 380, 'film', 11)
text(1028, 395, 'wafer', 11)
line([(873, 300), (873, 338)], 'option')
box(858, 338, 30, 14, dashed=True)
text(878, 318, 'megasonic', 10.5, 'start')
text(878, 330, '(option)', 10.5, 'start')
text(1050, 318, 'spin', 11, 'end')
text(1050, 330, 'chamber', 11, 'end')
bubble(1046, 258, 'AIT', '401')
interlock(1069, 236)
text(1046, 290, 'ambient', 10.5)

# ---------------------------------------------------------------- drain and exhaust
line([(842, 466), (842, 519)], arrow=True)
bubble(872, 500, 'AIT', '302', tap=(842, 500))
box(760, 520, 90, 36, ['drain tank'], 11, rx=4)
line([(760, 545), (732, 545)], arrow=True)
text(728, 549, 'to drain', 11, 'end')
line([(1032, 466), (1032, 580), (701, 580)], 'gas', arrow=True)
bubble(1062, 505, 'FT', '303', tap=(1032, 505))
bubble(1062, 545, 'AIT', '304', tap=(1032, 545))
box(580, 560, 120, 40, ['Ozone destruct', 'heated catalyst'], 11)
line([(580, 580), (548, 580)], 'gas', arrow=True)
text(544, 584, 'to house exhaust', 11, 'end')

# ---------------------------------------------------------------- key
add('<rect x="14" y="470" width="400" height="140" fill="#ffffff" stroke="#808080" stroke-width="1"/>')
line([(26, 490), (60, 490)])
text(66, 494, 'water', 11, 'start')
line([(110, 490), (144, 490)], 'gas')
text(150, 494, 'gas', 11, 'start')
add('<rect x="186" y="483" width="30" height="14" fill="#ffffff" stroke="#000000" stroke-width="1" stroke-dasharray="4 3"/>')
text(222, 494, 'option', 11, 'start')
text(282, 494, 'SP sample port', 11, 'start')
for i, s in enumerate([
        'Tags after ISA-5.1. First letter: A analysis (ozone, resistivity),',
        'F flow, P pressure, S speed, T temperature. Then I indicate,',
        'T transmit, C control. 1xx gas, 2xx water, 3xx chamber, 4xx safety.',
        'Interlock: the generator stops and the ozone water valve shuts on',
        '0.1 ppm ambient ozone (AIT-401), low exhaust flow (FT-303), open',
        'lid, a leak in the drip tray, or low cooling water.']):
    text(26 if i < 3 else 44, 514 + i * 15.5, s, 11, 'start')
interlock(32, 557)
add('</svg>')

svg = '\n'.join(out) + '\n'
assert '–' not in svg and '—' not in svg
Path(__file__).with_name('rig.svg').write_text(svg, encoding='utf-8')
print(f'wrote rig.svg ({len(svg)} bytes)')
