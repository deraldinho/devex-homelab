(() => {
  "use strict";

  const byId = id => document.getElementById(id);
  const toggleFlag = (id, on) => byId(id).classList.toggle("on", Boolean(on));

  function render(visual) {
    const v = visual || {};
    const avatar = byId("atlasAvatar");
    const mode = String(v.modo || "OCIOSO").toUpperCase();
    const expression = String(v.expressao || "SERENO").toUpperCase();
    avatar.dataset.mode = mode;
    avatar.dataset.expression = expression;
    avatar.classList.toggle("listening", Boolean(v.ouvindo));
    avatar.classList.toggle("thinking", Boolean(v.pensando));
    avatar.classList.toggle("speaking", Boolean(v.falando));
    byId("avatarMode").textContent = mode;
    byId("avatarExpression").textContent = expression;
    byId("avatarFocus").textContent = v.foco_visual || "neutro";
    const intensity = Math.round(Math.max(0, Math.min(1, Number(v.intensidade_expressao) || 0)) * 100);
    byId("avatarIntensity").textContent = `${intensity}%`;
    byId("avatarHeadline").textContent = `Atlas \u00b7 ${mode.charAt(0) + mode.slice(1).toLowerCase()}`;
    byId("avatarSource").textContent = v.source === "fallback"
      ? "fallback neutro \u00b7 fonte visual ainda indispon\u00edvel"
      : "EstadoVisualAtlas v1 \u00b7 fonte can\u00f4nica";
    toggleFlag("flagListening", v.ouvindo);
    toggleFlag("flagThinking", v.pensando);
    toggleFlag("flagSpeaking", v.falando);
    toggleFlag("flagIdentity", v.duvida_identidade);
  }

  window.AtlasAvatarRenderer = Object.freeze({ render });
})();
