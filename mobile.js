(function () {
  try {
    var LC = window.LightweightCharts;
    if (LC && LC.createChart) {
      var orig = LC.createChart.bind(LC);
      LC.createChart = function (el, opts) {
        opts = Object.assign({}, opts || {});
        opts.handleScroll = { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false };
        opts.handleScale = { mouseWheel: true, pinch: true, axisPressedMouseMove: { time: true, price: false } };
        if (window.matchMedia("(max-width: 880px)").matches) {
          opts.layout = Object.assign({}, opts.layout, { fontSize: 10 });
        }
        return orig(el, opts);
      };
    }
  } catch (e) { console.warn("mobile chart tweak skipped", e); }

  document.addEventListener("DOMContentLoaded", function () {
    var links = Array.prototype.slice.call(document.querySelectorAll(".mnav a"));
    if (!links.length || !("IntersectionObserver" in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id); });
      });
    }, { rootMargin: "-40% 0px -55% 0px" });
    links.forEach(function (a) {
      var s = document.querySelector(a.getAttribute("href"));
      if (s) io.observe(s);
    });
  });
})();
