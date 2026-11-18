// Shared page behaviour for every Basera page (loaded from base.html).

// 1. Scroll motion: writes the scroll distance (capped) into the
//    --basera-scroll CSS variable. basera.css uses it to move the background,
//    welcome copy and login box at slightly different speeds (parallax).
(function () {
  var root = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var MAX_SCROLL = 240;
  var ticking = false;

  function update() {
    var y = reduceMotion.matches ? 0 : Math.min(Math.max(window.scrollY, 0), MAX_SCROLL);
    root.style.setProperty("--basera-scroll", y.toFixed(1));
    ticking = false;
  }

  window.addEventListener("scroll", function () {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(update);
    }
  }, { passive: true });

  reduceMotion.addEventListener("change", update);
  update();
})();

// 2. Loading state on the primary button while a form is submitting.
//    Add data-loading-text="..." to any .basera-btn-primary submit button to use it.
document.querySelectorAll("form").forEach(function (form) {
  var button = form.querySelector(".basera-btn-primary[data-loading-text]");
  if (!button) return;
  var label = button.querySelector(".basera-btn-primary__label") || button;
  var original = label.textContent;

  form.addEventListener("submit", function () {
    button.classList.add("is-loading");
    button.setAttribute("aria-busy", "true");
    label.textContent = button.dataset.loadingText;
  });

  // Reset if the user comes back with the browser's Back button
  window.addEventListener("pageshow", function () {
    button.classList.remove("is-loading");
    button.removeAttribute("aria-busy");
    label.textContent = original;
  });
});
