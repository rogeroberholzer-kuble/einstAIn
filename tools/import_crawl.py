#!/usr/bin/env python3
"""Einmaliger Import: Crawl von einstain.ch (_crawl/) -> saubere Quellen in src/.

Liest das ausgelieferte Drupal-HTML, entfernt Drupal-Ballast und schreibt
Seiten, Artikel, Bausteine, Templates und Assets nach src/. Danach ist src/
die Quelle der Wahrheit, dieses Skript wird im Alltag nicht mehr gebraucht.
"""
import json, os, re, base64, html, urllib.parse
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWL = os.path.join(ROOT, '_crawl')
SRC = os.path.join(ROOT, 'src')
ORIGIN = 'https://einstain.ch'

pages_dump = json.load(open(os.path.join(CRAWL, 'einstain-crawl-pages.json')))
assets_dump = json.load(open(os.path.join(CRAWL, 'einstain-crawl-assets.json')))
RAWPAGES = pages_dump['pages']
CSS_TEXT = {k: v for k, v in pages_dump['text'].items() if '.css' in k}


# ---------------------------------------------------------------- Inline-SVG-Logos -> Sprite
# Die Logos stehen im Drupal-HTML auf jeder Seite mehrfach inline (rund 65 KB pro Seite).
# Sie wandern in eine Sprite-Datei und werden per <use> eingebunden.
SPRITE = {}


def _svg_to_use(m):
    attrs, inner = m.group(1), m.group(2)
    if len(inner) < 2000:
        return m.group(0)
    vb = re.search(r'viewBox="([^"]+)"', attrs)
    w, h = re.search(r'width="(\d+)"', attrs), re.search(r'height="(\d+)"', attrs)
    sid = 'logo-%sx%s' % (w.group(1) if w else 'w', h.group(1) if h else 'h')
    body = re.sub(r'\sclip-path="url\(#[^)]+\)"', '', inner)
    body = re.sub(r'<defs>\s*(<clipPath[^>]*>\s*<rect[^>]*/>\s*</clipPath>\s*)+</defs>', '', body)
    SPRITE[sid] = '<symbol id="%s" viewBox="%s" fill="none">%s</symbol>' % (sid, vb.group(1) if vb else '', body.strip())
    return '<svg%s><use href="/assets/img/logos.svg#%s"></use></svg>' % (attrs, sid)


for _k in list(RAWPAGES):
    RAWPAGES[_k] = re.sub(r'<svg\b([^>]*)>(.*?)</svg>', _svg_to_use, RAWPAGES[_k], flags=re.S)
os.makedirs(os.path.join(SRC, 'assets', 'img'), exist_ok=True)
with open(os.path.join(SRC, 'assets', 'img', 'logos.svg'), 'w', encoding='utf-8') as _f:
    _f.write('<svg xmlns="http://www.w3.org/2000/svg">\n%s\n</svg>\n' % '\n'.join(SPRITE[k] for k in sorted(SPRITE)))
print('SVG-Sprite:', sorted(SPRITE), 'url(# verbleibend:', sum('url(#' in v for v in SPRITE.values()))


# ---------------------------------------------------------------- assets
def slug_name(name):
    name = urllib.parse.unquote(name).lower()
    name = re.sub(r'\.(png|jpe?g)\.webp$', '.webp', name)
    name = re.sub(r'[^a-z0-9._-]+', '-', name)
    name = re.sub(r'-{2,}', '-', name).strip('-')
    return re.sub(r'-+\.', '.', name)


