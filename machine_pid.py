"""Draws the piping and instruments of the closed-loop machine as machine_pid.svg. The page inlines it.

    python3 machine_pid.py      -> machine_pid.svg

Same symbols as the test rig (rig.py, ISA-5.1). Numbers: 5xx gas and oxygen loop, 6xx water,
7xx process module. The four loops of the design are labelled: the oxygen loop, the ozone
cascade (contactor off-gas to the cover), heat recovery and water reclaim.
"""
from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1080, 700
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
    end = ' marker-end="url(#arm)"' if arrow else ''
    add(f'<path d="{d}" {STYLE[kind]}{end}/>')


def hop(x, y, kind='gas'):
    """A vertical line hopping over a horizontal one at (x, y)."""
    add(f'<rect x="{x - 4}" y="{y - 7}" width="8" height="14" fill="#ffffff"/>')
    add(f'<path d="M{x},{y + 7} A7,7 0 0 1 {x},{y - 7}" {STYLE[kind]}/>')


def box(x, y, w, h, labels=(), size=12, dashed=False, rx=0, fill='#ffffff'):
    dash = ' stroke-dasharray="4 3"' if dashed else ''
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="#000000" stroke-width="1.2"{dash}/>')
    n = len(labels)
    for i, s in enumerate(labels):
        text(x + w / 2, y + h / 2 + 4 + (i - (n - 1) / 2) * (size + 2), s, size)


def bubble(cx, cy, tag, num, tap=None):
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


