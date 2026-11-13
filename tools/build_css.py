#!/usr/bin/env python3
"""Baut src/assets/css/site.css aus dem CSS der alten Drupal-Seite.

Schritte:
 1. Alle CSS-Aggregate aus dem Crawl zu einer Vereinigung zusammenfuehren
    (Drupal lieferte pro Seite ein eigenes, 1 bis 1.5 MB grosses Aggregat aus).
 2. Exakt doppelte Regeln entfernen. Es bleibt jeweils das letzte Vorkommen,
    damit die Kaskade unveraendert bleibt.
 3. URLs auf /assets/... umschreiben, Google-Fonts-@import entfernen (steht im <head>).
 4. Mit PurgeCSS alles entfernen, was in dist/ und site.js nicht vorkommt.
 5. src/assets/css/custom.css anhaengen.

Aufruf: python3 build.py && python3 tools/build_css.py && python3 build.py
Braucht Node (npx purgecss). Nur noetig, wenn neue Klassen aus dem alten Theme gebraucht werden.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
WORK = os.path.join(ROOT, '_crawl', 'css')
os.makedirs(WORK, exist_ok=True)

dump = json.load(open(os.path.join(ROOT, '_crawl', 'einstain-crawl-pages.json')))
css_files = {k: v for k, v in dump['text'].items() if '.css' in k}
manifest = json.load(open(os.path.join(SRC, 'assets', 'manifest.json')))
ASSET_BY_PATH = {}
for local, url in manifest.items():
    ASSET_BY_PATH[re.sub(r'^https?://[^/]+', '', url).split('?')[0]] = '/' + local


def split_blocks(css):
    """CSS in Top-Level-Bloecke zerlegen (Regeln und @-Regeln), Kommentare entfernen."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    blocks, depth, start, i, n = [], 0, 0, 0, len(css)
    quote = None
    paren = 0
    while i < n:
        ch = css[i]
        if quote:
            if ch == '\\':
                i += 1
            elif ch == quote:
                quote = None
        elif ch in '"\'':
            quote = ch
        elif ch == '(':
            paren += 1
        elif ch == ')':
            paren = max(0, paren - 1)
        elif paren:
            pass
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                blocks.append(css[start:i + 1].strip())
                start = i + 1
        elif ch == ';' and depth == 0:
            blocks.append(css[start:i + 1].strip())
            start = i + 1
        i += 1
    return [b for b in blocks if b]


def dedupe_keep_last(blocks):
    seen, out = set(), []
    for b in reversed(blocks):
        if b in seen:
            continue
        seen.add(b)
        out.append(b)
    return list(reversed(out))


def dedupe_inside(block):
    """Auch innerhalb von @media/@supports doppelte Regeln entfernen."""
    m = re.match(r'(@(?:media|supports)[^{]*)\{(.*)\}$', block, flags=re.S)
    if not m:
        return block
    inner = dedupe_keep_last(split_blocks(m.group(2)))
    return '%s{%s}' % (m.group(1), ''.join(inner))


ordered = sorted(css_files.items(), key=lambda kv: -len(kv[1]))
blocks = []
for _name, text in reversed(ordered):      # groesstes Aggregat zuletzt: seine Reihenfolge gewinnt
    blocks.extend(split_blocks(text))
before = len(blocks)
blocks = dedupe_keep_last([dedupe_inside(b) for b in blocks])
blocks = [b for b in blocks if not b.startswith('@import') and '/modules/contrib/ai/' not in b and '/core/misc/' not in b]


def fix_url(m, base='/sites/default/files/css/'):
    raw = m.group(1).strip('\'"')
    if raw.startswith('data:') or raw.startswith('http'):
        return m.group(0)
    path = raw.split('?')[0].split('#')[0]
    if not path.startswith('/'):
        path = os.path.normpath(os.path.join(base, path))
    if path in ASSET_BY_PATH:
        return 'url(%s)' % ASSET_BY_PATH[path]
    return m.group(0)


css = '\n'.join(blocks)
css = re.sub(r'url\(([^)]+)\)', fix_url, css)
# Schriften: nur woff2 ist lokal vorhanden, ttf-Fallback entfernen
css = re.sub(r',\s*url\([^)]*\.ttf[^)]*\)\s*format\(["\']truetype["\']\)', '', css)
left = sorted(set(u for u in re.findall(r'url\(([^)]+)\)', css) if not u.strip('\'"').startswith(('data:', '/assets/', 'http'))))
union = os.path.join(WORK, 'theme-union.css')
open(union, 'w', encoding='utf-8').write(css)
print('Vereinigung: %d -> %d Bloecke, %d KB' % (before, len(blocks), len(css) // 1024))
if left:
    print('Nicht umgeschriebene URLs:', left[:12])

if '--no-purge' in sys.argv:
    sys.exit(0)

config = os.path.join(WORK, 'purgecss.config.cjs')
open(config, 'w').write('''module.exports = {
  content: [%s, %s],
  css: [%s],
  output: %s,
  fontFace: true, keyframes: true, variables: false,
  safelist: {
    standard: ['js', 'navigation-open', 'show', 'collapse', 'collapsing', 'collapsed', 'alert', 'alert-success',
               'alert-danger', 'active', 'is-active', 'visually-hidden', 'focusable'],
    deep: [/^navigation-open$/]
  }
};
''' % (json.dumps(os.path.join(ROOT, 'dist', '**', '*.html')), json.dumps(os.path.join(SRC, 'assets', 'js', 'site.js')),
       json.dumps(union), json.dumps(os.path.join(WORK, 'purged'))))
os.makedirs(os.path.join(WORK, 'purged'), exist_ok=True)
tools = os.environ.get('EINSTAIN_NODE_TOOLS', os.path.expanduser('~/.einstain-node-tools'))
os.makedirs(tools, exist_ok=True)
if not os.path.isdir(os.path.join(tools, 'node_modules', 'purgecss')):
    subprocess.check_call(['npm', 'install', '--silent', '--prefix', tools, 'purgecss@6'])
subprocess.check_call([os.path.join(tools, 'node_modules', '.bin', 'purgecss'), '--config', config])
purged = open(os.path.join(WORK, 'purged', 'theme-union.css'), encoding='utf-8').read()
open(os.path.join(SRC, 'assets', 'css', 'theme.css'), 'w', encoding='utf-8').write(purged)
custom = open(os.path.join(SRC, 'assets', 'css', 'custom.css'), encoding='utf-8').read()
site = '/* einstAIn: theme.css (uebernommenes Theme, bereinigt) + custom.css. Erzeugt von tools/build_css.py */\n' + purged + '\n' + custom
open(os.path.join(SRC, 'assets', 'css', 'site.css'), 'w', encoding='utf-8').write(site)
print('site.css: %d KB (theme %d KB)' % (len(site) // 1024, len(purged) // 1024))