ASSET_MAP = {}      # Originalpfad (ohne Query) -> /assets/...
MANIFEST = {}       # assets/... -> Original-URL (mit Query)
used = {}
for key, info in assets_dump.items():
    p = urllib.parse.unquote(key.split('?')[0])
    name = os.path.basename(p)
    if p.startswith('/sites/default/files/styles/'):
        sub = 'img/' + p.split('/')[5]
    elif p.startswith('/sites/default/files/'):
        sub = 'img/icons' if name.endswith('.svg') else 'img'
    elif '/build/fonts/' in p:
        if not name.endswith('.woff2'):
            continue
        sub = 'fonts'
    elif '/einstain/build/assets/' in p or '/einstain/src/assets/' in p:
        sub = 'img/theme'
    elif p.startswith('/media/'):
        m = re.search(r'filename="([^"]+)"', info.get('cd') or '')
        name = m.group(1) if m else 'media-%s.pdf' % p.split('/')[-1]
        sub = 'docs'
    else:
        continue
    local = 'assets/%s/%s' % (sub, slug_name(name))
    if local in used and used[local] != key.split('?')[0]:
        stem, ext = os.path.splitext(local)
        local = '%s-%d%s' % (stem, len(used), ext)
    used[local] = key.split('?')[0]
    ASSET_MAP[key.split('?')[0]] = '/' + local
    ASSET_MAP[p] = '/' + local
    MANIFEST[local] = ORIGIN + key
    out = os.path.join(SRC, local)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(base64.b64decode(info['b64']))


def map_url(u):
    """Asset-URL auf lokalen Pfad abbilden, sonst unveraendert."""
    if not u:
        return u
    bare = u[len(ORIGIN):] if u.startswith(ORIGIN + '/sites') or u.startswith(ORIGIN + '/media') else u
    path = bare.split('?')[0]
    if path in ASSET_MAP:
        return ASSET_MAP[path]
    return ASSET_MAP.get(urllib.parse.unquote(path), u)


# ---------------------------------------------------------------- classes
CSS_ALL = '\n'.join(CSS_TEXT.values())
CSS_CLASSES = set(re.findall(r'\.(-?[_a-zA-Z][\w-]*)', re.sub(r'url\([^)]*\)', '', CSS_ALL)))
JS_KEEP = {'scroll-appear', 'scroll-appear-inner', 'field--name-field-link', 'page-menu-btn',
           'blog-page', 'view', 'view-content', 'views-row', 'load-more-btn-wrapper',
           'blog-load-more-btn', 'accordion-collapse', 'collapse', 'collapsed', 'show'}
KEEP = CSS_CLASSES | JS_KEEP
DROP_ATTRS = {'data-once', 'data-component-id', 'data-history-node-id', 'data-off-canvas-main-canvas',
              'hreflang', 'dir', 'typeof', 'property', 'about', 'data-nosnippet', 'data-pager-hidden',
              'accept-charset', 'data-quickedit-field-id', 'data-entity-type', 'data-entity-uuid',
              'data-align', 'data-webform-required-error', 'aria-required'}
HONEYPOT = ('<div class="visually-hidden" aria-hidden="true"><label>Bitte leer lassen '
            '<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
            '<div class="form-status" role="status" aria-live="polite"></div>')


