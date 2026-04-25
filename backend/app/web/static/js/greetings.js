(() => {
  function setStatus(root, text) {
    const el = root.querySelector(".gtext-copy-status");
    if (!el) return;
    el.textContent = text;
    if (text) {
      window.setTimeout(() => {
        if (el.textContent === text) el.textContent = "";
      }, 1800);
    }
  }

  async function copyText(root, targetId) {
    const target = document.getElementById(targetId);
    if (!target) {
      setStatus(root, "Не найден текст");
      return;
    }
    const text = target.textContent || "";
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        setStatus(root, "Скопировано");
        return;
      }
    } catch (_) {
      // fall back
    }

    // Fallback for older browsers / non-secure contexts
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "true");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      setStatus(root, "Скопировано");
    } catch (_) {
      setStatus(root, "Не удалось скопировать");
    } finally {
      document.body.removeChild(ta);
    }
  }

  document.addEventListener("click", (e) => {
    const btn = e.target && e.target.closest ? e.target.closest("[data-copy-target]") : null;
    if (!btn) return;
    const root = btn.closest(".gtext");
    if (!root) return;
    const targetId = btn.getAttribute("data-copy-target");
    if (!targetId) return;
    copyText(root, targetId);
  });
})();

