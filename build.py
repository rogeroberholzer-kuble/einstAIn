#!/usr/bin/env python3
"""einstAIn Website: baut aus src/ die fertige statische Seite in dist/.

Aufruf:  python3 build.py
Braucht nur die Python-Standardbibliothek. Aufbau und Arbeitsweise stehen in README.md.
"""
import html
import json
import os
import re
import shutil
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src')
DIST = os.path.join(ROOT, 'dist')


def read(rel):
    with open(os.path.join(SRC, rel), encoding='utf-8') as f:
        return f.read()


def read_meta(rel):
    """Datei mit <!--meta {json} --> Kopf lesen -> (meta, inhalt)."""
    text = read(rel)
    m = re.match(r'\s*<!--meta\s*(\{.*?\})\s*-->\s*', text, flags=re.S)
    if not m:
        raise SystemExit('Kein meta-Kopf in ' + rel)
    return json.loads(m.group(1)), text[m.end():].strip()


SITE = json.loads(read('site.json'))
BLOG = json.loads(read('data/blog.json'))
TPL = {n: read('templates/%s.html' % n).strip()
       for n in ('layout', 'teaser', 'article', 'category-item', 'category-list')}
HEADER = read('partials/header.html').strip()
FOOTER = read('partials/footer.html').strip()
URL = SITE['site_url'].rstrip('/')

ARTICLES = {}
for fn in sorted(os.listdir(os.path.join(SRC, 'articles'))):
    if fn.endswith('.html'):
        meta, body = read_meta('articles/' + fn)
        meta['body'] = body
        ARTICLES[meta['slug']] = meta


def esc(text, quote=False):
    return html.escape(text, quote=quote)


def fill_article(tpl, art):
    path = '/de/blog/' + art['slug']
    return (tpl.replace('{{abs_url}}', URL + path).replace('{{url}}', path)
            .replace('{{title_enc}}', urllib.parse.quote(art['title'], safe=''))
            .replace('{{title_attr}}', esc(art['title'], True))
            .replace('{{title}}', esc(art['title'])))


def render_teaser(slug):
    art = ARTICLES[slug]
    return fill_article(TPL['teaser'].replace('{{img}}', art.get('teaser_image_html') or art.get('image_html', '')), art)


def render_rows(slugs):
    row_open = SITE.get('teaser_row_open', '')
    out = []
    for slug in slugs:
        if slug not in ARTICLES:
            print('WARNUNG: Artikel fehlt in src/articles:', slug)
            continue
        teaser = render_teaser(slug)
        out.append(row_open + '\n' + teaser + '\n</div>' if row_open else teaser)
    return '\n'.join(out)


def teaser_list(name):
    if name.startswith('category/'):
        return BLOG['categories'].get(name.split('/', 1)[1], [])
    return BLOG.get(name, [])


def render_nav(page_path, nav_href):
    items = []
    for item in SITE['nav']:
        active = item['href'] == nav_href
        current = active and item['href'] == page_path
        li = 'nav-item active' if active else 'nav-item'
        a = 'nav-link active is-active' if current else ('nav-link active' if active else 'nav-link')
        aria = ' aria-current="page"' if current else ''
        items.append('<li class="%s"><a class="%s" href="%s"%s>%s</a></li>' % (li, a, item['href'], aria, esc(item['label'])))
    return '<ul class="%s">\n%s\n</ul>' % (SITE.get('nav_ul_class', 'nav'), '\n'.join(items))


def head_tags(meta, path, og_type='website', image=''):
    title = meta.get('head_title') or meta['title']
    tags = []
    desc = meta.get('description', '')
    if desc:
        tags.append('<meta name="description" content="%s">' % esc(desc, True))
    if meta.get('noindex') or SITE.get('noindex'):
        tags.append('<meta name="robots" content="noindex, nofollow">')
    if not meta.get('no_canonical'):
        tags.append('<link rel="canonical" href="%s%s">' % (URL, path))
        tags.append('<meta property="og:url" content="%s%s">' % (URL, path))
    tags.append('<meta property="og:site_name" content="%s">' % esc(SITE['site_name'], True))
    tags.append('<meta property="og:type" content="%s">' % og_type)
    tags.append('<meta property="og:title" content="%s">' % esc(title, True))
    if desc:
        tags.append('<meta property="og:description" content="%s">' % esc(desc, True))
    if image:
        tags.append('<meta property="og:image" content="%s%s">' % (URL, image))
        tags.append('<meta name="twitter:card" content="summary_large_image">')
    return '%s | %s' % (title, SITE['site_name']), '\n'.join(tags)


def render_page(meta, content, path, og_type='website', image='', extra_head=''):
    head_title, tags = head_tags(meta, path, og_type, image)
    classes = ' '.join(meta.get('body_classes', []))
    nav = render_nav(path, meta.get('nav', ''))
    page = TPL['layout']
    for key, value in (('{{lang}}', SITE.get('lang', 'de')), ('{{head_title}}', esc(head_title)),
                       ('{{meta}}', tags + extra_head), ('{{body_class}}', ' class="%s"' % classes if classes else ''),
                       ('{{header}}', HEADER.replace('{{nav}}', nav)), ('{{footer}}', FOOTER),
                       ('{{content}}', content)):
        page = page.replace(key, value)
    return page


def out_file(path):
    return 'index.html' if path in ('', '/') else path.strip('/') + '/index.html'