def clean(node):
    """Drupal-Ballast aus einem Teilbaum entfernen (in place)."""
    for c in node.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for el in node.select('[data-drupal-messages-fallback], script, .contextual, .captcha'):
        el.decompose()
    for form in node.select('form'):
        for inp in form.select('input[type=hidden]'):
            inp.decompose()
        form.attrs = {'class': form.get('class', []), 'action': '/_db/main/contact_messages',
                      'method': 'post', 'data-contact-form': ''}
        actions = form.select_one('.form-actions')
        if actions:
            actions.insert_before(BeautifulSoup(HONEYPOT, 'html.parser'))
    for el in [node] + node.find_all(True):
        if not isinstance(el, Tag):
            continue
        for a in list(el.attrs):
            if a in DROP_ATTRS or a.startswith('data-drupal'):
                del el.attrs[a]
        if el.has_attr('class'):
            cls = [c for c in el['class'] if c in KEEP and not c.startswith('js-view-dom-id')]
            if cls:
                el['class'] = cls
            else:
                del el['class']
        for a in ('src', 'href', 'poster'):
            if el.has_attr(a):
                el[a] = map_url(el[a])
        if el.has_attr('srcset'):
            parts = []
            for part in el['srcset'].split(','):
                bits = part.strip().split(' ')
                bits[0] = map_url(bits[0])
                parts.append(' '.join(bits))
            el['srcset'] = ', '.join(parts)
    # leere Wrapper-Ketten aufloesen: <div><div class=x>..</div></div> -> <div class=x>..</div>
    changed = True
    while changed:
        changed = False
        for el in node.find_all('div'):
            if el.attrs or el.parent is None:
                continue
            kids = [c for c in el.children if isinstance(c, Tag)]
            text = ''.join(c for c in el.children if isinstance(c, NavigableString)).strip()
            sibs = [c for c in el.parent.children if isinstance(c, Tag)]
            ptext = ''.join(c for c in el.parent.children if isinstance(c, NavigableString)).strip()
            if len(kids) == 1 and not text and len(sibs) == 1 and not ptext:
                el.unwrap()
                changed = True
            elif not kids and not text:
                el.decompose()
                changed = True
    return node


def ser(node, inner=False):
    s = node.decode_contents(formatter='minimal') if inner else node.decode(formatter='minimal')
    return re.sub(r'\n\s*\n+', '\n', s).strip()


def soup_of(path):
    return BeautifulSoup(RAWPAGES[path], 'lxml')


def write(rel, text):
    out = os.path.join(SRC, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text.rstrip() + '\n')


def with_meta(meta, body):
    return '<!--meta\n%s\n-->\n%s' % (json.dumps(meta, ensure_ascii=False, indent=2), body)


def head_meta(s):
    d = s.find('meta', attrs={'name': 'description'})
    title = s.title.get_text().strip()
    return re.sub(r'\s*\|\s*einstAIn$', '', title), (d['content'].strip() if d else '')


def nav_state(s):
    li = s.select_one('.page-menu-frame .nav-item.active')
    return li.a['href'] if li else ''


def body_classes(s):
    return [c for c in s.body.get('class', []) if c in CSS_CLASSES]


def cleaned_main(s, slots=()):
    """<main> kopieren, Slots vor dem Bereinigen markieren (Klassen koennen wegfallen), dann bereinigen."""
    m = BeautifulSoup(str(s.find('main')), 'html.parser')
    for selector, name in slots:
        el = m.select_one(selector)
        if el is not None:
            el['data-slot'] = name
    for pager in m.select('.pager .pagination-wrapper'):
        pager.decompose()
    return clean(m).find('main')


def slot(node, name):
    return node.select_one('[data-slot="%s"]' % name)


def strip_slots(node):
    for el in node.select('[data-slot]'):
        del el['data-slot']
    return node


ARTICLE_SLOTS = (('article.blog--post .image-wrapper img', 'img'), ('.content-links__categories', 'cats'),
                 ('article.blog--post .node__content', 'body'), ('.block--related-posts .view-content', 'related'))


# ---------------------------------------------------------------- partials
home = soup_of('/de')
nav = [{'label': a.get_text(strip=True), 'href': a['href']} for a in home.select('.page-menu-frame ul.nav a')]
nav_ul_class = ' '.join(c for c in home.select_one('.page-menu-frame ul.nav').get('class', []) if c in KEEP)
wrapper_classes = [' '.join(c for c in e.get('class', []) if c in KEEP)
                   for e in (home.select_one('.dialog-off-canvas-main-canvas'), home.select_one('.main-page-wrapper'))]
hdr = BeautifulSoup('<div></div>', 'html.parser').div
for sel in ('.page-menu-frame', '.page-frame'):
    hdr.append(clean(BeautifulSoup(str(home.select_one(sel)), 'html.parser')))
for ul in hdr.select('ul.nav'):
    ul.replace_with('{{nav}}')
