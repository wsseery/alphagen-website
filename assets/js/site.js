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
