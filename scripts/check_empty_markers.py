#!/usr/bin/env python3
"""Fail if any partial marker in the given HTML files has been left populated.

dist/ is gitignored and self-contained; source files must always be
committed with empty <!-- partial:x --><!-- /partial:x --> markers.
"""
import re
import sys

DEFAULT_PAGES = ['index.html', 'groups.html', 'bracket.html', 'scorers.html']


def main():
    pages = sys.argv[1:] or DEFAULT_PAGES
    stale = False
    for page in pages:
        with open(page, encoding='utf-8') as f:
            html = f.read()
        for m in re.finditer(r'<!-- partial:(\w+) -->(.*?)<!-- /partial:\1 -->', html, re.S):
            if m.group(2).strip():
                print(f'✗ {page} has populated marker "{m.group(1)}" — run python3 build.py --strip before committing')
                stale = True
    if stale:
        sys.exit(1)
    print('✓ all partial markers are empty')


if __name__ == '__main__':
    main()
