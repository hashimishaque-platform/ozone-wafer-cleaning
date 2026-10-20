#!/usr/bin/env python3
"""Build the single-file page from template.html, model.js, rig.svg, checks.json and mechanism.json.

    python3 make_data.py                   -> checks.json and mechanism.json (from the Python package)
    python3 rig.py                         -> rig.svg (Figure 7, the test rig)
    python3 build.py                       -> index.html, a complete page for GitHub Pages
    python3 build.py --artifact OUT URL    -> page body only, with the home link pointing to URL
"""
import html
import json
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent

# ---- search engines and link previews (full page only) ----
META = {
    'repo': 'ozone-wafer-cleaning',
    'name': 'Ozone wafer cleaning',
    'title': 'Ozonated water resist strip calculator | Hashim Ishaque',
    'headline': 'Ozonated water for photoresist removal: a process model',
    'description': ('Ozonated water (DIO3) for photoresist removal on a spinning wafer: ozone solubility and decay, '
                    'film transport, strip rate, uniformity and ozone budget, from published data.'),
    'image_alt': 'Strip rate across a 300 mm wafer and the fate of the dissolved ozone in a single-wafer process',
    'keywords': ('ozonated water, DIO3, photoresist strip, ozone solubility, ozone decomposition, wet cleaning, '
                 'single-wafer, spin processor, mass transfer, semiconductor cleaning, test rig, design of experiments'),
    'languages': ['Python', 'JavaScript'],
    'about': [
        ('Ozone', 'https://en.wikipedia.org/wiki/Ozone'),
        ('Photoresist', 'https://en.wikipedia.org/wiki/Photoresist'),
        ('Wafer cleaning', 'https://en.wikipedia.org/wiki/Wafer_cleaning'),
        ('Mass transfer', 'https://en.wikipedia.org/wiki/Mass_transfer'),
    ],
}
SITE = 'https://hashimishaque.com'
PERSON = {
    '@type': 'Person', '@id': SITE + '/#person', 'name': 'Hashim Ishaque', 'url': SITE + '/',
    'sameAs': ['https://www.linkedin.com/in/hashimishaque/', 'https://github.com/hashimishaque-platform'],
}
WEBSITE = {'@type': 'WebSite', '@id': SITE + '/#website', 'url': SITE + '/', 'name': 'Hashim Ishaque'}
MIT = 'https://opensource.org/licenses/MIT'
EXTRA = ()


def head(meta, extra=()):
    """Title, description, canonical address, icons, link preview and structured data (schema.org)."""
    url = f"{SITE}/{meta['repo']}/"
    image = url + 'social.png'
    page = {
        '@type': 'WebPage', '@id': url, 'url': url, 'name': meta['headline'], 'description': meta['description'],
        'inLanguage': 'en', 'isPartOf': {'@id': WEBSITE['@id']}, 'author': {'@id': PERSON['@id']},
        'primaryImageOfPage': {'@type': 'ImageObject', 'url': image, 'width': 1200, 'height': 630},
        'about': [{'@type': 'Thing', 'name': n, 'sameAs': u} for n, u in meta['about']],
        'keywords': meta['keywords'], 'breadcrumb': {'@id': url + '#breadcrumb'},
    }
    code = {
        '@type': 'SoftwareSourceCode', '@id': url + '#code', 'name': meta['name'], 'description': meta['description'],
        'url': url, 'codeRepository': f"https://github.com/hashimishaque-platform/{meta['repo']}",
        'programmingLanguage': meta['languages'], 'runtimePlatform': 'Web browser', 'license': MIT,
        'author': {'@id': PERSON['@id']},
    }
    crumbs = {'@type': 'BreadcrumbList', '@id': url + '#breadcrumb', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Hashim Ishaque', 'item': SITE + '/'},
        {'@type': 'ListItem', 'position': 2, 'name': meta['name'], 'item': url}]}
    graph = [page, code, crumbs, WEBSITE, PERSON, *extra]
    ld = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, indent=1).replace('</', '<\\/')
    e = lambda s: html.escape(s, quote=True)
    return '\n'.join([
        f"<title>{e(meta['title'])}</title>",
        f'<meta name="description" content="{e(meta["description"])}">',
        '<meta name="author" content="Hashim Ishaque">',
        f'<link rel="canonical" href="{url}">',
        '<link rel="icon" href="/favicon.ico" sizes="32x32">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Hashim Ishaque">',
        f'<meta property="og:title" content="{e(meta["headline"])}">',
        f'<meta property="og:description" content="{e(meta["description"])}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{image}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{e(meta["image_alt"])}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<script type="application/ld+json">\n{ld}\n</script>',
    ])


def module(name):
    src = (here / name).read_text(encoding='utf-8')
    # the CommonJS export block is only for Node
    stripped = re.sub(r"\nif \(typeof module !== 'undefined'\) \{.*?\n\}\n", "\n", src, flags=re.S)
    assert stripped != src, f'no export block found in {name}'
    return stripped.strip()


def build(home, full):
    page = (here / 'template.html').read_text(encoding='utf-8')
    assert page.count('<!--RIG-->') == 1, 'Figure 7 placeholder missing'
    page = page.replace('<!--RIG-->', (here / 'rig.svg').read_text(encoding='utf-8').strip())
    page = page.replace('/*MODEL*/', module('model.js'))
    checks = json.loads((here / 'checks.json').read_text(encoding='utf-8'))
    mech = json.loads((here / 'mechanism.json').read_text(encoding='utf-8'))
    page = page.replace('/*CHECKS*/', json.dumps(checks, ensure_ascii=False))
    page = page.replace('/*MECH*/', json.dumps(mech))
    if not home.startswith('http'):
        page = page.replace('href="/*HOME*/" target="_blank" rel="noopener"', f'href="{home}"')
    page = page.replace('/*HOME*/', home)
    left = re.findall(r'/\*[A-Z]+\*/', page)
    assert not left, f'placeholders left: {left}'
    for ch in ('\u2013', '\u2014'):
        assert ch not in page, f'dash {ch!r} found'
    if full:
        page = re.sub(r'<title>.*?</title>\n', '', page, count=1)
        i = page.index('</style>') + len('</style>')
        page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                + head(META, EXTRA) + '\n'
                + page[:i].strip() + '\n</head>\n<body>\n' + page[i:].strip() + '\n</body>\n</html>\n')
        for ch in ('\u2013', '\u2014'):
            assert ch not in page, f'dash {ch!r} found'
    return page


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--artifact':
        out, home, full = Path(sys.argv[2]), sys.argv[3], False
    else:
        out, home, full = here / 'index.html', '/', True
    page = build(home, full)
    out.write_text(page, encoding='utf-8')
    print(f'wrote {out} ({len(page)} bytes)')
