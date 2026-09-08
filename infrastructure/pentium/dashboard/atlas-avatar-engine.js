(() => {
  "use strict";

  const MODES = new Set(["OCIOSO", "OBSERVANDO", "CONVERSANDO", "REAGINDO"]);
  const EXPRESSIONS = new Set(["SERENO", "ENGAJADO", "CURIOSO", "ATENTO", "PREOCUPADO", "SOB_PRESSAO", "RECUPERANDO"]);
  const POLICY = Object.freeze({
    defaultTransitionMs: 400,
    criticalTransitionMs: 160,
    minArchetypeDwellMs: 1200,
  });

  class AtlasAvatarEngine {
    constructor(host) {
      this.host = host;
      this.ready = false;
      this.state = null;
      this.app = null;
      this.rig = null;
      this.startedAt = performance.now();
      this.reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
      this.hidden = document.hidden;
      document.addEventListener("visibilitychange", () => { this.hidden = document.hidden; });
    }

    async init() {
      if (!this.host || !window.PIXI) return false;
      try {
        const app = new PIXI.Application();
        await app.init({ resizeTo: this.host, backgroundAlpha: 0, antialias: true, autoDensity: true });
        this.host.replaceChildren(app.canvas);
        this.app = app;
        this.rig = this.#buildRig();
        app.stage.addChild(this.rig.root);
        app.ticker.add(ticker => this.#tick(ticker.deltaMS));
        this.host.classList.add("pixi-ready");
        this.ready = true;
        return true;
      } catch (error) {
        this.host.dataset.rendererError = error?.name || "PixiInitError";
        return false;
      }
    }

    render(state) {
      if (!this.ready || !state || !MODES.has(state.modo) || !EXPRESSIONS.has(state.expressao)) return false;
      this.state = state;
      this.#applyState();
      return true;
    }

    #buildRig() {
      const root = new PIXI.Container();
      root.position.set(170, 310);
      const body = new PIXI.Graphics().roundRect(-52, -112, 104, 150, 28).fill(0x14253f).stroke({ color: 0x273d60, width: 3 });
      const shirt = new PIXI.Graphics().poly([-28,-95, 28,-95, 42,15, -42,15]).fill(0xf2f4f8);
      const hairBack = new PIXI.Graphics().ellipse(0, -154, 74, 92).fill(0x49376e).stroke({ color: 0x7d61ad, width: 3 });
      const head = new PIXI.Container();
      head.position.set(0, -155);
      const face = new PIXI.Graphics().ellipse(0, 0, 55, 67).fill(0xf0d4c6);
      const fringe = new PIXI.Graphics().poly([-52,-18,-38,-55,-4,-68,30,-58,52,-22,28,-40,4,-50,-18,-35]).fill(0x5a4380);
      const eyeL = new PIXI.Container(); eyeL.position.set(-19, -4);
      const eyeR = new PIXI.Container(); eyeR.position.set(19, -4);
      for (const eye of [eyeL, eyeR]) {
        eye.addChild(new PIXI.Graphics().ellipse(0, 0, 10, 7).fill(0xf8ffff));
        const iris = new PIXI.Graphics().circle(0, 0, 5).fill(0x43d17d);
        iris.name = "iris";
        eye.addChild(iris);
      }
      const mouth = new PIXI.Graphics().roundRect(-12, 23, 24, 4, 2).fill(0x9a5662);
      const browL = new PIXI.Graphics().roundRect(-30, -22, 21, 3, 2).fill(0x4a3658);
      const browR = new PIXI.Graphics().roundRect(9, -22, 21, 3, 2).fill(0x4a3658);
      head.addChild(face, fringe, browL, browR, eyeL, eyeR, mouth);

      const armL = new PIXI.Container(); armL.position.set(-49, -82); armL.pivot.set(0, 0);
      armL.addChild(new PIXI.Graphics().roundRect(-15, 0, 25, 105, 12).fill(0x14253f));
      const armR = new PIXI.Container(); armR.position.set(49, -82); armR.pivot.set(0, 0);
      armR.addChild(new PIXI.Graphics().roundRect(-10, 0, 25, 105, 12).fill(0x14253f));
      root.addChild(hairBack, body, shirt, armL, armR, head);
      return { root, head, eyeL, eyeR, mouth, browL, browR, armL, armR };
    }

    #applyState() {
      const s = this.state;
      const r = this.rig;
      const intensity = s.intensidade_expressao;
      const look = s.direcao_olhar || "centro";
      const lookX = look === "esquerda" ? -3 : look === "direita" ? 3 : 0;
      const lookY = look === "cima" ? -2 : look === "baixo" ? 2 : 0;
      for (const eye of [r.eyeL, r.eyeR]) eye.getChildByName("iris").position.set(lookX, lookY);
      r.head.rotation = s.expressao === "CURIOSO" || s.duvida_identidade ? 0.08 + intensity * 0.06 : 0;
      r.armL.rotation = s.gesto_atual === "ACENO" ? -0.72 : s.gesto_atual === "DUVIDA" ? -0.28 : 0.08;
      r.armR.rotation = s.gesto_atual === "ESCUTA" ? 0.48 : s.gesto_atual === "ABERTO" ? 0.22 : -0.08;
      r.mouth.scale.y = s.falando ? 2.4 : (s.expressao === "SERENO" || s.expressao === "RECUPERANDO" ? 0.7 : 1);
      const pressure = s.expressao === "SOB_PRESSAO" || s.expressao === "PREOCUPADO";
      r.browL.rotation = pressure ? -0.12 : 0;
      r.browR.rotation = pressure ? 0.12 : 0;
      r.root.scale.set(s.modo === "REAGINDO" ? 1.025 : 1);
    }

    #tick(deltaMs) {
      if (!this.ready || !this.state || this.hidden) return;
      const s = this.state;
      const motion = this.reducedMotion ? 0 : s.intensidade_movimento;
      const t = (performance.now() - this.startedAt) / 1000;
      const idle = s.modo === "OCIOSO" ? Math.sin(t * (0.8 + s.velocidade_movimento)) * 2.5 * motion : 0;
      this.rig.root.y = 310 + idle;
      if (s.falando && motion > 0) this.rig.mouth.scale.y = 1.2 + Math.abs(Math.sin(t * 9)) * 1.6;
      const blink = !this.reducedMotion && (Math.floor(t * 10) % 43 === 0);
      this.rig.eyeL.scale.y = blink ? 0.15 : 1;
      this.rig.eyeR.scale.y = blink ? 0.15 : 1;
      void deltaMs;
    }
  }

  window.AtlasAvatarEngine = Object.freeze({ AtlasAvatarEngine, POLICY, MODES, EXPRESSIONS });
})();
