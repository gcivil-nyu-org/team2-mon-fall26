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
  for (const select of form.querySelectorAll("select[data-autosubmit]")) {
    select.addEventListener("change", () => form.requestSubmit());
  }
})();
