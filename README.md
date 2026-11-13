# einstAIn Website

Statischer Nachbau von einstain.ch (vorher Drupal 11) fuer den Kuble Host.
Live-Test: https://einstain.host.kuble.ai/ (Slug `einstain`, Host "Neu").

## Aufbau

- `src/` ist die Quelle der Wahrheit. Hier wird gearbeitet.
  - `site.json`: Domain, Navigation, noindex-Schalter, Weiterleitungen der alten PDF-Links.
  - `pages/`: Seiten. Jede Datei beginnt mit einem `<!--meta {...} -->` Kopf (Titel, Beschreibung, Pfad, aktiver Menuepunkt), danach folgt der Inhalt von `<main>`.
  - `articles/`: Blogartikel. Kopf mit Titel, Beschreibung, Bild, Kategorien, verwandten Artikeln. Danach der Artikeltext.
  - `data/blog.json`: Reihenfolge der Artikel (featured, latest, Hauptliste, Kategorien).
  - `templates/`: Seitenrahmen (`layout.html`), Artikelseite, Teaser.
  - `partials/`: Header und Footer.
  - `assets/`: CSS, JS, Bilder, Schriften, PDFs. `manifest.json` nennt zu jeder Datei die Original-URL auf einstain.ch.
- `build.py` baut daraus `dist/`. Aufruf: `python3 build.py` (nur Python-Standardbibliothek).
- `dist/` ist das Ergebnis und wird auf den Host publiziert. Nie von Hand aendern.
- `tools/import_crawl.py`: einmaliger Import aus dem Crawl. `tools/build_css.py`: erzeugt `site.css` aus dem alten Theme-CSS.
- `_crawl/`: Rohdaten des Crawls vom 13.11.2026. Nur Referenz.

## Typische Aenderungen

- Text einer Seite: Datei in `src/pages/` aendern, bauen, die betroffene Datei aus `dist/` publizieren.
- Neuer Artikel: Datei in `src/articles/` anlegen (bestehenden Artikel als Vorlage nehmen), Slug in `src/data/blog.json` eintragen, Bilder nach `src/assets/img/` legen, bauen. Publiziert werden muessen der Artikel, die Blog-Uebersicht, betroffene Kategorieseiten, `sitemap.xml` und `de/rss.xml`.
- Menue: `nav` in `src/site.json`.
- Eigene Styles: `src/assets/css/custom.css`, danach `python3 tools/build_css.py` und `python3 build.py`.

## Besonderheiten des Hosts

- Unbekannte Pfade liefern die Wurzel-`index.html` mit Status 200. Diese Datei ist deshalb die 404-Seite und leitet `/` per Skript nach `/de` um, ebenso die alten PDF-Links `/media/NN`.
- Pfade ohne Endung (`/de/blog/slug`) werden aus `de/blog/slug/index.html` bedient. Alle Verweise sind absolut (`/assets/...`).
- Kontaktformular: schreibt per `POST /_db/main/contact_messages` in die Host-Datenbank. Der Host verschickt keine Mails.

## Go-live Checkliste

1. `noindex` in `src/site.json` auf `false`, bauen, alles publizieren (robots.txt und Meta-Tags aendern sich).
2. Domain einstain.ch per DNS auf den Host legen (Custom Domain im Host einrichten).
3. Formular einmal testen, taegliche Pruefung der Einsendungen aktiv.
