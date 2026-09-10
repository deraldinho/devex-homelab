(() => {
  "use strict";

  const MODES = new Set(["OCIOSO", "OBSERVANDO", "CONVERSANDO", "REAGINDO"]);
  const ARCHETYPES = new Set(["SERENO", "ENGAJADO", "CURIOSO", "ATENTO", "PREOCUPADO", "SOB_PRESSAO", "RECUPERANDO"]);

  class AtlasAvatarEngine {
    constructor(host) {
      this.host = host;
      this.app = null;
      this.root = null;
      this.parts = {};
      this.state = null;
      this.ready = false;
      this.phase = 0;
      this.reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
      this.hidden = document.hidden;
      document.addEventListener("visibilitychange", () => { this.hidden = document.hidden; });
    }

    async init() {
      if (this.ready) return true;
      if (!window.PIXI || !this.host) return false;
      try {
        this.app = new PIXI.Application();
        await this.app.init({ resizeTo: this.host, backgroundAlpha: 0, antialias: true, autoDensity: true });
        this.host.appendChild(this.app.canvas);
        this.buildRig();
        this.app.ticker.add(ticker => this.tick(ticker.deltaMS));
        this.ready = true;
        this.host.classList.add("pixi-ready");
        return true;
      } catch (error) {
        console.warn("Atlas Pixi fallback", error?.name || "init_error");
        return false;
      }
    }

    buildRig() {
      const root = new PIXI.Container();
      root.position.set(150, 30);
      this.app.stage.addChild(root);
      this.root = root;

      const hairBack = new PIXI.Graphics().ellipse(0, 130, 92, 138).fill(0x49376e);
      const torso = new PIXI.Graphics().roundRect(-66, 205, 132, 122, 36).fill(0x14253f);
      const shirt = new PIXI.Graphics().poly([-28, 205, 28, 205, 46, 318, -46, 318]).fill(0xf2f4f8);
      const leftArm = new PIXI.Container();
      const rightArm = new PIXI.Container();
      leftArm.position.set(-58, 222); rightArm.position.set(58, 222);
      leftArm.addChild(new PIXI.Graphics().roundRect(-16, 0, 30, 105, 14).fill(0x14253f));
      rightArm.addChild(new PIXI.Graphics().roundRect(-14, 0, 30, 105, 14).fill(0x14253f));

      const head = new PIXI.Container();
      head.position.set(0, 118);
      const face = new PIXI.Graphics().ellipse(0, 0, 61, 74).fill(0xf0d4c6);
      const hairFront = new PIXI.Graphics().arc(0, -7, 66, Math.PI, Math.PI * 2).lineTo(56, -28).fill(0x5a4380);
      const leftEye = this.makeEye(-22, 5);
      const rightEye = this.makeEye(22, 5);
      const mouth = new PIXI.Graphics().roundRect(-14, 38, 28, 5, 3).fill(0x9a5662);
      head.addChild(face, hairFront, leftEye, rightEye, mouth);
      root.addChild(hairBack, torso, shirt, leftArm, rightArm, head);
      this.parts = { torso, leftArm, rightArm, head, leftEye, rightEye, mouth };
    }

    makeEye(x, y) {
      const eye = new PIXI.Container();
      eye.position.set(x, y);
      const white = new PIXI.Graphics().ellipse(0, 0, 11, 8).fill(0xf8ffff);
      const iris = new PIXI.Graphics().circle(0, 0, 5).fill(0x43d17d);
      const pupil = new PIXI.Graphics().circle(0, 0, 2).fill(0x0b1612);
      eye.addChild(white, iris, pupil);
      eye.iris = iris;
      eye.pupil = pupil;
      return eye;
    }

    render(state) {
      this.state = state;
      if (!this.ready) return;
      const mode = MODES.has(state.modo) ? state.modo : "OCIOSO";
      const expression = ARCHETYPES.has(state.expressao) ? state.expressao : "SERENO";
      const intensity = state.intensidade_expressao;
      const look = this.lookVector(state.direcao_olhar || state.foco_visual);
      for (const eye of [this.parts.leftEye, this.parts.rightEye]) {
        eye.iris.position.set(look.x * 3, look.y * 2);
        eye.pupil.position.set(look.x * 3, look.y * 2);
      }
      this.applyExpression(expression, intensity);
      this.applyPose(mode, state.gesto_atual, intensity);
    }

    lookVector(direction) {
      const value = String(direction || "neutro").toLowerCase();
      if (value.includes("esquer")) return { x: -1, y: 0 };
      if (value.includes("direit")) return { x: 1, y: 0 };
      if (value.includes("cima")) return { x: 0, y: -1 };
      if (value.includes("baixo")) return { x: 0, y: 1 };
      return { x: 0, y: 0 };
    }

    applyExpression(expression, intensity) {
      const head = this.parts.head;
      const mouth = this.parts.mouth;
      head.rotation = expression === "CURIOSO" ? 0.05 * intensity : expression === "PREOCUPADO" ? -0.025 * intensity : 0;
      mouth.scale.y = this.state?.falando ? 1.8 : 1;
      mouth.rotation = expression === "SERENO" || expression === "RECUPERANDO" ? -0.03 : expression === "SOB_PRESSAO" ? 0.03 : 0;
      const eyeScale = expression === "CURIOSO" || expression === "ATENTO" ? 1 + 0.08 * intensity : 1;
      this.parts.leftEye.scale.set(eyeScale);
      this.parts.rightEye.scale.set(eyeScale);
    }

    applyPose(mode, gesture, intensity) {
      const leftArm = this.parts.leftArm;
      const rightArm = this.parts.rightArm;
      leftArm.rotation = mode === "CONVERSANDO" ? 0.12 : 0;
      rightArm.rotation = mode === "OBSERVANDO" ? -0.08 : 0;
      if (gesture === "ACENO" || gesture === "aceno") rightArm.rotation = -0.75;
      if (gesture === "DUVIDA" || gesture === "duvida") this.parts.head.rotation += 0.08;
      if (mode === "REAGINDO") { leftArm.rotation -= 0.18 * intensity; rightArm.rotation += 0.18 * intensity; }
    }

    tick(deltaMS) {
      if (!this.ready || !this.state || this.hidden) return;
      const motion = this.reducedMotion ? 0 : this.state.intensidade_movimento * this.state.velocidade_movimento;
      this.phase += deltaMS * 0.001 * (0.4 + motion);
      const idle = this.state.modo === "OCIOSO" ? Math.sin(this.phase * 1.7) * 2 * motion : 0;
      this.root.y = 30 + idle;
      if (this.state.falando && !this.reducedMotion) {
        this.parts.mouth.scale.y = 1 + Math.abs(Math.sin(this.phase * 8)) * 1.4;
      }
      if (!this.reducedMotion && Math.sin(this.phase * 0.55) > 0.995) {
        this.parts.leftEye.scale.y = 0.12;
        this.parts.rightEye.scale.y = 0.12;
      }
    }
  }

  window.AtlasAvatarEngine = AtlasAvatarEngine;
})();
