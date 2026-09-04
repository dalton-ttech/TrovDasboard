/* CountUp.js 2.9.0 is vendored locally; no runtime CDN or framework is required. */
(() => {
  'use strict';
  let previousKey = null;
  let counters = [];

  function mount(root, key, { replay = false } = {}) {
    counters.forEach(({ counter, element, finalText }) => { counter.reset(); element.textContent = finalText; });
    counters = [];
    const values = [...root.querySelectorAll('[data-count-target]')];
    if (!values.length) { previousKey = null; return; }
    const changed = key !== previousKey;
    previousKey = key;
    if ((!replay && !changed) || window.matchMedia('(prefers-reduced-motion: reduce)').matches || !window.countUp?.CountUp) return;

    for (const element of values) {
      const target = Number(element.dataset.countTarget);
      if (!Number.isFinite(target)) continue;
      const finalText = element.textContent;
      const counter = new window.countUp.CountUp(element, target, {
        startVal: 0, duration: 0.8, decimalPlaces: Number(element.dataset.countDecimals),
        separator: ',', decimal: '.', useGrouping: true, useEasing: true,
        smartEasingThreshold: Number.MAX_SAFE_INTEGER,
      });
      if (counter.error) { element.textContent = finalText; continue; }
      counters.push({ counter, element, finalText });
      counter.start(() => { element.textContent = finalText; });
    }
  }
  window.TrovAdsMotion = { mount };
})();
