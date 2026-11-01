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
      // Counts visitors who begin a form, so abandonment shows against
      // generate_lead. Not called form_start: GA4's enhanced measurement already
      // sends an event by that name, and the two would merge.
      var lineInput = form.querySelector('input[name="line"]');
      form.addEventListener('focusin', function onStart() {
        form.removeEventListener('focusin', onStart);
        if (typeof window.agTrack === 'function') {
          window.agTrack('ag_form_start', { form_line: lineInput ? lineInput.value : '' });
        }
      });

      form.addEventListener('submit', function (event) {
        event.preventDefault();
        if (form.getAttribute('data-busy') === '1') return;

        clearMessages(form);

        // Catch empty and malformed fields here. A server round trip for a typo
        // also spends the single-use Turnstile token and makes the visitor wait
        // for a new one.
        var problems = checkFields(form);
        if (Object.keys(problems).length) {
          showMessages(form, problems);
          return;
        }

        var button = form.querySelector('button[type="submit"]');
        var label = button ? button.textContent : '';
        busy(form, button, true, 'Sending…');

        // Interaction-only Turnstile hands over its token a moment after the page
        // loads. A visitor who submits first waits for it instead of being refused.
        waitForToken(form, 8000).then(function () { send(form, button, label); });
      });
    });

    function send(form, button, label) {
      var data = new FormData(form);
      data.append('page', location.pathname);

      // The Worker stores only name/company/email/phone/notes/page, so the
      // general-inquiry line dropdown rides inside notes instead of being dropped.
      var interest = form.querySelector('select[name="interest"]');
      data.delete('interest');
      if (interest && interest.value) {
        var notes = (data.get('notes') || '').toString().trim();
        data.set('notes', 'Line of interest: ' + interest.options[interest.selectedIndex].text +
          (notes ? '\n\n' + notes : ''));
      }
      // Risk pages (2026-11-01) carry a hidden "risk" input naming the page's
      // risk type. Same treatment as interest: the Worker would drop it.
      var risk = (data.get('risk') || '').toString().trim();
      data.delete('risk');
      if (risk) {
        var n2 = (data.get('notes') || '').toString().trim();
        data.set('notes', 'Risk page: ' + risk + (n2 ? '\n\n' + n2 : ''));
      }
      // Attribution: the first-touch UTMs captured on landing (see agAttribution
      // below) ride in notes as one tagged line, for the same reason.
      var attr = window.agAttribution ? window.agAttribution() : null;
      if (attr && attr.line) {
        var n3 = (data.get('notes') || '').toString().trim();
        data.set('notes', (n3 ? n3 + '\n\n' : '') + attr.line);
      }
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
              var params = { currency: 'USD', value: 1.0, form_line: line };
              if (attr && attr.params) {
                for (var k in attr.params) {
                  if (Object.prototype.hasOwnProperty.call(attr.params, k)) params[k] = attr.params[k];
                }
              }
              window.agTrack('generate_lead', params);
            }
            if (typeof window.agAgile === 'function') window.agAgile(form, data);
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
    }

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

    // Same tests and wording as the Worker, so the browser and the server never
    // disagree about what counts as a valid entry.
    var EMAIL_RE = /^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$/;

    function checkFields(form) {
      var errors = {};
      form.querySelectorAll('[required]').forEach(function (el) {
        if (!el.value.trim()) errors[el.name] = 'Required.';
      });
      var email = form.querySelector('[name="email"]');
      if (email && email.value.trim() && !EMAIL_RE.test(email.value.trim())) {
        errors.email = 'That does not look like an email address.';
      }
      return errors;
    }

    // Resolves once Turnstile has filled its hidden token input, or after `ms`
    // either way; the Worker still makes the final call on a missing token.
    function waitForToken(form, ms) {
      return new Promise(function (resolve) {
        if (!form.querySelector('.cf-turnstile')) { resolve(); return; }
        var start = Date.now();
        (function poll() {
          var token = form.querySelector('[name="cf-turnstile-response"]');
          if ((token && token.value) || Date.now() - start >= ms) { resolve(); return; }
          setTimeout(poll, 200);
        })();
      });
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

/* ── First-touch attribution (added 2026-11-01, risk landing pages) ────
   On landing, keep the visit's UTM tags, click IDs, first landing page and
   referrer in sessionStorage, so the form a visitor submits three pages later
   still knows where they came from. The Worker keeps only name, company, email,
   phone, notes and page, so site.js folds this into notes as one tagged line
   ("[utm] source=…; medium=…") and sends it with generate_lead as GA4 event
   parameters. First touch wins within a session; nothing is stored across
   sessions. Every storage access is wrapped: private windows can throw.
   ──────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';
  var KEY = 'ag_attr';
  var FIELDS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'fbclid'];

  function read() {
    try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { return null; }
  }

  function clean(v) {
    return String(v || '').replace(/[\r\n;=]/g, ' ').slice(0, 120).trim();
  }

  try {
    if (!read()) {
      var q = new URLSearchParams(location.search);
      var rec = { landing: location.pathname, referrer: '' };
      FIELDS.forEach(function (f) { if (q.get(f)) rec[f] = clean(q.get(f)); });
      try {
        var ref = document.referrer ? new URL(document.referrer) : null;
        if (ref && ref.hostname !== location.hostname) rec.referrer = clean(ref.hostname);
      } catch (e) { /* malformed referrer: ignore */ }
      sessionStorage.setItem(KEY, JSON.stringify(rec));
    }
  } catch (e) { /* storage unavailable: attribution is simply absent */ }

  window.agAttribution = function () {
    var r = read();
    if (!r) return null;
    var bits = [];
    var params = {};
    var map = { utm_source: 'source', utm_medium: 'medium', utm_campaign: 'campaign',
      utm_content: 'content', utm_term: 'term', gclid: 'gclid', fbclid: 'fbclid' };
    FIELDS.forEach(function (f) {
      if (r[f]) { bits.push(map[f] + '=' + r[f]); params['lead_' + map[f]] = r[f]; }
    });
    if (r.landing) { bits.push('landing=' + r.landing); params.lead_landing = r.landing; }
    if (r.referrer) { bits.push('referrer=' + r.referrer); params.lead_referrer = r.referrer; }
    if (!bits.length) return null;
    return { line: '[utm] ' + bits.join('; '), params: params };
  };
})();

