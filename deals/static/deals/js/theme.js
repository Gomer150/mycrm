(() => {
  const storageKey = "theme";
  const root = document.documentElement;
  const toggle = document.querySelector("[data-theme-toggle]");
  const modes = ["system", "light", "dark"];
  const labels = {
    system: "Система",
    light: "Светлая",
    dark: "Темная",
  };

  const media = window.matchMedia("(prefers-color-scheme: dark)");

  const getSystemTheme = () => (media.matches ? "dark" : "light");

  const applyTheme = (mode) => {
    const resolved = mode === "system" ? getSystemTheme() : mode;
    if (mode === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", mode);
    }
    root.setAttribute("data-bs-theme", resolved);

    if (toggle) {
      const label = toggle.querySelector(".theme-toggle__label");
      if (label) {
        label.textContent = labels[mode] || "";
      }
      toggle.setAttribute("aria-label", `Тема: ${labels[mode] || ""}`);
    }
  };

  const stored = localStorage.getItem(storageKey) || "system";
  applyTheme(stored);

  if (toggle) {
    toggle.addEventListener("click", () => {
      const current = localStorage.getItem(storageKey) || "system";
      const next = modes[(modes.indexOf(current) + 1) % modes.length];
      localStorage.setItem(storageKey, next);
      applyTheme(next);
    });
  }

  const handleSystemChange = () => {
    const mode = localStorage.getItem(storageKey) || "system";
    if (mode === "system") {
      applyTheme("system");
    }
  };

  if (media.addEventListener) {
    media.addEventListener("change", handleSystemChange);
  } else if (media.addListener) {
    media.addListener(handleSystemChange);
  }
})();
