/** Mark active link in floating nav based on current page */
(function () {
  const page = document.body.dataset.page;
  if (!page) return;
  document.querySelectorAll(".nav-links a[data-nav]").forEach((a) => {
    if (a.dataset.nav === page) a.classList.add("active");
  });
})();
