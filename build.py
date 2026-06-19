#!/usr/bin/env python3
import os
import re
import shutil
import sys

DIST = 'dist'
PAGES = [
    { 'file': 'index.html',   'nav': 'schedule', 'canonical': './',            'title': 'World Cup 2026 Schedule - Live Scores & Local Times',  'description': 'All 104 matches with live scores, standings and bracket. Times in your timezone. Free, no ads.'           },
    { 'file': 'groups.html',  'nav': 'groups',   'canonical': 'groups.html',   'title': 'World Cup 2026 Group Standings - Live & Updated',       'description': 'Live standings updated as matches are played. All 12 groups with FIFA tiebreaker logic.'                  },
    { 'file': 'bracket.html', 'nav': 'knockout', 'canonical': 'bracket.html',  'title': 'World Cup 2026 Knockout Bracket',                       'description': 'Full bracket from Round of 32 to the Final. Match times in your local timezone.'                          },
    { 'file': 'scorers.html', 'nav': 'scorers',  'canonical': 'scorers.html',  'title': 'World Cup 2026 Top Scorers - Golden Boot Race',         'description': 'FIFA World Cup 2026 Golden Boot race - top scorers updated live throughout the tournament.'                },
]

STATIC_FILES = ['styles.css', 'manifest.json', 'favicon.ico', 'sw.js', 'sitemap.xml', 'data.json', 'scorers.json']


def read_partial(name):
    with open(os.path.join('_partials', name), encoding='utf-8') as f:
        return f.read().rstrip()


def inject(html, partial_name, content):
    pattern = rf'(<!-- partial:{partial_name} -->)[\s\S]*?(<!-- /partial:{partial_name} -->)'
    if not re.search(pattern, html):
        return html
    return re.sub(pattern, rf'\g<1>\n{content}\n\2', html)


def strip_markers(html):
    return re.sub(
        r'<!-- partial:([\w-]+) -->[\s\S]*?<!-- /partial:([\w-]+) -->',
        r'<!-- partial:\1 -->\n<!-- /partial:\2 -->',
        html,
    )


def copy_dir(src, dest):
    os.makedirs(dest, exist_ok=True)
    for entry in os.scandir(src):
        s, d = entry.path, os.path.join(dest, entry.name)
        if entry.is_dir():
            copy_dir(s, d)
        else:
            shutil.copy2(s, d)


def build_page(page, check=False):
    file, nav, canonical, title, description = (
        page['file'], page['nav'], page['canonical'], page['title'], page['description']
    )
    with open(file, encoding='utf-8') as f:
        html = f.read()

    head = read_partial('head.html') \
        .replace('{{PAGE_TITLE}}', title) \
        .replace('{{PAGE_DESCRIPTION}}', description) \
        .replace('{{PAGE_CANONICAL}}', canonical)
    html = inject(html, 'head', head)

    html = inject(html, 'langs', read_partial('langs.html'))

    nav_html = read_partial('nav.html').replace(
        f'class="nav-btn" id="nav-{nav}"',
        f'class="nav-btn active" id="nav-{nav}"',
    )
    html = inject(html, 'nav', nav_html)

    html = inject(html, 'tz-options', read_partial('tz-options.html'))
    html = inject(html, 'common-js', read_partial('common.js'))
    html = inject(html, 'footer', read_partial('footer.html'))
    html = inject(html, 'jsonld', read_partial('jsonld.html'))

    dest = os.path.join(DIST, file)
    if check:
        try:
            with open(dest, encoding='utf-8') as f:
                built = f.read()
        except FileNotFoundError:
            built = None
        if html != built:
            print(f'✗ {file} is stale — run python3 build.py')
            return False
        print(f'✓ {file}')
        return True
    else:
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'✓ {file}')
        return True


def main():
    args = sys.argv[1:]

    if '--strip' in args:
        for page in PAGES:
            with open(page['file'], encoding='utf-8') as f:
                html = f.read()
            html = strip_markers(html)
            with open(page['file'], 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"stripped {page['file']}")
        print('Strip complete.')
        sys.exit(0)

    check = '--check' in args

    if not check:
        os.makedirs(DIST, exist_ok=True)

    stale = False
    for page in PAGES:
        if not build_page(page, check=check):
            stale = True

    if check and stale:
        sys.exit(1)

    if not check:
        for f in STATIC_FILES:
            if os.path.exists(f):
                shutil.copy2(f, os.path.join(DIST, f))
        if os.path.exists('icons'):
            copy_dir('icons', os.path.join(DIST, 'icons'))

    print('Build complete.')


if __name__ == '__main__':
    main()