// Agile CRM (GATE C, Bill 2026-10-31: client-side). After the Worker accepts a lead,
// the same details go to the agency's Agile web form in the background, tagged per the
// insurance tag plan. The domain and key are Agile's public web-form tracking values
// (Agile embeds them in every website form). It runs only after the Worker said ok, it
// never blocks or delays the thank-you redirect, and any failure is ignored: the Worker
// copy and its notification email stay the record of the lead.
(function () {
  var AGILE = {
    domain: 'savingsre',
    api: 'o8d0am3m1ras18l8f0r0qai4hq',
    formName: 'AlphaGen Website Lead',
    formId: '4901019659730944',
    // Every website lead. ins-web-lead is the trigger tag for the welcome campaign.
    tags: ['INS-Contact', 'INS-Role-Client', 'INS-Src-Website', 'ins-dial-list', 'ins-web-lead']
  };
  // Forms that are not risk pages carry no data-agile-* attributes; their Worker
  // line decides the audience and, where it names one, the line tag.
  var BY_LINE = {
    'general-liability': ['Commercial', 'General-Liability'],
    'workers-comp': ['Commercial', 'Workers-Comp'],
    'commercial': ['Commercial', ''],
    'cyber': ['Commercial', 'Cyber'],
    'commercial-ebook': ['Commercial', ''],
    'relocation-business': ['Commercial', ''],
    'homeowners': ['Personal', 'Homeowners'],
    'personal-lines': ['Personal', ''],
    'relocation': ['Personal', ''],
    'relocation-guide': ['Personal', '']
  };

  window.agAgile = function (form, data) {
    try {
      if (!AGILE.formName || !window.fetch || !window.URLSearchParams) return;
      var line = (data.get('line') || '').toString();
      var group = form.getAttribute('data-agile-group') || '';
      var tag = form.getAttribute('data-agile-line') || '';
      var sel = form.querySelector('select[name="interest"]');
      var opt = sel && sel.selectedIndex > -1 ? sel.options[sel.selectedIndex] : null;
      if (opt && opt.getAttribute('data-agile-line')) {
        tag = opt.getAttribute('data-agile-line');
        group = opt.getAttribute('data-agile-group') || group;
      }
      if (!group && BY_LINE[line]) group = BY_LINE[line][0];
      if (!tag && BY_LINE[line]) tag = BY_LINE[line][1];
      var tags = AGILE.tags.slice();
      if (group) tags.push('INS-Aud-Client-' + group);
      if (tag) tags.push('INS-Line-' + tag);

      var name = (data.get('name') || '').toString().trim().split(/\s+/);
      var q = new URLSearchParams();
      q.set('_agile_form_name', AGILE.formName);
      q.set('_agile_domain', AGILE.domain);
      q.set('_agile_api', AGILE.api);
      q.set('_agile_form_id', AGILE.formId);
      q.set('_agile_redirect_url', location.origin + '/thank-you/');
      q.set('_agile_document_url', location.href.split('?')[0]);
      q.set('_agile_confirmation_msg', 'Thanks.');
      q.set('tags', tags.join(','));
      q.set('first_name', name.shift() || '');
      q.set('last_name', name.join(' '));
      ['email', 'phone', 'company'].forEach(function (f) {
        var v = (data.get(f) || '').toString().trim();
        if (v) q.set(f, v);
      });
      q.set('note', ((data.get('notes') || '').toString().trim() + '\n\nPage: ' + location.pathname +
        (line ? '\nForm line: ' + line : '')).trim());
      fetch('https://' + AGILE.domain + '.agilecrm.com/formsubmit?' + q.toString(),
        { method: 'GET', mode: 'no-cors', credentials: 'omit', keepalive: true })
        .catch(function () { /* the Worker already has the lead */ });
    } catch (e) { /* never block the visitor */ }
  };
})();