write('partials/header.html', ser(hdr, inner=True))
write('partials/footer.html', ser(clean(BeautifulSoup(str(home.select_one('footer.page__footer')), 'html.parser'))))


# ---------------------------------------------------------------- teaser + articles
def share_enc(t):
    return urllib.parse.quote(t, safe='')


def teaser_key(art):
    return art.select_one('h2 a')['href'].rsplit('/', 1)[-1]


ARTICLE_PATHS = sorted(p for p in RAWPAGES if re.match(r'^/de/blog/(?!category)[^/?]+$', p))
all_soups = {p: soup_of(p) for p in RAWPAGES}
teaser_occ = {}
for p, s in all_soups.items():
    main = s.find('main')
    if not main:
        continue
    for art in main.select('article.blog--teaser'):
        t = clean(BeautifulSoup(str(art), 'html.parser')).find('article')
        teaser_occ.setdefault(teaser_key(art), {})[ser(t)] = p

articles = {}
for p in ARTICLE_PATHS:
    s = all_soups[p]
    slug = p.rsplit('/', 1)[-1]
    title, desc = head_meta(s)
    main = cleaned_main(s, ARTICLE_SLOTS)
    img = slot(main, 'img')
    if img is not None:
        img = BeautifulSoup(str(img), 'html.parser').find('img')
        del img['data-slot']
    cats = [{'name': a.get_text(strip=True), 'href': a['href']} for a in slot(main, 'cats').select('a')]
    body = slot(main, 'body')
    related = [teaser_key(a) for a in s.find('main').select('.block--related-posts article.blog--teaser')]
    articles[slug] = {'slug': slug, 'title': main.find('h1').get_text(strip=True), 'description': desc,
                      'image_html': ser(img) if img else '', 'teaser_image_html': '',
                      'categories': cats, 'related': related,
                      'body_classes': body_classes(s), 'nav': nav_state(s),
                      '_main': main, '_body': ser(body, inner=True), '_head_title': title}


def templatize(text, art):
    url = '/de/blog/' + art['slug']
    text = text.replace(ORIGIN + url, '{{abs_url}}').replace(url, '{{url}}')
    text = text.replace(share_enc(art['title']), '{{title_enc}}')
    text = text.replace(html.escape(art['title'], quote=True), '{{title_attr}}')
    text = text.replace(html.escape(art['title'], quote=False), '{{title}}')
    return text


def fill(tpl, art):
    return (tpl.replace('{{abs_url}}', ORIGIN + '/de/blog/' + art['slug'])
            .replace('{{url}}', '/de/blog/' + art['slug'])
            .replace('{{title_enc}}', share_enc(art['title']))
            .replace('{{title_attr}}', html.escape(art['title'], quote=True))
            .replace('{{title}}', html.escape(art['title'], quote=False)))


for slug, occ in teaser_occ.items():
    art = articles.get(slug)
    if not art:
        print('WARN Teaser ohne Artikel:', slug)
        continue
    art['_teaser_variants'] = list(occ)
    timg = BeautifulSoup(art['_teaser_variants'][0], 'html.parser').select_one('.image-wrapper img')
    art['teaser_image_html'] = ser(timg) if timg else ''

ex = next(a for a in articles.values() if a['related'] and a['image_html'] and a['categories'] and a.get('_teaser_variants'))
print('Exemplar:', ex['slug'])
tt = BeautifulSoup(ex['_teaser_variants'][0], 'html.parser')
tt.select_one('.image-wrapper img').replace_with('{{img}}')
TEASER_TPL = templatize(ser(tt), ex)
write('templates/teaser.html', TEASER_TPL)


def render_teaser(art):
    return fill(TEASER_TPL.replace('{{img}}', art['teaser_image_html']), art)


def first_diff(a, b):
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return '\n   raw: %s\n   tpl: %s' % (a[max(0, i - 90):i + 150].replace('\n', ' '), b[max(0, i - 90):i + 150].replace('\n', ' '))