def write_dist(rel, text):
    out = os.path.join(DIST, rel)
    # PDFs liegen nicht auf dem Host (Limite 5 MB pro Datei): docs_base in site.json nennt ihren Ablageort.
    if SITE.get('docs_base') and rel.endswith('.html'):
        text = text.replace('/assets/docs/', SITE['docs_base'].rstrip('/') + '/')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text)


def first_src(img_html):
    m = re.search(r'\ssrc="([^"]+)"', img_html or '')
    return m.group(1) if m else ''


def main():
    if os.path.isdir(DIST):
        try:
            shutil.rmtree(DIST)
        except OSError:
            # Loeschen nicht erlaubt (z.B. in Claude-Sitzungen): Dateien werden ueberschrieben.
            print('Hinweis: dist/ konnte nicht geleert werden, Dateien werden ueberschrieben.')
    os.makedirs(DIST, exist_ok=True)
    urls = []

    # Seiten aus src/pages
    for base, _dirs, files in os.walk(os.path.join(SRC, 'pages')):
        for fn in sorted(files):
            if not fn.endswith('.html'):
                continue
            rel = os.path.relpath(os.path.join(base, fn), SRC)
            meta, content = read_meta(rel)
            content = re.sub(r'\{\{teasers:([^}]+)\}\}', lambda m: render_rows(teaser_list(m.group(1))), content)
            content = content.replace('<div class="view blog-page', '<div data-page-size="%d" class="view blog-page' % SITE.get('list_page_size', 3))
            path = meta['path']
            if path == '/404':
                meta404 = dict(meta, noindex=True, no_canonical=True)
                redirects = json.dumps(SITE.get('media_redirects', {}), ensure_ascii=False)
                router = ('\n<script>(function(){var p=location.pathname.replace(/\\/+$/,"");var m=%s;'
                          'if(p===""){location.replace("/de");}else if(m[p]){location.replace(m[p]);}})();</script>' % redirects)
                # Der Host liefert fuer unbekannte Pfade die Wurzel-index.html aus: sie ist 404-Seite und leitet / nach /de.
                write_dist('index.html', render_page(meta404, content, '/', extra_head=router))
                write_dist('404.html', render_page(meta404, content, '/404'))
                continue
            write_dist(out_file(path), render_page(meta, content, path))
            urls.append(path)

    # Artikel
    for slug, art in ARTICLES.items():
        path = '/de/blog/' + slug
        cats = ''.join(TPL['category-item'].replace('{{href}}', c['href']).replace('{{name}}', esc(c['name']))
                       for c in art.get('categories', []))
        cats = TPL['category-list'].replace('{{items}}', cats) if cats else ''
        tpl = TPL['article']
        if not art.get('related'):
            tpl = re.sub(r'<!--related-start-->.*?<!--related-end-->', '', tpl, flags=re.S)
        tpl = tpl.replace('<!--related-start-->', '').replace('<!--related-end-->', '')
        content = (tpl.replace('{{img}}', art.get('image_html', ''))
                   .replace('{{categories}}', cats)
                   .replace('{{related}}', render_rows(art.get('related', []))))
        content = fill_article(content, art).replace('{{body}}', art['body'])
        write_dist(out_file(path), render_page(art, content, path, og_type='article', image=first_src(art.get('image_html'))))
        urls.append(path)

    # Assets und statische Dateien
    shutil.copytree(os.path.join(SRC, 'assets'), os.path.join(DIST, 'assets'), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('manifest.json', '.DS_Store'))
    static = os.path.join(SRC, 'static')
    if os.path.isdir(static):
        shutil.copytree(static, DIST, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.DS_Store'))

    # robots.txt, sitemap.xml, RSS
    if SITE.get('noindex'):
        write_dist('robots.txt', 'User-agent: *\nDisallow: /\n')
    else:
        write_dist('robots.txt', 'User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n' % URL)
    write_dist('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n'
               % '\n'.join('  <url><loc>%s%s</loc></url>' % (URL, u) for u in sorted(urls)))
    order = []
    for slug in BLOG.get('featured', []) + BLOG.get('latest', []) + BLOG.get('list', []):
        if slug in ARTICLES and slug not in order:
            order.append(slug)
    items = '\n'.join('  <item>\n    <title>%s</title>\n    <link>%s/de/blog/%s</link>\n    <guid>%s/de/blog/%s</guid>\n    <description>%s</description>\n  </item>'
                      % (esc(ARTICLES[s]['title']), URL, s, URL, s, esc(ARTICLES[s].get('description', ''))) for s in order)
    write_dist('de/rss.xml', '<?xml version="1.0" encoding="utf-8"?>\n<rss version="2.0">\n<channel>\n  <title>%s</title>\n  <link>%s/de</link>\n  <description>Insights von einstAIn</description>\n  <language>de</language>\n%s\n</channel>\n</rss>\n'
               % (esc(SITE['site_name']), URL, items))

    # Kontrolle: verweisen alle /assets/-Pfade auf vorhandene Dateien?
    missing, pages, size = set(), 0, 0
    for base, _dirs, files in os.walk(DIST):
        for fn in files:
            if fn.endswith('.html'):
                pages += 1
                text = open(os.path.join(base, fn), encoding='utf-8').read()
                size += len(text.encode('utf-8'))
                for ref in re.findall(r'["\s,](/assets/[^"\s,#?]+)', text):
                    if not os.path.isfile(os.path.join(DIST, ref.lstrip('/'))):
                        missing.add(ref)
    print('Gebaut: %d HTML-Dateien, zusammen %d KB' % (pages, size // 1024))
    if missing:
        print('FEHLENDE ASSETS:', sorted(missing))


if __name__ == '__main__':
    main()
