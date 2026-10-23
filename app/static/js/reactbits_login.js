/**
 * reactbits_login.js — React Bits Inspired Animations for EduAssess Login
 * Features: Aurora Ambient Canvas Shader, Spotlight Card Hover, 3D Parallax Tilt, Magnetic Buttons.
 */

(function () {
  'use strict';

  // State & Mouse Tracking
  const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2, targetX: window.innerWidth / 2, targetY: window.innerHeight / 2 };

  window.addEventListener('mousemove', (e) => {
    mouse.targetX = e.clientX;
    mouse.targetY = e.clientY;
  });

  /* ==========================================================================
     1. REACT BITS AURORA CANVAS ANIMATION
     ========================================================================== */
  function initAuroraCanvas() {
    const canvas = document.getElementById('reactbits-aurora');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    window.addEventListener('resize', () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });

    // Particle Star Dust
    const particles = [];
    const particleCount = 45;
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        radius: Math.random() * 2 + 0.8,
        alpha: Math.random() * 0.6 + 0.2,
        speedX: (Math.random() - 0.5) * 0.4,
        speedY: (Math.random() - 0.5) * 0.4 - 0.2,
      });
    }

    // Color Blobs for Fluid Gradient
    let step = 0;

    function render() {
      // Smooth lerp mouse tracking
      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;

      ctx.clearRect(0, 0, width, height);

      // Check dark mode status
      const isDark = document.documentElement.classList.contains('dark');

      step += 0.008;

      // Dynamic Aurora Gradient Blobs
      const blob1X = width * 0.3 + Math.sin(step) * 120 + (mouse.x - width / 2) * 0.08;
      const blob1Y = height * 0.3 + Math.cos(step * 0.8) * 80 + (mouse.y - height / 2) * 0.08;

      const blob2X = width * 0.7 + Math.cos(step * 1.1) * 140 - (mouse.x - width / 2) * 0.06;
      const blob2Y = height * 0.6 + Math.sin(step * 0.9) * 90 - (mouse.y - height / 2) * 0.06;

      const blob3X = width * 0.5 + Math.sin(step * 0.7) * 100;
      const blob3Y = height * 0.8 + Math.cos(step * 1.2) * 110;

      // Render Aurora Blob 1 (Indigo / Blue)
      const grad1 = ctx.createRadialGradient(blob1X, blob1Y, 0, blob1X, blob1Y, Math.max(width, height) * 0.55);
      if (isDark) {
        grad1.addColorStop(0, 'rgba(99, 102, 241, 0.25)');
        grad1.addColorStop(0.5, 'rgba(79, 70, 229, 0.1)');
        grad1.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else {
        grad1.addColorStop(0, 'rgba(129, 140, 248, 0.35)');
        grad1.addColorStop(0.5, 'rgba(199, 210, 254, 0.15)');
        grad1.addColorStop(1, 'rgba(243, 244, 248, 0)');
      }
      ctx.fillStyle = grad1;
      ctx.fillRect(0, 0, width, height);

      // Render Aurora Blob 2 (Teal / Cyan)
      const grad2 = ctx.createRadialGradient(blob2X, blob2Y, 0, blob2X, blob2Y, Math.max(width, height) * 0.45);
      if (isDark) {
        grad2.addColorStop(0, 'rgba(14, 165, 233, 0.2)');
        grad2.addColorStop(0.5, 'rgba(6, 182, 212, 0.08)');
        grad2.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else {
        grad2.addColorStop(0, 'rgba(56, 189, 248, 0.25)');
        grad2.addColorStop(0.5, 'rgba(186, 230, 253, 0.12)');
        grad2.addColorStop(1, 'rgba(243, 244, 248, 0)');
      }
      ctx.fillStyle = grad2;
      ctx.fillRect(0, 0, width, height);

      // Render Aurora Blob 3 (Purple Accent)
      const grad3 = ctx.createRadialGradient(blob3X, blob3Y, 0, blob3X, blob3Y, Math.max(width, height) * 0.4);
      if (isDark) {
        grad3.addColorStop(0, 'rgba(168, 85, 247, 0.15)');
        grad3.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else {
        grad3.addColorStop(0, 'rgba(192, 132, 252, 0.2)');
        grad3.addColorStop(1, 'rgba(243, 244, 248, 0)');
      }
      ctx.fillStyle = grad3;
      ctx.fillRect(0, 0, width, height);

      // Render Floating Dust Particles
      ctx.fillStyle = isDark ? 'rgba(255, 255, 255, 0.8)' : 'rgba(99, 102, 241, 0.6)';
      particles.forEach((p) => {
        p.x += p.speedX;
        p.y += p.speedY;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.save();
        ctx.globalAlpha = p.alpha;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      });

      requestAnimationFrame(render);
    }

    render();
  }

  /* ==========================================================================
     2. REACT BITS SPOTLIGHT CARD EFFECT
     ========================================================================== */
  function initSpotlightCard() {
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
     3. REACT BITS 3D PARALLAX TILT CARD
     ========================================================================== */
  function init3DTiltCard() {
    const tiltContainers = document.querySelectorAll('[data-tilt="true"]');

    tiltContainers.forEach((card) => {
      card.classList.add('reactbits-tilt-card');
      const maxTilt = parseFloat(card.getAttribute('data-tilt-max')) || 8;

      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const rotateX = ((mouseY - height / 2) / (height / 2)) * -maxTilt;
        const rotateY = ((mouseX - width / 2) / (width / 2)) * maxTilt;

        card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) scale3d(1.015, 1.015, 1.015)`;
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
      const strength = parseFloat(btn.getAttribute('data-magnet-strength')) || 0.25;

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
    initAuroraCanvas();
    initSpotlightCard();
    init3DTiltCard();
    // initMagnetButtons disabled for button stability
  });
})();
