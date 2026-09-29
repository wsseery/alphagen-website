/* AlphaGen Insurance Agency — shared site script
   Nav toggle, header shadow, and click tracking for tel: links and CTAs.
   Defensive: every element is feature-detected before binding. */
(function () {
  'use strict';

  window.dataLayer = window.dataLayer || [];

  // Push to dataLayer AND, when gtag.js is present, send the GA4 event directly.
  function track(name, params) {
    var payload = { event: name };
    for (var k in params) if (Object.prototype.hasOwnProperty.call(params, k)) payload[k] = params[k];
    window.dataLayer.push(payload);
    if (typeof window.gtag === 'function') window.gtag('event', name, params);
  }
  window.agTrack = track;

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    // Header scroll shadow
    var header = document.getElementById('site-header');
    if (header) {
      var onScroll = function () {
        if (window.scrollY > 40) header.classList.add('scrolled');
        else header.classList.remove('scrolled');
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }

    // Mobile nav
    var toggle = document.getElementById('mobile-toggle');
    var panel = document.getElementById('mobile-nav');
    if (toggle && panel) {
      var openIcon = toggle.innerHTML;
      var closeIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      toggle.addEventListener('click', function () {
        var isOpen = panel.classList.toggle('open');
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        toggle.setAttribute('aria-label', isOpen ? 'Close menu' : 'Open menu');
        toggle.innerHTML = isOpen ? closeIcon : openIcon;
      });
      panel.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', function () {
          panel.classList.remove('open');
          toggle.setAttribute('aria-expanded', 'false');
          toggle.setAttribute('aria-label', 'Open menu');
          toggle.innerHTML = openIcon;
        });
      });
    }

    // tel: clicks
    document.querySelectorAll('a[href^="tel:"]').forEach(function (a) {
      a.addEventListener('click', function () {
        track('phone_click', {
          phone_number: a.getAttribute('href').replace('tel:', ''),
          link_label: a.getAttribute('data-label') || a.textContent.trim(),
          page_path: location.pathname
        });
      });
    });

    // mailto: clicks
    document.querySelectorAll('a[href^="mailto:"]').forEach(function (a) {
      a.addEventListener('click', function () {
        track('email_click', { link_label: a.textContent.trim(), page_path: location.pathname });
      });
    });

    // CTA clicks — any element carrying data-cta
    document.querySelectorAll('[data-cta]').forEach(function (a) {
      a.addEventListener('click', function () {
        track('cta_click', {
          cta_label: a.getAttribute('data-cta'),
          destination: a.getAttribute('href') || '',
          page_path: location.pathname
        });
      });
    });
  });
})();

/* ── Native quote forms — progressive enhancement ──────────────────────
   Added 2026-09-29 with the move off JotForm.

   Without JavaScript the form still works: it is a plain POST to /api/quote
   and the Worker answers with a 302 to /thank-you/?line=…  This only makes it
   nicer — inline errors, no page flash, and a chance to fire generate_lead
   BEFORE navigating away.

   The redirect carries &src=ag so /thank-you/ knows not to fire the event a
   second time. Change one without the other and every lead double-counts.
   ──────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    var forms = document.querySelectorAll('form.ag-form');
    if (!forms.length) return;

    Array.prototype.forEach.call(forms, function (form) {
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        if (form.getAttribute('data-busy') === '1') return;

        clearMessages(form);

        var button = form.querySelector('button[type="submit"]');
        var label = button ? button.textContent : '';
        busy(form, button, true, 'Sending…');

        var data = new FormData(form);
        data.append('page', location.pathname);
        var line = (data.get('line') || '').toString();

        fetch(form.getAttribute('action'), {
          method: 'POST',
          body: data,
          headers: { 'Accept': 'application/json' },
          credentials: 'same-origin'
        })
          .then(function (res) {
            return res.json().then(function (b) { return b; }, function () { return null; });
          })
          .then(function (body) {
            if (body && body.ok) {
              // Fire the conversion here, while we still control the page.
              if (typeof window.agTrack === 'function') {
                window.agTrack('generate_lead', { currency: 'USD', value: 1.0, form_line: line });
              }
              var to = body.redirect || ('/thank-you/?line=' + encodeURIComponent(line));
              to += (to.indexOf('?') === -1 ? '?' : '&') + 'src=ag';
              // Give the analytics beacon a moment before navigating.
              setTimeout(function () { location.href = to; }, 250);
              return;
            }
            showMessages(form, (body && body.errors) || {
              form: 'Something went wrong. Please try again, or call (561) 220-0402.'
            });
            resetTurnstile(form);
            busy(form, button, false, label);
          })
          .catch(function () {
            showMessages(form, {
              form: 'We could not reach the server. Please check your connection, or call (561) 220-0402.'
            });
            resetTurnstile(form);
            busy(form, button, false, label);
          });
      });
    });

    function busy(form, button, on, label) {
      form.setAttribute('data-busy', on ? '1' : '0');
      if (!button) return;
      button.disabled = on;
      button.setAttribute('aria-busy', on ? 'true' : 'false');
      button.textContent = label;
    }

    function clearMessages(form) {
      form.querySelectorAll('.ag-error, .ag-message').forEach(function (el) {
        el.parentNode.removeChild(el);
      });
      form.querySelectorAll('[aria-invalid="true"]').forEach(function (el) {
        el.removeAttribute('aria-invalid');
        el.removeAttribute('aria-describedby');
      });
    }

    function showMessages(form, errors) {
      var first = null;
      var general = [];

      Object.keys(errors).forEach(function (key) {
        var fieldEl = form.querySelector('[name="' + key + '"]');
        if (!fieldEl) { general.push(errors[key]); return; }
        var id = (fieldEl.id || key) + '-error';
        var note = document.createElement('p');
        note.className = 'ag-error';
        note.id = id;
        note.textContent = errors[key];
        fieldEl.setAttribute('aria-invalid', 'true');
        fieldEl.setAttribute('aria-describedby', id);
        fieldEl.parentNode.appendChild(note);
        if (!first) first = fieldEl;
      });

      if (general.length) {
        var box = document.createElement('p');
        box.className = 'ag-message';
        box.setAttribute('role', 'alert');
        box.textContent = general.join(' ');
        var set = form.querySelector('fieldset') || form;
        set.insertBefore(box, set.firstChild);
        if (!first) first = box;
      }

      if (first && typeof first.focus === 'function') first.focus();
      else if (first && first.scrollIntoView) first.scrollIntoView({ block: 'center' });
    }

    // A Turnstile token is single-use. Without this, a visitor who fixes a typo
    // and resubmits is rejected for a stale token rather than for anything they did.
    function resetTurnstile(form) {
      var widget = form.querySelector('.cf-turnstile');
      if (widget && window.turnstile && typeof window.turnstile.reset === 'function') {
        try { window.turnstile.reset(widget); } catch (e) { /* not fatal */ }
      }
    }
  });
})();
