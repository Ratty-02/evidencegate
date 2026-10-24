(function () {
  document.documentElement.classList.add('js');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Scroll progress bar
  var bar = document.getElementById('scroll-progress');
  function onScroll() {
    if (!bar) return;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.transform = 'scaleX(' + (max > 0 ? window.scrollY / max : 0) + ')';
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // Reveal elements on scroll
  var items = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add('in'); });
  }

  // Count-up numbers
  document.querySelectorAll('[data-count]').forEach(function (el) {
    var target = parseFloat(el.getAttribute('data-count')) || 0;
    if (reduce || target === 0) { el.textContent = target; return; }
    var start = null;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / 900, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });

  // Gauges fill to their value
  document.querySelectorAll('.gauge[data-value]').forEach(function (el) {
    var v = el.getAttribute('data-value');
    requestAnimationFrame(function () { el.style.setProperty('--v', v); });
  });

  // Loading state on forms with data-loading
  document.querySelectorAll('form[data-loading]').forEach(function (form) {
    form.addEventListener('submit', function () {
      var btn = form.querySelector('button');
      if (!btn) return;
      btn.disabled = true;
      btn.classList.add('is-loading');
      btn.textContent = form.getAttribute('data-loading');
    });
  });

  // Slide to approve: submit only when the track is almost fully slid
  document.querySelectorAll('[data-slide-form]').forEach(function (form) {
    var input = form.querySelector('[data-slide]');
    if (!input) return;
    function paint() { input.style.setProperty('--fill', input.value + '%'); }
    input.addEventListener('input', paint);
    input.addEventListener('change', function () {
      if (Number(input.value) >= 96) {
        input.disabled = true;
        if (form.requestSubmit) form.requestSubmit(); else form.submit();
      } else {
        input.value = 0;
        paint();
      }
    });
    paint();
  });

  // Burst of particles when an approval lands
  document.querySelectorAll('[data-burst]').forEach(function (host) {
    if (reduce) return;
    for (var i = 0; i < 18; i++) {
      var dot = document.createElement('span');
      var angle = (i / 18) * Math.PI * 2;
      var dist = 70 + (i % 3) * 18;
      dot.style.setProperty('--x', Math.cos(angle) * dist + 'px');
      dot.style.setProperty('--y', Math.sin(angle) * dist + 'px');
      dot.style.animationDelay = (i % 4) * 0.03 + 's';
      if (i % 2) dot.style.background = 'var(--green)';
      host.appendChild(dot);
    }
  });
})();

// Confirmation toasts fade out on their own
(function () {
  var toast = document.querySelector('[data-toast]');
  if (!toast) return;
  setTimeout(function () { toast.classList.add('out'); }, 3800);
})();
