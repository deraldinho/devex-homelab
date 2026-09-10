(() => {
  "use strict";

  const byId = id => document.getElementById(id);
  const clamp = (value, min, max, fallback) => {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(min, Math.min(max, number)) : fallback;
  };

  function normalize(visual) {
    const v = visual || {};
    return {
      ...v,
      modo: String(v.modo || "OCIOSO").toUpperCase(),
      expressao: String(v.expressao || "SERENO").toUpperCase(),
      intensidade_expressao: clamp(v.intensidade_expressao, 0, 1, 0.25),
      velocidade_movimento: clamp(v.velocidade_movimento, 0, 1, 0.35),
      intensidade_movimento: clamp(v.intensidade_movimento, 0, 1, 0.25),
      transicao_ms: clamp(v.transicao_ms, 120, 1500, 400),
      foco_visual: v.foco_visual || "neutro",
      direcao_olhar: v.direcao_olhar || "centro",
      gesto_atual: v.gesto_atual || "nenhum",
      falando: Boolean(v.falando), ouvindo: Boolean(v.ouvindo), pensando: Boolean(v.pensando),
      duvida_identidade: Boolean(v.duvida_identidade),
    };
  }

  let engine = null;
  let initPromise = null;

  function ensureEngine() {
    if (engine?.ready) return Promise.resolve(engine);
    if (initPromise) return initPromise;
    const host = byId("atlasPixiStage");
    if (!window.AtlasAvatarEngine || !host) return Promise.resolve(null);
    engine = new window.AtlasAvatarEngine(host);
    initPromise = engine.init().then(ok => ok ? engine : null).catch(() => null);
    return initPromise;
  }

  function renderSvg(v) {
    const avatar = byId("atlasAvatar");
    if (!avatar) return;
    avatar.dataset.mode = v.modo;
    avatar.dataset.expression = v.expressao;
    avatar.classList.toggle("listening", v.ouvindo);
    avatar.classList.toggle("thinking", v.pensando);
    avatar.classList.toggle("speaking", v.falando);
  }

  function toggleFlag(id, on) {
    const element = byId(id);
    if (element) element.classList.toggle("on", Boolean(on));
  }

  function renderMeta(v) {
    byId("avatarMode").textContent = v.modo;
    byId("avatarExpression").textContent = v.expressao;
    byId("avatarFocus").textContent = v.foco_visual;
    byId("avatarIntensity").textContent = `${Math.round(v.intensidade_expressao * 100)}%`;
    byId("avatarHeadline").textContent = `Atlas \u00b7 ${v.modo.charAt(0) + v.modo.slice(1).toLowerCase()}`;
    byId("avatarSource").textContent = v.source === "fallback"
      ? "fallback neutro \u00b7 fonte visual ainda indispon\u00edvel"
      : "EstadoVisualAtlas v1.1 \u00b7 fonte can\u00f4nica";
    toggleFlag("flagListening", v.ouvindo);
    toggleFlag("flagThinking", v.pensando);
    toggleFlag("flagSpeaking", v.falando);
    toggleFlag("flagIdentity", v.duvida_identidade);
  }

  function render(visual) {
    const v = normalize(visual);
    renderMeta(v);
    renderSvg(v);
    ensureEngine().then(active => active?.render(v));
    return v;
  }

  window.AtlasAvatarRenderer = Object.freeze({ render, normalize });
})();
