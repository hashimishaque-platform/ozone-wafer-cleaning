#!/usr/bin/env python3
"""Put the 3D page of the process module together.

    python3 simulation/build.py    -> simulation/index.html, one file to open in a browser

The page is template.html with two scripts set in: the simulation core (the property and decay
functions from the top of ../model.js, then core.js) and the 3D scene and panels (app.js).
"""
from pathlib import Path

here = Path(__file__).resolve().parent
PROPS_END = '// ---------------------------------------------------------------- pH of water'   # model.js up to here


def props():
    text = (here.parent / 'model.js').read_text(encoding='utf-8')
    cut = text.index(PROPS_END)
    return text[:cut]


def main():
    page = (here / 'template.html').read_text(encoding='utf-8')
    core = props() + '\n' + (here / 'core.js').read_text(encoding='utf-8')
    app = (here / 'app.js').read_text(encoding='utf-8')
    assert page.count('/*CORE*/') == 1 and page.count('/*APP*/') == 1
    body = page.replace('/*CORE*/', core).replace('/*APP*/', app)
    for dash in ('—', '–'):
        assert dash not in body, 'no em or en dashes on the page'
    head = ('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
    (here / 'index.html').write_text(head + body, encoding='utf-8')
    print('wrote simulation/index.html,', len(body.encode('utf-8')), 'bytes')


if __name__ == '__main__':
    main()
