/**
 * reactbits_dashboard.js — React Bits UI Enhancements for Dashboards
 * Features: Spotlight Metric Cards, Animated Count-Up Counters, 3D Parallax Tilt, Magnetic Buttons.
 */

(function () {
  'use strict';

  /* ==========================================================================
     1. REACT BITS SPOTLIGHT CARD HOVER EFFECT
     ========================================================================== */
  function initSpotlightCards() {
    const spotlightCards = document.querySelectorAll('[data-spotlight="true"], .reactbits-spotlight');

    spotlightCards.forEach((card) => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        card.style.setProperty('--mouse-x', `${x}px`);
        card.style.setProperty('--mouse-y', `${y}px`);
      });
    });
  }

  /* ==========================================================================
     2. REACT BITS ANIMATED COUNT-UP COUNTERS
     ========================================================================== */
  function initCountUpCounters() {
    const counterElements = document.querySelectorAll('[data-counter-target]');

    counterElements.forEach((el) => {
      const rawTarget = el.getAttribute('data-counter-target') || '0';
      const target = parseFloat(rawTarget);
      const isDecimal = rawTarget.includes('.');
      const decimalPlaces = isDecimal ? (rawTarget.split('.')[1] || '').length : 0;
      const prefix = el.getAttribute('data-counter-prefix') || '';
      const suffix = el.getAttribute('data-counter-suffix') || '';
      const duration = parseInt(el.getAttribute('data-counter-duration')) || 1400; // ms

      if (isNaN(target)) return;

      const startTime = performance.now();

      function easeOutExpo(x) {
        return x === 1 ? 1 : 1 - Math.pow(2, -10 * x);
      }

      function updateCounter(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easedProgress = easeOutExpo(progress);

        const currentVal = easedProgress * target;
        const formattedVal = isDecimal ? currentVal.toFixed(decimalPlaces) : Math.round(currentVal);

        el.textContent = `${prefix}${formattedVal}${suffix}`;

        if (progress < 1) {
          requestAnimationFrame(updateCounter);
        } else {
          el.textContent = `${prefix}${isDecimal ? target.toFixed(decimalPlaces) : target}${suffix}`;
        }
      }

      requestAnimationFrame(updateCounter);
    });
  }

  /* ==========================================================================
     3. REACT BITS 3D PARALLAX TILT CARD
     ========================================================================== */
  function init3DTiltCards() {
    const tiltContainers = document.querySelectorAll('[data-tilt="true"]');

    tiltContainers.forEach((card) => {
      card.classList.add('reactbits-tilt-card');
      const maxTilt = parseFloat(card.getAttribute('data-tilt-max')) || 7;

      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const rotateX = ((mouseY - height / 2) / (height / 2)) * -maxTilt;
        const rotateY = ((mouseX - width / 2) / (width / 2)) * maxTilt;

        card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) scale3d(1.02, 1.02, 1.02)`;
      });

      card.addEventListener('mouseleave', () => {
        card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
      });
    });
  }

  /* ==========================================================================
     4. REACT BITS MAGNETIC BUTTONS
     ========================================================================== */
  function initMagnetButtons() {
    const magnetButtons = document.querySelectorAll('[data-magnet="true"], .reactbits-magnet-btn');

    magnetButtons.forEach((btn) => {
      const strength = parseFloat(btn.getAttribute('data-magnet-strength')) || 0.22;

      btn.addEventListener('mousemove', (e) => {
        const rect = btn.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        const distanceX = e.clientX - centerX;
        const distanceY = e.clientY - centerY;

        btn.style.transform = `translate3d(${distanceX * strength}px, ${distanceY * strength}px, 0)`;
      });

      btn.addEventListener('mouseleave', () => {
        btn.style.transform = `translate3d(0px, 0px, 0px)`;
      });
    });
  }

  // Initialize on DOM Ready
  document.addEventListener('DOMContentLoaded', () => {
    initSpotlightCards();
    initCountUpCounters();
    init3DTiltCards();
    initMagnetButtons();
  });
})();