bad = 0
for slug, art in articles.items():
    for v in art.get('_teaser_variants', []):
        if v != render_teaser(art):
            bad += 1
            if bad <= 3:
                print('TEASER DIFF', slug, first_diff(v, render_teaser(art)))
print('Teaser geprueft. Abweichungen:', bad, '| Artikel ohne Teaser:',
      [s for s, a in articles.items() if '_teaser_variants' not in a])

exm = BeautifulSoup(str(ex['_main']), 'html.parser').find('main')
slot(exm, 'img').replace_with('{{img}}')
cw = slot(exm, 'cats')
cat_first = cw.find('a')
cat_item = cat_first.parent if cat_first.parent is not cw else cat_first
CAT_ITEM = ser(cat_item).replace(cat_first['href'], '{{href}}').replace(html.escape(cat_first.get_text(strip=True)), '{{name}}')
cat_list = cat_item.parent
cat_list.clear()
cat_list.append('{{items}}')
CAT_WRAP = ser(cw, inner=True) if cat_list is not cw else '{{items}}'
cw.clear()
cw.append('{{categories}}')
b = slot(exm, 'body')
b.clear()
b.append('{{body}}')
rel = slot(exm, 'related')
row = rel.find(True, recursive=False)
ROW_OPEN = '<div class="%s">' % ' '.join(row.get('class', [])) if row.name == 'div' and row.get('class') else ''
rel.clear()
rel.append('{{related}}')
# Der Related-Block ist optional: Artikel ohne verwandte Beitraege zeigen ihn nicht.
rel_block = rel
while rel_block.parent is not None and len(rel_block.parent.select('article')) == 0:
    rel_block = rel_block.parent
rel_block.insert_before(Comment('related-start'))
rel_block.insert_after(Comment('related-end'))
ARTICLE_TPL = templatize(ser(strip_slots(exm), inner=True), ex)
write('templates/article.html', ARTICLE_TPL)
write('templates/category-item.html', CAT_ITEM)
write('templates/category-list.html', CAT_WRAP)


def rows(slugs):
    out = []
    for r in slugs:
        if r in articles:
            t = render_teaser(articles[r])
            out.append(ROW_OPEN + t + '</div>' if ROW_OPEN else t)
    return '\n'.join(out)


def render_article(art):
    cats = ''.join(CAT_ITEM.replace('{{href}}', c['href']).replace('{{name}}', html.escape(c['name'])) for c in art['categories'])
    cats = CAT_WRAP.replace('{{items}}', cats) if cats else ''
    tpl = ARTICLE_TPL
    if not art['related']:
        tpl = re.sub(r'<!--related-start-->.*?<!--related-end-->', '', tpl, flags=re.S)
    tpl = tpl.replace('<!--related-start-->', '').replace('<!--related-end-->', '')
    return fill(tpl.replace('{{img}}', art['image_html']).replace('{{categories}}', cats)
                .replace('{{related}}', rows(art['related'])), art).replace('{{body}}', art['_body'])


def norm(sx):
    return re.sub(r'>\s+', '>', re.sub(r'\s+<', '<', re.sub(r'\s+', ' ', sx))).strip()


bad = 0
for slug, art in articles.items():
    raw, mine = norm(ser(strip_slots(art['_main']), inner=True)), norm(render_article(art))
    if raw != mine:
        bad += 1
        if bad <= 4:
            print('ARTICLE DIFF', slug, first_diff(raw, mine))
print('Artikel geprueft:', len(articles), 'Abweichungen:', bad)

for slug, art in articles.items():
    meta = {k: v for k, v in art.items() if not k.startswith('_')}
    if art['_head_title'] != art['title']:
        meta['head_title'] = art['_head_title']
    write('articles/%s.html' % slug, with_meta(meta, art['_body']))


# ---------------------------------------------------------------- Blog-Daten
def slugs_in(sp, selector):
    return [teaser_key(a) for a in sp.select(selector)]


