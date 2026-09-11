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
    const img = byId("atlasAvatarAnimeImg");
    if (img) {
      const isPoke = v.acao_pet === 'POKE' || v.modo === 'REAGINDO';
      const isSit = v.acao_pet === 'SIT';
      const target = isPoke ? '/assets/atlas-pet-poke.png' : (isSit ? '/assets/atlas-pet-sitting.png' : '/assets/atlas-pet-standing.png');
      if (img.getAttribute('href') !== target) {
        img.setAttribute('href', target);
      }
    }
  }

  let currentIntentHeadline = null;

  function renderMeta(v, pixiReady) {
    byId("avatarMode").textContent = v.modo;
    byId("avatarExpression").textContent = v.expressao;
    byId("avatarFocus").textContent = v.foco_visual;
    byId("avatarIntensity").textContent = `${Math.round(v.intensidade_expressao * 100)}%`;
    byId("avatarHeadline").textContent = currentIntentHeadline || `Atlas \u00b7 ${v.modo.charAt(0) + v.modo.slice(1).toLowerCase()}`;
    const hostErr = byId("atlasPixiStage")?.dataset?.rendererError;
    byId("avatarSource").textContent = v.source === "fallback"
      ? "fallback neutro \u00b7 fonte visual ainda indispon\u00edvel"
      : `EstadoVisualAtlas v1.1 \u00b7 ${pixiReady ? "PixiJS" : (hostErr ? "fallback SVG (" + hostErr + ")" : "fallback SVG")}`;
    toggleFlag("flagListening", v.ouvindo);
    toggleFlag("flagThinking", v.pensando);
    toggleFlag("flagSpeaking", v.falando);
    toggleFlag("flagIdentity", v.duvida_identidade);
  }

  let lastIntentBehaviorKey = null;
  let lastIntentBehaviorEngine = null;

  function intentTarget(intent) {
    const subject = String(intent?.assunto_id || "").toLowerCase();
    const entity = String(intent?.entidade_id || "").toLowerCase();
    if (["core", "x99", "pentium"].includes(entity) || /core|x99|pentium/.test(subject)) return "services";
    return "activity";
  }

  function projectIntentBehavior(intentState) {
    const payload = intentState && typeof intentState === "object" ? intentState : {};
    const intent = payload.intent && typeof payload.intent === "object" ? payload.intent : null;
    if (!intent) return Object.freeze({key:"none", clear:true, returnToPatrol:true});
    const state = String(intent.estado || "").toUpperCase();
    const key = `${intent.intencao_id || "unknown"}:${state}`;
    if (state === "ATIVA") return Object.freeze({key,target:intentTarget(intent),petMode:"SIT",visual:{expressao:"ATENTO",gesto_atual:"ESCUTA",postura_atual:"ATENTO",velocidade_movimento:.22,intensidade_movimento:.30}});
    if (state === "AGUARDANDO") return Object.freeze({key,target:"chat",petMode:"SIT",visual:{expressao:"ENGAJADO",gesto_atual:"ESCUTA",postura_atual:"ABERTO",velocidade_movimento:.12,intensidade_movimento:.18}});
    if (state === "CONCLUIDA") return Object.freeze({key,target:intentTarget(intent),petMode:"SIT",oneShot:true,durationMs:1600,returnToPatrol:true,visual:{expressao:"RECUPERANDO",gesto_atual:"ALIVIO",postura_atual:"ABERTO",velocidade_movimento:.28,intensidade_movimento:.42}});
    return Object.freeze({key,clear:true,returnToPatrol:true});
  }

  function applyIntentBehavior(targetEngine, intentState) {
    if (!targetEngine || typeof targetEngine.applyIntentBehavior !== "function") return false;
    const projection = projectIntentBehavior(intentState);
    if (targetEngine === lastIntentBehaviorEngine && projection.key === lastIntentBehaviorKey) return false;
    try {
      targetEngine.applyIntentBehavior(projection);
    } catch (error) {
      console.warn("[applyIntentBehavior] overlay failed:", error);
      return false;
    }
    lastIntentBehaviorEngine = targetEngine; lastIntentBehaviorKey = projection.key;
    return true;
  }

  function renderIntent(intentState) {
    const payload = intentState && typeof intentState === "object" ? intentState : {};
    const intent = payload.intent && typeof payload.intent === "object" ? payload.intent : null;
    const state = String(intent?.estado || "").toUpperCase();
    const subject = String(intent?.assunto_id || intent?.entidade_id || "");
    const labels = {ATIVA: "ACOMPANHANDO", AGUARDANDO: "AGUARDANDO VOCÊ", CONCLUIDA: "RECUPERADO", CANCELADA: "ENCERRADO", EXPIRADA: "EXPIRADO"};
    const intentHeadline = intent ? `${labels[state] || state || "OBSERVANDO"}${subject ? " · " + subject : ""}` : "OBSERVANDO";
    const headline = byId("avatarHeadline");
    currentIntentHeadline = `Atlas · ${intentHeadline}`;
    if (headline) headline.textContent = currentIntentHeadline;
    toggleFlag("flagTracking", state === "ATIVA");
    toggleFlag("flagWaitingHuman", state === "AGUARDANDO");
    applyIntentBehavior(engine, intentState);
    return intentHeadline;
  }

  let engine = null;
  let initPromise = null;

  function ensureEngine() {
    if (engine?.ready) return Promise.resolve(true);
    if (initPromise) return initPromise;
    const host = byId("atlasPixiStage");
    const Engine = window.AtlasAvatarEngine?.AtlasAvatarEngine;
    if (!host || !Engine) return Promise.resolve(false);
    engine = new Engine(host);
    initPromise = engine.init().then(ready => {
      if (!ready) initPromise = null;
      return ready;
    }).catch(err => {
      console.warn("[ensureEngine] engine.init failed:", err);
      initPromise = null;
      return false;
    });
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
    renderIntent,
    projectIntentBehavior,
    applyIntentBehavior,
    normalize,
    settleVisualState,
    resetTransitionState,
    ensureEngine,
    getEngine: () => engine,
  });
})();
