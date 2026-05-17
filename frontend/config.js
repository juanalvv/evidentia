/** API base URL — Person B sets this on Brev; empty = same origin */
window.EVIDENTIA_API =
  window.EVIDENTIA_API ||
  ((location.hostname === "localhost" || location.hostname === "127.0.0.1") &&
  location.port === "8080"
    ? "http://localhost:8000"
    : "");

/** Mock mode: load fixture without backend */
window.EVIDENTIA_USE_MOCK = false;
