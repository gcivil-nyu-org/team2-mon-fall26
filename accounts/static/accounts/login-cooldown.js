(() => {
  const notice = document.getElementById("login-cooldown");
  if (!notice) return;
  const button = document.getElementById(notice.dataset.form)?.querySelector('[type="submit"]');
  if (!button) return;
  const remaining = notice.querySelector("[data-remaining]");
  const deadline = Date.now() + Number(notice.dataset.seconds) * 1000;
  button.disabled = true;
  const timer = window.setInterval(() => {
    const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    if (remaining.textContent !== String(seconds)) remaining.textContent = String(seconds);
    if (seconds === 0) {
      window.clearInterval(timer);
      button.disabled = false;
      notice.setAttribute("role", "status");
      notice.textContent = "You can log in now.";
    }
  }, 250);
})();
