(() => {
  "use strict";

  // Without JavaScript the Search button applies the filters. With it, picking
  // a dropdown value applies that filter straight away.
  const form = document.getElementById("hotspot-filters");
  if (!form) return;
  // Leave blank fields out of the URL so links stay short and shareable.
  form.addEventListener("formdata", (event) => {
    for (const [name, value] of [...event.formData.entries()]) {
      if (!String(value).trim()) event.formData.delete(name);
    }
  });
  const nearInput = document.getElementById("filter-near");
  const sortSelect = document.getElementById("filter-sort");
  const nearButton = document.querySelector("[data-near-me]");
  const nearStatus = document.getElementById("near-me-status");

  function showNearStatus(message) {
    if (!nearStatus) return;
    nearStatus.textContent = message;
    nearStatus.hidden = false;
  }

  // "Near me": ask the browser for the visitor's location, then reload the results
  // sorted by distance. The results URL includes the rounded coordinates.
  function locate() {
    if (!navigator.geolocation || !window.isSecureContext) {
      showNearStatus("Your browser can't share your location on this page. Search by neighborhood or ZIP code instead.");
      return;
    }
    if (nearButton) nearButton.setAttribute("aria-busy", "true");
    showNearStatus("Finding your location… The results URL will include your rounded coordinates.");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        nearInput.value = `${position.coords.latitude.toFixed(4)},${position.coords.longitude.toFixed(4)}`;
        if (sortSelect) sortSelect.value = "nearest";
        form.requestSubmit();
      },
      (error) => {
        if (nearButton) nearButton.removeAttribute("aria-busy");
        if (sortSelect && sortSelect.value === "nearest" && !nearInput.value) sortSelect.value = "";
        showNearStatus(
          error.code === error.PERMISSION_DENIED
            ? "Location access is blocked. Allow it for this site in your browser, or search by neighborhood or ZIP code instead."
            : "We couldn't find your location. Try again, or search by neighborhood or ZIP code instead.",
        );
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  }

  if (nearButton && nearInput) nearButton.addEventListener("click", locate);
  for (const select of form.querySelectorAll("select[data-autosubmit]")) {
    select.addEventListener("change", () => {
      // Sorting by distance needs a location first.
      if (select === sortSelect && select.value === "nearest" && nearInput && !nearInput.value) {
        locate();
        return;
      }
      form.requestSubmit();
    });
  }
})();
