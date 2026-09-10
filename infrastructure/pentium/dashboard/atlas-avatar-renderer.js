(() => {
  "use strict";

  const MODES = new Set(["OCIOSO", "OBSERVANDO", "CONVERSANDO", "REAGINDO"]);
  const EXPRESSIONS = new Set(["SERENO", "ENGAJADO", "CURIOSO", "ATENTO", "PREOCUPADO", "SOB_PRESSAO", "RECUPERANDO"]);
  const MIN_ARCHETYPE_DWELL_MS = 1200;
  const clamp01 = value => Math.max(0, Math.min(1, Number(value) || 0));
  const clampMs = value => Math.max(120, Math.min(1500, Number(value) || 400));
  const byId = id => document.getElementById(id);
  const toggleFlag = (id, on) => byId(id)?.classList.toggle("on", Boolean(on));

  function normalize(visual) {
    const v = visual && typeof visual === "object" ? visual : {};
    const mode = String(v.modo || "OCIOSO").toUpperCase();
    const expression = String(v.expressao || "SERENO").toUpperCase();
    return Object.freeze({
      modo: MODES.has(mode) ? mode : "OCIOSO",
      expressao: EXPRESSIONS.has(expression) ? expression : "SERENO",
      intensidade_expressao: clamp01(v.intensidade_expressao),
      foco_visual: String(v.foco_visual || "neutro"),
      direcao_olhar: String(v.direcao_olhar || "centro").toLowerCase(),
      gesto_atual: String(v.gesto_atual || "NENHUM").toUpperCase(),
      velocidade_movimento: clamp01(v.velocidade_movimento),
      intensidade_movimento: clamp01(v.intensidade_movimento),
      falando: Boolean(v.falando),
      ouvindo: Boolean(v.ouvindo),
      pensando: Boolean(v.pensando),
      duvida_identidade: Boolean(v.duvida_identidade),
      transicao_ms: clampMs(v.transicao_ms),
      source: v.source === "fallback" ? "fallback" : "canonical",
    });
  }

  let transitionState = null;

  function isCriticalTransition(v) {
    return v.modo === "REAGINDO" || v.expressao === "SOB_PRESSAO";
  }

  function settleVisualState(requested, nowMs = performance.now()) {
    if (!transitionState) {
      transitionState = { expression: requested.expressao, changedAt: nowMs };
      return requested;
    }
    if (requested.expressao === transitionState.expression) return requested;
    const dwellMs = nowMs - transitionState.changedAt;
    if (!isCriticalTransition(requested) && dwellMs < MIN_ARCHETYPE_DWELL_MS) {
      return Object.freeze({ ...requested, expressao: transitionState.expression });
    }
    transitionState = { expression: requested.expressao, changedAt: nowMs };
    return requested;
  }

  function resetTransitionState() {
    transitionState = null;
  }

  function renderSvgFallback(v) {
    const avatar = byId("atlasAvatar");
    if (!avatar) return;
    avatar.dataset.mode = v.modo;
    avatar.dataset.expression = v.expressao;
    avatar.classList.toggle("listening", v.ouvindo);
    avatar.classList.toggle("thinking", v.pensando);
    avatar.classList.toggle("speaking", v.falando);
  }

  function renderMeta(v, pixiReady) {
    byId("avatarMode").textContent = v.modo;
    byId("avatarExpression").textContent = v.expressao;
    byId("avatarFocus").textContent = v.foco_visual;
    byId("avatarIntensity").textContent = `${Math.round(v.intensidade_expressao * 100)}%`;
    byId("avatarHeadline").textContent = `Atlas \u00b7 ${v.modo.charAt(0) + v.modo.slice(1).toLowerCase()}`;
    byId("avatarSource").textContent = v.source === "fallback"
      ? "fallback neutro \u00b7 fonte visual ainda indispon\u00edvel"
      : `EstadoVisualAtlas v1.1 \u00b7 ${pixiReady ? "PixiJS" : "fallback SVG"}`;
    toggleFlag("flagListening", v.ouvindo);
    toggleFlag("flagThinking", v.pensando);
    toggleFlag("flagSpeaking", v.falando);
    toggleFlag("flagIdentity", v.duvida_identidade);
  }

  let engine = null;
  let initPromise = null;

  function ensureEngine() {
    if (initPromise) return initPromise;
    const host = byId("atlasPixiStage");
    const Engine = window.AtlasAvatarEngine?.AtlasAvatarEngine;
    if (!host || !Engine) return Promise.resolve(false);
    engine = new Engine(host);
    initPromise = engine.init().catch(() => false);
    return initPromise;
  }

  function render(visual) {
    const v = settleVisualState(normalize(visual));
    renderSvgFallback(v);
    const pixiReady = Boolean(engine?.ready && engine.render(v));
    renderMeta(v, pixiReady);
    if (!pixiReady) {
      ensureEngine().then(ready => {
        if (ready && engine.render(v)) renderMeta(v, true);
      });
    }
    return v;
  }

  window.AtlasAvatarRenderer = Object.freeze({
    render,
    normalize,
    settleVisualState,
    resetTransitionState,
    ensureEngine,
    getEngine: () => engine,
  });
})();
