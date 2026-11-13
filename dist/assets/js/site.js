/* einstAIn Website: Verhalten der Seite, ohne Abhaengigkeiten.
   Ersetzt jQuery, Bootstrap-JS, GSAP und die Drupal-Skripte der alten Seite. */
(function () {
  'use strict';
  var doc = document;

  /* Menue oeffnen und schliessen */
  doc.querySelectorAll('.page-menu-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      doc.body.classList.toggle('navigation-open');
    });
  });

  /* Einblenden beim Scrollen (vorher GSAP ScrollTrigger: opacity 0, y 40, scale .98 -> 0.4s) */
  var targets = [];
  doc.querySelectorAll('.scroll-appear-inner').forEach(function (section) {
    section.querySelectorAll('p, h2, h3, h4, .field--name-field-link').forEach(function (el) { targets.push(el); });
  });
  doc.querySelectorAll('.scroll-appear').forEach(function (el) { targets.push(el); });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('appear-in');
        } else if (entry.boundingClientRect.top > 0) {
          entry.target.classList.remove('appear-in');
        }
      });
    }, { rootMargin: '0px 0px 40px 0px' });
    targets.forEach(function (el) {
      el.classList.add('appear');
      io.observe(el);
    });
  }

  /* Akkordeon (vorher Bootstrap Collapse) */
  function whenDone(el, cb) {
    var called = false;
    function finish() {
      if (called) { return; }
      called = true;
      el.removeEventListener('transitionend', finish);
      cb();
    }
    el.addEventListener('transitionend', finish);
    setTimeout(finish, 450);
  }
  function setButtons(el, open) {
    doc.querySelectorAll('[data-bs-target="#' + el.id + '"]').forEach(function (b) {
      b.classList.toggle('collapsed', !open);
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  function collapse(el, open) {
    if (el.classList.contains('collapsing')) { return; }
    if (open) {
      el.classList.remove('collapse');
      el.classList.add('collapsing');
      el.style.height = '0px';
      setButtons(el, true);
      requestAnimationFrame(function () { el.style.height = el.scrollHeight + 'px'; });
      whenDone(el, function () {
        el.classList.remove('collapsing');
        el.classList.add('collapse', 'show');
        el.style.height = '';
      });
    } else {
      el.style.height = el.getBoundingClientRect().height + 'px';
      void el.offsetHeight;
      el.classList.add('collapsing');
      el.classList.remove('collapse', 'show');
      setButtons(el, false);
      requestAnimationFrame(function () { el.style.height = '0px'; });
      whenDone(el, function () {
        el.classList.remove('collapsing');
        el.classList.add('collapse');
        el.style.height = '';
      });
    }
  }
  doc.addEventListener('click', function (ev) {
    var btn = ev.target.closest ? ev.target.closest('[data-bs-toggle="collapse"]') : null;
    if (!btn) { return; }
    var target = doc.querySelector(btn.getAttribute('data-bs-target'));
    if (!target) { return; }
    ev.preventDefault();
    var isOpen = target.classList.contains('show');
    var parent = target.getAttribute('data-bs-parent');
    if (!isOpen && parent) {
      doc.querySelectorAll(parent + ' .collapse.show').forEach(function (other) {
        if (other !== target) { collapse(other, false); }
      });
    }
    collapse(target, !isOpen);
  });

  /* Blog-Listen: "Mehr laden" blendet die naechsten Eintraege ein */
  doc.querySelectorAll('.view.blog-page').forEach(function (view) {
    var list = null;
    Array.prototype.forEach.call(view.children, function (child) {
      if (child.classList.contains('view-content')) { list = child; }
    });
    var wrap = view.querySelector('.load-more-btn-wrapper');
    var btn = view.querySelector('.blog-load-more-btn');
    if (!list) { return; }
    var rows = Array.prototype.slice.call(list.children);
    var size = parseInt(view.getAttribute('data-page-size') || '3', 10);
    var shown = size;
    function apply() {
      rows.forEach(function (row, i) { row.style.display = i < shown ? '' : 'none'; });
      if (wrap && shown >= rows.length) { wrap.style.display = 'none'; }
    }
    if (btn) {
      btn.addEventListener('click', function (ev) {
        ev.preventDefault();
        shown += size;
        apply();
      });
    }
    apply();
  });

  /* Kontaktformular: speichert in der Host-Datenbank (Tabelle main/contact_messages) */
  doc.querySelectorAll('form[data-contact-form]').forEach(function (form) {
    var status = form.querySelector('.form-status');
    var submit = form.querySelector('[type="submit"]');
    function show(text, ok) {
      if (!status) { return; }
      status.textContent = text;
      status.className = 'form-status alert ' + (ok ? 'alert-success' : 'alert-danger');
    }
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }
      var data = new FormData(form);
      var thanks = 'Vielen Dank für Ihre Nachricht. Wir melden uns in Kürze.';
      if (data.get('website')) {
        form.reset();
        show(thanks, true);
        return;
      }
      var row = {
        name: String(data.get('name') || ''),
        company: String(data.get('company') || ''),
        email: String(data.get('email') || ''),
        message: String(data.get('message') || ''),
        page: location.pathname,
        created_at: new Date().toISOString()
      };
      if (submit) { submit.disabled = true; }
      fetch(form.getAttribute('action'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(row)
      }).then(function (res) {
        if (!res.ok) { throw new Error('HTTP ' + res.status); }
        form.reset();
        show(thanks, true);
      }).catch(function () {
        show('Die Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es später erneut oder schreiben Sie uns per E-Mail.', false);
      }).then(function () {
        if (submit) { submit.disabled = false; }
      });
    });
  });
})();