def zigzag(x0, x1, cy, amp=9):
    n = 6
    pts = [(x0, cy)] + [(x0 + (x1 - x0) * (i + 0.5) / n, cy + (amp if i % 2 else -amp)) for i in range(n)] + [(x1, cy)]
    add('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts) + f'" {STYLE["thin"]}/>')


def cylinder(x, y, w, h, label):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" fill="#ffffff" stroke="#000000" stroke-width="1.2"/>')
    text(x + w / 2, y + h / 2 + 4, label, 12)


def loop_label(x, y, s, anchor='start'):
    text(x, y, s, 11.5, anchor, ' font-style="italic" fill="#0000cc"')


add(f'<svg id="fig13" class="plot wide" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
    f'aria-label="Piping and instruments of the closed-loop machine" font-family="{FONT}">')
add('<defs><marker id="arm" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" '
    'markerHeight="10" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#000000"/></marker></defs>')
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>')

# ---------------------------------------------------------------- oxygen loop (top line) and generator
line([(840, 88), (840, 30), (124, 30), (124, 69)], 'gas', arrow=True)
loop_label(300, 22, 'oxygen loop: oxygen behind the destruct is dried and returned to the generator')
valve(880, 30)
line([(840, 30), (870, 30)], 'gas')
line([(890, 30), (930, 30)], 'gas', arrow=True)
text(936, 34, 'bleed', 11, 'start')
cylinder(14, 40, 30, 62, 'O₂')
text(29, 118, 'make-up', 11)
line([(44, 70), (64, 70)], 'gas')
box(64, 60, 36, 20, ['MFC'], 10)
bubble(82, 120, 'FIC', '501', tap=(82, 80))
line([(100, 70), (226, 70)], 'gas')
add('<circle cx="124" cy="70" r="2.6" fill="#000000"/>')
add('<circle cx="160" cy="70" r="2.6" fill="#000000"/>')
cylinder(145, 170, 30, 50, 'CO₂')
line([(160, 170), (160, 136)], 'gas')
box(142, 116, 36, 20, ['MFC'], 10)
line([(160, 116), (160, 71)], 'gas', arrow=True)
bubble(205, 126, 'FIC', '502', tap=(178, 126))
box(226, 44, 110, 52, ['Ozone', 'generator'], 13)
line([(254, 116), (254, 97)], 'thin', arrow=True)
line([(310, 96), (310, 115)], 'thin', arrow=True)
text(282, 130, 'cooling water', 11)
line([(336, 70), (395, 70)], 'gas')
bubble(370, 120, 'AIT', '503', tap=(370, 70))
check_valve(405, 70)
line([(415, 70), (465, 70), (465, 199)], 'gas', arrow=True)

# ---------------------------------------------------------------- membrane contactor, cold
box(430, 200, 70, 220)
for x in (453, 465, 477):
    add(f'<line x1="{x}" y1="212" x2="{x}" y2="408" stroke="#888888" stroke-width="0.8"/>')
line([(442, 396), (442, 222)], 'thin', arrow=True)
line([(488, 222), (488, 396)], 'option', arrow=True)
text(465, 438, 'membrane', 12)
text(465, 452, 'contactor,', 12)
text(465, 466, '10 °C, CO₂ to pH 4.5', 11)
text(16, 380, 'ultrapure water', 11, 'start')
line([(16, 400), (150, 400)])
box(150, 384, 54, 32)
zigzag(156, 198, 400)
bubble(177, 350, 'TIC', '601', tap=(177, 384))
text(177, 432, 'chiller', 11)
line([(204, 400), (429, 400)], arrow=True)

# ---------------------------------------------------------------- ozone cascade: off-gas to the cover
line([(500, 400), (510, 400)], 'gas')
valve(520, 400)
bubble(520, 440, 'PIC', '506', tap=(520, 408))
line([(530, 400), (600, 400), (600, 150), (946, 150), (946, 299)], 'gas', arrow=True)
hop(600, 220)
box(690, 140, 36, 20, ['MFC'], 10)
bubble(708, 106, 'FIC', '504', tap=(708, 140))
loop_label(740, 142, 'ozone cascade: the off-gas covers the film')

# ---------------------------------------------------------------- water: contactor to the nozzle
line([(500, 220), (548, 220)])
bubble(525, 184, 'AIT', '602', tap=(525, 220))
box(548, 210, 36, 20, ['LFC'], 10)
bubble(566, 184, 'FIC', '603', tap=(566, 210))
line([(584, 220), (610, 220)])
box(610, 204, 60, 32, ['heat', 'recovery'], 10)
line([(670, 220), (690, 220)])
box(690, 206, 44, 28)
zigzag(694, 730, 220, 7)
bubble(712, 184, 'TIC', '604', tap=(712, 206))
line([(734, 220), (795, 220)])
bubble(760, 184, 'AIT', '605', tap=(760, 220))
bubble(795, 184, 'AIT', '608', tap=(795, 220))
valve(805, 220, third='down')
line([(815, 220), (936, 220), (936, 299)], arrow=True)
text(941, 290, 'coaxial', 10, 'end')

# ---------------------------------------------------------------- process module
add('<rect x="820" y="300" width="240" height="180" fill="none" stroke="#000000" stroke-width="1.2"/>')
box(872, 306, 136, 14, dashed=True)
text(940, 317, 'UV lamps (option)', 9.5)
add('<rect x="852" y="304" width="6" height="22" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
add('<rect x="1022" y="304" width="6" height="22" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
add('<rect x="845" y="326" width="190" height="12" fill="#e6eef5" stroke="#000000" stroke-width="1.1"/>')
text(940, 335.5, 'quartz cover', 9)
add('<polyline points="852,334 838,340 838,466 1042,466 1042,340 1028,334" fill="none" stroke="#000000" stroke-width="1.2"/>')
add('<rect x="850" y="344" width="180" height="3" fill="#9ab0d8"/>')
add('<rect x="850" y="347" width="180" height="4" fill="#000000"/>')
add('<line x1="900" y1="339" x2="900" y2="343" stroke="#000000" stroke-width="0.7"/>')
add('<rect x="928" y="351" width="24" height="26" fill="#ffffff" stroke="#000000" stroke-width="1.2"/>')
add('<line x1="940" y1="377" x2="940" y2="490" stroke="#000000" stroke-width="3"/>')
box(916, 490, 48, 28, ['M'], 13)
bubble(996, 504, 'SIC', '701', tap=(964, 504))
bubble(828, 278, 'ZT', '702', tap=(852, 306))
# gas out of the rim, endpoint analyser, destruct, dryer, blower
line([(1042, 380), (1072, 380), (1072, 110), (1061, 110)], 'gas', arrow=True)
bubble(1044, 240, 'AIT', '505', tap=(1072, 240))
text(1044, 270, 'O₃, CO₂', 9.5)
box(962, 88, 98, 40, ['destruct', 'heated catalyst'], 10)
line([(962, 108), (941, 108)], 'gas', arrow=True)
box(880, 88, 60, 40, ['dryer'], 11)
line([(880, 108), (853, 108)], 'gas', arrow=True)
add('<circle cx="840" cy="100" r="12" fill="#ffffff" stroke="#000000" stroke-width="1.2"/>')
add('<polygon points="834,94 846,100 834,106" fill="none" stroke="#000000" stroke-width="1"/>')
text(840, 128, 'blower', 10)

# ---------------------------------------------------------------- drain: endpoint, heat recovery, reclaim
line([(850, 466), (850, 560), (660, 560), (660, 237)], arrow=True)
bubble(880, 520, 'AIT', '606', tap=(850, 520))
add('<circle cx="805" cy="560" r="2.6" fill="#000000"/>')
line([(805, 236), (805, 560)])
line([(620, 237), (620, 600), (541, 600)], arrow=True)
loop_label(668, 584, 'heat recovery', 'start')
box(450, 584, 90, 32, ['ozone removal'], 10.5)
line([(450, 600), (395, 600)])
bubble(420, 560, 'AIT', '607', tap=(420, 600))
valve(385, 600, third='down')
line([(375, 600), (300, 600)], arrow=True)
text(296, 596, 'reclaim to the', 11, 'end')
text(296, 610, 'ultrapure water plant', 11, 'end')
line([(385, 616), (385, 640)], arrow=True)
text(392, 640, 'drain', 11, 'start')
loop_label(296, 572, 'water reclaim', 'end')
bubble(1046, 530, 'AIT', '705')
text(1046, 560, 'ambient', 10)

# ---------------------------------------------------------------- key
add('<rect x="14" y="470" width="270" height="88" fill="#ffffff" stroke="#808080" stroke-width="1"/>')
line([(26, 488), (60, 488)])
text(66, 492, 'water', 11, 'start')
line([(110, 488), (144, 488)], 'gas')
text(150, 492, 'gas', 11, 'start')
add('<rect x="186" y="481" width="30" height="14" fill="#ffffff" stroke="#000000" stroke-width="1" stroke-dasharray="4 3"/>')
text(222, 492, 'option', 11, 'start')
for i, s in enumerate(['5xx gas and oxygen, 6xx water, 7xx module.',
                       'AIT-505 and AIT-606: end point of the strip.',
                       'AIT-607: TOC and conductivity before reclaim.']):
    text(26, 512 + i * 15, s, 11, 'start')
add('</svg>')

svg = '\n'.join(out) + '\n'
assert '–' not in svg and '—' not in svg
Path(__file__).with_name('machine_pid.svg').write_text(svg, encoding='utf-8')
print(f'wrote machine_pid.svg ({len(svg)} bytes)')