def paged(base):
    out = []
    keys = [base] + sorted((k for k in RAWPAGES if k.startswith(base + '?page=')), key=lambda k: int(k.rsplit('C', 1)[-1]))
    for k in keys:
        for sl in slugs_in(all_soups[k], '.view.blog-page > .view-content article.blog--teaser'):
            if sl not in out:
                out.append(sl)
    return out


blog = all_soups['/de/blog']
data = {'featured': slugs_in(blog, '.view-display-id-featured article.blog--teaser'),
        'latest': slugs_in(blog, '.view-display-id-latest article.blog--teaser'),
        'list': paged('/de/blog'), 'categories': {}}
for p in RAWPAGES:
    m = re.match(r'^/de/blog/category/([^/?]+)$', p)
    if m:
        data['categories'][m.group(1)] = paged(p)
write('data/blog.json', json.dumps(data, ensure_ascii=False, indent=2))
print('Blog: featured', len(data['featured']), 'latest', len(data['latest']), 'list', len(data['list']),
      {k: len(v) for k, v in data['categories'].items()}, '| in keiner Hauptliste:',
      [s for s in articles if s not in data['list'] + data['featured'] + data['latest']])


# ---------------------------------------------------------------- Seiten
def page_content(path, markers):
    s = all_soups[path]
    title, desc = head_meta(s)
    main = cleaned_main(s, [(sel, mk) for sel, mk, _ in markers])
    for selector, marker, _ in markers:
        vc = slot(main, marker)
        if vc is None:
            print('WARN Marker-Ziel fehlt:', path, selector)
            continue
        vc.clear()
        vc.append(marker)
    strip_slots(main)
    meta = {'title': title, 'description': desc, 'path': path, 'nav': nav_state(s), 'body_classes': body_classes(s)}
    return meta, ser(main, inner=True)


PAGE_FILES = {'/de': 'de/index', '/de/mission': 'de/mission', '/de/organisation': 'de/organisation',
              '/de/kontakt': 'de/kontakt', '/de/blog': 'de/blog/index'}
for path, rel in PAGE_FILES.items():
    markers = []
    if path == '/de/blog':
        markers = [('.view-display-id-featured > .view-content', '{{teasers:featured}}', None),
                   ('.view-display-id-latest > .view-content', '{{teasers:latest}}', None),
                   ('.view.blog-page > .view-content', '{{teasers:list}}', None)]
    meta, content = page_content(path, markers)
    write('pages/%s.html' % rel, with_meta(meta, content))
for cat in data['categories']:
    meta, content = page_content('/de/blog/category/' + cat,
                                 [('.view.blog-page > .view-content', '{{teasers:category/%s}}' % cat, None)])
    write('pages/de/blog/category/%s.html' % cat, with_meta(meta, content))
meta, content = page_content('__404', [])
meta['path'] = '/404'
write('pages/404.html', with_meta(meta, content))

site = {'site_url': ORIGIN, 'site_name': 'einstAIn', 'lang': 'de', 'noindex': True,
        'nav': nav, 'nav_ul_class': nav_ul_class, 'wrapper_classes': wrapper_classes,
        'teaser_row_open': ROW_OPEN, 'list_page_size': 3,
        'media_redirects': {k: v for k, v in ASSET_MAP.items() if k.startswith('/media/')}}
write('site.json', json.dumps(site, ensure_ascii=False, indent=2))
write('assets/manifest.json', json.dumps(MANIFEST, ensure_ascii=False, indent=1))
print('Assets:', len(MANIFEST), '| Seiten:', len(PAGE_FILES) + len(data['categories']) + 1, '| Artikel:', len(articles))
print('wrapper', wrapper_classes, '| nav ul', nav_ul_class, '| row', ROW_OPEN, '| cat item', CAT_ITEM)
print('nav states:', sorted({(p, nav_state(s)) for p, s in all_soups.items() if s.find('main')})[:6])
