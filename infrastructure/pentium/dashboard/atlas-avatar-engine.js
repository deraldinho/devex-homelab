(() => {
  "use strict";
  const MODES = new Set(["OCIOSO", "OBSERVANDO", "CONVERSANDO", "REAGINDO"]);
  const EXPRESSIONS = new Set(["SERENO", "ENGAJADO", "CURIOSO", "ATENTO", "PREOCUPADO", "SOB_PRESSAO", "RECUPERANDO"]);
  const POLICY = Object.freeze({ defaultTransitionMs: 400, criticalTransitionMs: 160, minArchetypeDwellMs: 1200 });
  const M = window.AtlasAvatarMotion;

  class AtlasAvatarEngine {
    constructor(host) {
      this.host = host;
      this.ready = false;
      this.state = null;
      this.app = null;
      this.rig = null;
      this.startedAt = performance.now();
      this.motion = M ? new M.MotionState() : null;
      this.reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
      this.hidden = document.hidden;
      document.addEventListener("visibilitychange", () => { this.hidden = document.hidden; });

      // Locomoção Ampla & Patrulha
      this.walkOffset = 0;
      this.walkTargetOffset = 0;
      this.walkDirection = 1;
      this.stepPhase = 0;
      this.walking = true;
      this.patrolLimit = 95; // Amplitude ampla de caminhada
      this.nextPatrolTime = performance.now() + 2000;
      this.zDepth = 0;
      this.targetZDepth = 0;

      // Mouse tracking interativo
      this.mouseTarget = { x: 0, y: 0, active: false };
      this.lastMouseMove = 0;
      this.#initMouseTracking();
    }

    #initMouseTracking() {
      if (!this.host) return;
      const updateMouse = (e) => {
        const rect = this.host.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return;
        const normX = ((e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2));
        const normY = ((e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2));
        this.mouseTarget = {
          x: Math.max(-1, Math.min(1, normX)),
          y: Math.max(-1, Math.min(1, normY)),
          active: true,
        };
        this.lastMouseMove = performance.now();
      };
      this.host.addEventListener("mousemove", updateMouse);
      window.addEventListener("mousemove", (e) => {
        const rect = this.host?.getBoundingClientRect();
        if (!rect) return;
        const dist = Math.hypot(e.clientX - (rect.left + rect.width / 2), e.clientY - (rect.top + rect.height / 2));
        if (dist < 1000) updateMouse(e);
      });
      this.host.addEventListener("mouseleave", () => {
        setTimeout(() => { if (performance.now() - this.lastMouseMove > 2500) this.mouseTarget.active = false; }, 2500);
      });
    }

    async init() {
      if (!this.host || !window.PIXI || !M) return false;
      try {
        const app = new PIXI.Application();
        await app.init({ resizeTo: this.host, backgroundAlpha: 0, antialias: true, autoDensity: true });
        this.host.replaceChildren(app.canvas);
        this.app = app;
        this.rig = this.#buildRig();
        app.stage.addChild(this.rig.root);
        app.ticker.add(t => this.#tick(t.deltaMS));
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

    visitPanel(target) {
      this.walking = true;
      if (target === 'mind' || target === 'cognitionPanel') {
        this.walkTargetOffset = -this.patrolLimit * 0.9;
        this.targetZDepth = -0.12;
        if (this.rig?.hudPanel) this.rig.hudPanel.visible = true;
      } else if (target === 'chat' || target === 'atlasChatPanel') {
        this.walkTargetOffset = this.patrolLimit * 0.9;
        this.targetZDepth = 0.12;
      } else if (target === 'services') {
        this.walkTargetOffset = -this.patrolLimit * 0.45;
        this.targetZDepth = 0.05;
      } else {
        this.walkTargetOffset = 0;
        this.targetZDepth = 0;
      }
    }

    #arm(side) {
      const upper = new PIXI.Container();
      const sign = side === 'L' ? -1 : 1;
      upper.position.set(40 * sign, -78);

      // Ombro e manga estilizada anime
      const sleeve = new PIXI.Graphics();
      sleeve.moveTo(side === 'L' ? -10 : -4, 0)
        .lineTo(side === 'L' ? 8 : 12, 0)
        .quadraticCurveTo(side === 'L' ? 10 : 14, 28, side === 'L' ? 6 : 10, 52)
        .lineTo(side === 'L' ? -12 : -8, 52)
        .quadraticCurveTo(side === 'L' ? -14 : -10, 24, side === 'L' ? -10 : -4, 0)
        .fill(0x132238)
        .stroke({ color: 0x223a5e, width: 2 });
      // Friso luminoso ciano no punho
      sleeve.rect(side === 'L' ? -12 : -8, 48, 18, 3).fill(0x2ee4b0);
      upper.addChild(sleeve);

      // Antebraço esbelto
      const forearm = new PIXI.Container();
      forearm.position.set(side === 'L' ? -2 : 2, 50);
      const armG = new PIXI.Graphics();
      armG.roundRect(-7, 0, 14, 46, 7).fill(0x182c46);
      armG.circle(0, 32, 3.5).fill(0x2ee4b0); // bracelete holográfico
      forearm.addChild(armG);

      // Mão delicada de anime
      const hand = new PIXI.Graphics();
      hand.ellipse(0, 48, 6.5, 9).fill(0xf6ded4);
      hand.ellipse(side === 'L' ? -3 : 3, 46, 2.5, 5).fill(0xf6ded4); // polegar delicado
      forearm.addChild(hand);

      upper.addChild(forearm);
      return { upper, forearm, hand };
    }

    #buildRig() {
      const root = new PIXI.Container();
      root.position.set(170,280);

      // Sombra suave sob os pés
      const shadow = new PIXI.Graphics().ellipse(0, 114, 48, 8).fill({ color: 0x000000, alpha: 0.38 });
      root.addChild(shadow);

      // Pernas esbeltas anime articuladas
      const legL = new PIXI.Container();
      legL.position.set(-16, 26);
      const legLG = new PIXI.Graphics();
      legLG.moveTo(-8, 0).lineTo(8, 0).lineTo(6, 88).lineTo(-7, 88).closePath().fill(0x162033).stroke({ color: 0x243754, width: 1.5 });
      // Bota cyber estilizada com salto sutil
      legLG.roundRect(-9, 86, 20, 22, 6).fill(0x0a0f18);
      legLG.rect(-8, 86, 18, 2.5).fill(0x2ee4b0); // friso ciano
      legL.addChild(legLG);

      const legR = new PIXI.Container();
      legR.position.set(16, 26);
      const legRG = new PIXI.Graphics();
      legRG.moveTo(-8, 0).lineTo(8, 0).lineTo(7, 88).lineTo(-6, 88).closePath().fill(0x162033).stroke({ color: 0x243754, width: 1.5 });
      legRG.roundRect(-11, 86, 20, 22, 6).fill(0x0a0f18);
      legRG.rect(-10, 86, 18, 2.5).fill(0x2ee4b0);
      legR.addChild(legRG);

      // Cabelo Traseiro Anime volumoso, fluido e sedoso
      const hairBack = new PIXI.Container();
      hairBack.position.set(0, -152);
      const hbG = new PIXI.Graphics();
      // Silhueta orgânica curva do cabelo longo anime
      hbG.moveTo(-40, -10)
        .quadraticCurveTo(-75, 20, -72, 85)
        .quadraticCurveTo(-60, 128, -42, 142)
        .quadraticCurveTo(-36, 105, -22, 115)
        .quadraticCurveTo(-8, 148, 0, 136)
        .quadraticCurveTo(8, 148, 22, 115)
        .quadraticCurveTo(36, 105, 42, 142)
        .quadraticCurveTo(60, 128, 72, 85)
        .quadraticCurveTo(75, 20, 40, -10)
        .closePath()
        .fill(0x382452)
        .stroke({ color: 0x583d78, width: 2.5 });
      // Camadas internas de sombra do cabelo
      hbG.moveTo(-35, 25).quadraticCurveTo(-55, 75, -38, 110).quadraticCurveTo(-45, 60, -35, 25).fill(0x2d1c44);
      hbG.moveTo(35, 25).quadraticCurveTo(55, 75, 38, 110).quadraticCurveTo(45, 60, 35, 25).fill(0x2d1c44);
      hairBack.addChild(hbG);

      // Tronco Cyber-Anime elegante e acinturado
      const torso = new PIXI.Container();
      const body = new PIXI.Graphics();
      // Jaqueta obsidian com corte gracioso
      body.moveTo(-38, -102)
        .lineTo(38, -102)
        .quadraticCurveTo(34, -40, 28, 12)
        .lineTo(-28, 12)
        .quadraticCurveTo(-34, -40, -38, -102)
        .closePath()
        .fill(0x131f33)
        .stroke({ color: 0x243958, width: 2.5 });

      // Camisa/colete claro interno
      const shirt = new PIXI.Graphics();
      shirt.moveTo(-18, -92).lineTo(18, -92).lineTo(20, 10).lineTo(-20, 10).closePath().fill(0xf2f6fc);

      // Pescoço gracioso de anime
      const neck = new PIXI.Graphics();
      neck.roundRect(-10, -114, 20, 24, 6).fill(0xf4ded3);

      // Gravata tech e núcleo reator ciano iluminado no peito
      const reactor = new PIXI.Graphics();
      reactor.moveTo(-5, -88).lineTo(5, -88).lineTo(0, -48).closePath().fill(0x1d2c44);
      reactor.circle(0, -42, 8).fill(0x2ee4b0);
      reactor.circle(0, -42, 13).fill({ color: 0x43d17d, alpha: 0.35 });
      reactor.circle(0, -42, 3.5).fill(0xffffff);
      torso.addChild(neck, body, shirt, reactor);

      // Braços articulados
      const L = this.#arm('L');
      const R = this.#arm('R');

      // Cabeça & Rosto Anime Harmonioso
      const head = new PIXI.Container();
      head.position.set(0, -156);

      // Formato facial anime delicado e afilado (curvas suaves, nada de cantos duros)
      const face = new PIXI.Graphics();
      face.moveTo(-45, -30)
        .quadraticCurveTo(-46, 12, -32, 42)
        .quadraticCurveTo(-18, 62, 0, 66)
        .quadraticCurveTo(18, 62, 32, 42)
        .quadraticCurveTo(46, 12, 45, -30)
        .quadraticCurveTo(42, -62, 0, -64)
        .quadraticCurveTo(-42, -62, -45, -30)
        .closePath()
        .fill(0xf6ded4);

      // Comms / fones auriculares cyber nas têmporas
      const commL = new PIXI.Graphics().roundRect(-48, 4, 6, 20, 3).fill(0x162234).stroke({ color: 0x2ee4b0, width: 1.5 });
      const commR = new PIXI.Graphics().roundRect(42, 4, 6, 20, 3).fill(0x162234).stroke({ color: 0x2ee4b0, width: 1.5 });

      // Blush suave translúcido de anime nas bochechas
      const blushL = new PIXI.Graphics();
      blushL.ellipse(-23, 24, 10, 5.5).fill({ color: 0xff6b8b, alpha: 0.38 });
      const blushR = new PIXI.Graphics();
      blushR.ellipse(23, 24, 10, 5.5).fill({ color: 0xff6b8b, alpha: 0.38 });

      // Olhos Grandes e Expressivos Anime
      const eyeL = new PIXI.Container();
      eyeL.position.set(-18, -2);
      const eyeR = new PIXI.Container();
      eyeR.position.set(18, -2);

      for (const [eye, isLeft] of [[eyeL, true], [eyeR, false]]) {
        // Esclera limpa amendoada
        const sclera = new PIXI.Graphics().ellipse(0, 0, 11, 8.5).fill(0xf7fbff);

        // Delineador superior curvo com cílio alado clássico de anime
        const lash = new PIXI.Graphics();
        lash.moveTo(isLeft ? 10 : -10, 0)
          .quadraticCurveTo(0, -9, isLeft ? -10 : 10, -2)
          .quadraticCurveTo(isLeft ? -14 : 14, -5, isLeft ? -16 : 16, -7)
          .stroke({ color: 0x16131c, width: 3.2, cap: 'round' });
        // Cílio inferior delicado
        const lowerLash = new PIXI.Graphics();
        lowerLash.arc(0, 3.5, 8.5, Math.PI * 0.25, Math.PI * 0.75).stroke({ color: 0x483a4f, width: 1.2 });

        // Íris rica com DUPLO CATCHLIGHT clássico de anime
        const iris = new PIXI.Container();
        iris.name = "iris";
        const irisBase = new PIXI.Graphics();
        irisBase.circle(0, 0, 6.0).fill(0x0e5234); // anel externo escuro
        irisBase.circle(0, 0, 4.8).fill(0x2ee4b0); // centro esmeralda vibrante
        irisBase.circle(0, 0, 2.6).fill(0x0c1713); // pupila profunda

        // CATCHLIGHTS DUPLOS BRANCOS (O brilho clássico de anime)
        const highlightBig = new PIXI.Graphics().circle(-2.0, -2.2, 2.2).fill(0xffffff);
        const highlightSmall = new PIXI.Graphics().circle(2.0, 1.8, 1.2).fill(0xffffff);
        iris.addChild(irisBase, highlightBig, highlightSmall);

        eye.addChild(sclera, iris, lash, lowerLash);
      }

      // Sobrancelhas finas e expressivas
      const browL = new PIXI.Graphics();
      browL.moveTo(-10, 0).quadraticCurveTo(0, -4, 10, 1).stroke({ color: 0x4e385e, width: 2.2, cap: 'round' });
      browL.position.set(-18, -17);

      const browR = new PIXI.Graphics();
      browR.moveTo(-10, 1).quadraticCurveTo(0, -4, 10, 0).stroke({ color: 0x4e385e, width: 2.2, cap: 'round' });
      browR.position.set(18, -17);

      // Boca delicada de anime
      const mouth = new PIXI.Graphics();
      mouth.moveTo(-7, 0).quadraticCurveTo(0, 3, 7, 0).stroke({ color: 0xa44c60, width: 2.2, cap: 'round' });
      mouth.position.set(0, 38);

      // Franja & Cabelo Frontal Anime com Volume Completo (sem cortes no crânio)
      const fringe = new PIXI.Container();
      const hairGeo = new PIXI.Graphics();

      // Topo do crânio com volume farto de cabelo anime cobrindo completamente a cabeça
      hairGeo.moveTo(-48, -25)
        .quadraticCurveTo(-52, -78, 0, -84)
        .quadraticCurveTo(52, -78, 48, -25)
        .quadraticCurveTo(46, -10, 42, 25)
        .lineTo(34, -15)
        .quadraticCurveTo(0, -60, -34, -15)
        .lineTo(-42, 25)
        .quadraticCurveTo(-46, -10, -48, -25)
        .closePath()
        .fill(0x422d5b)
        .stroke({ color: 0x624386, width: 2 });

      // Mechas laterais longas curvas (Side-Bangs) que descem além das bochechas
      hairGeo.moveTo(-44, -28)
        .quadraticCurveTo(-54, 15, -46, 56)
        .quadraticCurveTo(-38, 20, -35, -5)
        .closePath()
        .fill(0x4f366e);

      hairGeo.moveTo(44, -28)
        .quadraticCurveTo(54, 15, 46, 56)
        .quadraticCurveTo(38, 20, 35, -5)
        .closePath()
        .fill(0x4f366e);

      // Franja frontal dividida em mechas curvas delicadas sobre a testa
      hairGeo.moveTo(-45, -35)
        .quadraticCurveTo(-32, -4, -25, 12)
        .quadraticCurveTo(-22, -10, -14, -22)
        .quadraticCurveTo(-8, 6, -1, 16)
        .quadraticCurveTo(0, -8, 8, -18)
        .quadraticCurveTo(16, 4, 23, 13)
        .quadraticCurveTo(28, -6, 45, -35)
        .quadraticCurveTo(0, -82, -45, -35)
        .closePath()
        .fill(0x493366)
        .stroke({ color: 0x6e4e94, width: 1.8 });

      // Hair Halo / Angel Ring (arco luminoso no cabelo anime)
      const halo = new PIXI.Graphics();
      halo.moveTo(-28, -52).quadraticCurveTo(0, -68, 28, -52).stroke({ color: 0xc4aef0, width: 3.5, alpha: 0.75, cap: 'round' });
      fringe.addChild(hairGeo, halo);

      // Ahoge esbelto e orgânico
      const ahoge = new PIXI.Graphics();
      ahoge.moveTo(0, -80).bezierCurveTo(-14, -106, 18, -112, 26, -98).stroke({ color: 0x76539e, width: 3, cap: 'round' });
      ahoge.name = "ahoge";

      // Emotes de Anime: Sweat Drop e Sparkles
      const sweatDrop = new PIXI.Graphics();
      sweatDrop.moveTo(0, -12).quadraticCurveTo(6, 0, 0, 6).quadraticCurveTo(-6, 0, 0, -12).fill({ color: 0x58cfff, alpha: 0.88 });
      sweatDrop.position.set(34, -22);
      sweatDrop.visible = false;
      sweatDrop.name = "sweatDrop";

      const sparkles = new PIXI.Container();
      sparkles.name = "sparkles";
      sparkles.visible = false;
      for (const [sx, sy] of [[-38, -64], [36, -60], [44, -6]]) {
        const star = new PIXI.Graphics();
        star.poly([0, -7, 2, -2, 7, 0, 2, 2, 0, 7, -2, 2, -7, 0, -2, -2]).fill(0xffec70);
        star.position.set(sx, sy);
        sparkles.addChild(star);
      }

      head.addChild(face, commL, commR, blushL, blushR, browL, browR, eyeL, eyeR, mouth, fringe, ahoge, sweatDrop, sparkles);

      // Mini-Drone Mascote Flutuante "Bit"
      const bitDrone = new PIXI.Container();
      bitDrone.name = "bitDrone";
      bitDrone.position.set(80, -135);
      const droneBody = new PIXI.Graphics();
      droneBody.circle(0, 0, 10).fill(0x131f32).stroke({ color: 0x2ee4b0, width: 1.8 });
      droneBody.circle(0, 0, 5.5).fill(0x2ee4b0);
      droneBody.circle(-2, -2, 1.8).fill(0xffffff);
      const droneWingL = new PIXI.Graphics().ellipse(-12, -3, 4.5, 2).fill({ color: 0x43d17d, alpha: 0.65 });
      const droneWingR = new PIXI.Graphics().ellipse(12, -3, 4.5, 2).fill({ color: 0x43d17d, alpha: 0.65 });
      bitDrone.addChild(droneBody, droneWingL, droneWingR);

      // Tela HUD Holográfica de Diagnósticos
      const hudPanel = new PIXI.Container();
      hudPanel.name = "hudPanel";
      hudPanel.position.set(38, -42);
      hudPanel.visible = false;
      const hudBg = new PIXI.Graphics();
      hudBg.roundRect(0, 0, 54, 36, 5).fill({ color: 0x0e2436, alpha: 0.7 }).stroke({ color: 0x2ee4b0, width: 1.4 });
      hudBg.rect(6, 7, 26, 2.5).fill(0x43d17d);
      hudBg.rect(6, 15, 42, 2).fill({ color: 0x2ee4b0, alpha: 0.8 });
      hudBg.rect(6, 21, 32, 2).fill({ color: 0x2ee4b0, alpha: 0.6 });
      hudBg.rect(6, 27, 20, 2).fill({ color: 0x2ee4b0, alpha: 0.4 });
      hudPanel.addChild(hudBg);

      // Montagem na hierarquia preservando todos os nomes contratuais
      root.addChild(legL, legR, hairBack, torso, L.upper, R.upper, head, bitDrone, hudPanel);

      return {
        root,
        torso,
        hairBack,
        head,
        eyeL,
        eyeR,
        mouth,
        browL,
        browR,
        armL: L.upper,
        armR: R.upper,
        forearmL: L.forearm,
        forearmR: R.forearm,
        handL: L.hand,
        handR: R.hand,
        legL,
        legR,
        bitDrone,
        hudPanel,
        sweatDrop,
        sparkles,
        ahoge,
      };
    }

    #lookTarget(s) {
      const d = String(s.direcao_olhar || 'centro').toLowerCase();
      return {
        x: d === 'esquerda' ? -3 : d === 'direita' ? 3 : 0,
        y: d === 'cima' ? -2 : d === 'baixo' ? 2 : 0,
      };
    }

    #applyState() {
      const s = this.state, r = this.rig, i = s.intensidade_expressao;
      const curious = s.expressao === 'CURIOSO' || s.duvida_identidade;
      r.head._targetRotation = curious ? .08 + i * .06 : 0;
      const g = String(s.gesto_atual || 'NENHUM').toUpperCase();
      const side = String(s.lado_gesto || 'none').toLowerCase();
      const semanticPosture = String(s.postura_atual || 'NEUTRO').toUpperCase();
      const leftGesture = side==='left'||side==='both'||side==='none';
      const rightGesture = side==='right'||side==='both'||side==='none';

      r.armL._targetRotation = leftGesture ? (g === 'ACENO' ? -.72 : g === 'DUVIDA' ? -.28 : g === 'FECHADO' ? .2 : .08) : .08;
      r.armR._targetRotation = rightGesture ? (g === 'ESCUTA' ? .48 : g === 'ABERTO' ? .22 : g === 'SURPRESA' ? -.34 : g === 'ACENO' ? .58 : -.08) : -.08;
      r.forearmL._targetRotation = leftGesture ? (g === 'ACENO' ? -.45 : g === 'DUVIDA' ? -.2 : 0) : 0;
      r.forearmR._targetRotation = rightGesture ? (g === 'ESCUTA' ? -.62 : g === 'ABERTO' ? .12 : g === 'SURPRESA' ? .28 : g === 'ACENO' ? -.36 : 0) : 0;
      r.torso._semanticRotation = semanticPosture === 'ABERTO' ? -.015 : semanticPosture === 'FECHADO' ? .025 : 0;

      const pressure = s.expressao === 'SOB_PRESSAO' || s.expressao === 'PREOCUPADO';
      r.browL._targetRotation = pressure ? -.12 : (s.expressao === 'CURIOSO' ? .10 : 0);
      r.browR._targetRotation = pressure ? .12 : (s.expressao === 'CURIOSO' ? -.06 : 0);
      r.root._targetScale = s.modo === 'REAGINDO' ? 1.025 : semanticPosture === 'ABERTO' ? 1.012 : 1;
      r.legL._targetRotation = g === 'ALIVIO' ? -.015 : 0;
      r.legR._targetRotation = g === 'ALIVIO' ? .015 : 0;

      if (r.sweatDrop) r.sweatDrop.visible = pressure;
      if (r.sparkles) r.sparkles.visible = s.expressao === 'RECUPERANDO' || g === 'ALIVIO';
      if (r.hudPanel) r.hudPanel.visible = s.modo === 'OBSERVANDO' || g === 'ESCUTA';

      // Navegação por foco cognitivo
      if (s.foco_visual === 'core') {
        this.walkTargetOffset = -this.patrolLimit * 0.75;
        this.walking = true;
      } else if (s.foco_visual === 'x99') {
        this.walkTargetOffset = this.patrolLimit * 0.75;
        this.walking = true;
      } else if (s.foco_visual === 'deraldinho') {
        this.walkTargetOffset = 0;
      }
    }

    #tick(deltaMs) {
      if (!this.ready || !this.state || this.hidden) return;
      const s = this.state, r = this.rig;
      const dt = Math.min(.05, Math.max(0, deltaMs / 1000));
      const now = performance.now();
      const t = (now - this.startedAt) / 1000;
      const motion = this.reducedMotion ? 0 : s.intensidade_movimento;
      const alive = this.motion.step({ ...s, intensidade_movimento: motion }, dt, t);

      // LOCOMOÇÃO & PATRULHA (WALK CYCLE DE ANIME)
      if (!this.reducedMotion) {
        if (now >= this.nextPatrolTime) {
          this.walking = Math.random() > 0.20;
          if (this.walking) {
            // Caminha para um ponto aleatório da passarela
            this.walkTargetOffset = (Math.random() * (this.patrolLimit * 2)) - this.patrolLimit;
          }
          this.nextPatrolTime = now + 3200 + Math.random() * 3800;
        }

        const distToTarget = this.walkTargetOffset - this.walkOffset;
        if (Math.abs(distToTarget) > 2.5 && this.walking) {
          this.walkDirection = distToTarget > 0 ? 1 : -1;
          const speed = 36 * (0.85 + motion * 0.45);
          this.walkOffset += this.walkDirection * speed * dt;
          this.stepPhase += dt * 5.6 * (0.85 + motion * 0.35);
        } else {
          this.stepPhase = M.smoothExp(this.stepPhase, 0, dt, 4);
        }
      }

      const isWalking = Math.abs(Math.sin(this.stepPhase)) > 0.05;
      const walkBob = isWalking ? Math.abs(Math.sin(this.stepPhase)) * 3.6 : 0;
      const legSwing = isWalking ? Math.sin(this.stepPhase) * 0.34 : 0;
      const armSwing = isWalking ? Math.sin(this.stepPhase) * 0.24 : 0;

      // CONTRATO VITAL PRESERVADO:
      r.root.x=170+alive.weightShift*.22+(this.walkOffset||0);
      r.root.y = 280 + alive.breath - walkBob;

      // Virada suave na direção da caminhada com profundidade 3D
      this.zDepth = M.smoothExp(this.zDepth, this.targetZDepth, dt, 5);
      const depthScale = 1.0 + this.zDepth;
      const targetScaleX = (r.root._targetScale || 1) * (this.walkDirection || 1) * depthScale;
      r.root.scale.x = M.smoothExp(r.root.scale.x, targetScaleX, dt, 6);
      const scY = (r.root._targetScale || 1) * depthScale;
      r.root.scale.y = M.smoothExp(r.root.scale.y, scY, dt, 7);

      // Pernas no Walk Cycle
      r.legL.rotation = M.smoothExp(r.legL.rotation, (r.legL._targetRotation || 0) + legSwing, dt, 12);
      r.legR.rotation = M.smoothExp(r.legR.rotation, (r.legR._targetRotation || 0) - legSwing, dt, 12);

      // Tronco e Cabelo
      r.torso.rotation = M.smoothExp(r.torso.rotation, (r.torso._semanticRotation || 0) + alive.weightShift * .0025, dt, 5);
      r.hairBack.rotation = alive.hairLag + (isWalking ? -this.walkDirection * 0.04 : 0);

      // Cabeça com micro-inclinações anime e mouse tracking
      let headTilt = (r.head._targetRotation || 0) + alive.headMicro;
      if (this.mouseTarget.active) {
        headTilt += this.mouseTarget.x * 0.045;
      }
      r.head.rotation = M.smoothExp(r.head.rotation, headTilt, dt, 9);

      // Braços no Walk Cycle contralateral
      r.armL.rotation = M.smoothExp(r.armL.rotation, (r.armL._targetRotation || 0) - armSwing, dt, 7);
      r.armR.rotation = M.smoothExp(r.armR.rotation, (r.armR._targetRotation || 0) + armSwing, dt, 7);
      r.forearmL.rotation = M.smoothExp(r.forearmL.rotation, r.forearmL._targetRotation || 0, dt, 8);
      r.forearmR.rotation = M.smoothExp(r.forearmR.rotation, r.forearmR._targetRotation || 0, dt, 8);

      // Sobrancelhas
      r.browL.rotation = M.smoothExp(r.browL.rotation, r.browL._targetRotation || 0, dt, 10);
      r.browR.rotation = M.smoothExp(r.browR.rotation, r.browR._targetRotation || 0, dt, 10);

      // OLHAR DINÂMICO (MOUSE TRACKING + SACCADES)
      let lookPoint = this.#lookTarget(s);
      if (this.mouseTarget.active && (now - this.lastMouseMove < 3000)) {
        lookPoint = {
          x: this.mouseTarget.x * 3.4,
          y: this.mouseTarget.y * 2.2,
        };
      }
      const gaze = this.motion.saccade.update(dt, lookPoint, motion, now);
      for (const eye of [r.eyeL, r.eyeR]) {
        const iris = eye.getChildByName('iris');
        if (iris) {
          iris.x = gaze.x;
          iris.y = gaze.y;
        }
      }

      // Piscar de olhos suave anime
      const blink = !this.reducedMotion && this.motion.blink.update(now);
      r.eyeL.scale.y = M.smoothExp(r.eyeL.scale.y, blink ? .08 : 1, dt, 34);
      r.eyeR.scale.y = M.smoothExp(r.eyeR.scale.y, blink ? .08 : 1, dt, 34);

      // Boca anime falando
      const mouthTarget = s.falando && motion > 0
        ? 1.15 + Math.abs(Math.sin(t * 8.5)) * 1.5
        : (s.expressao === 'SERENO' || s.expressao === 'RECUPERANDO' ? .75 : 1);
      r.mouth.scale.y = M.smoothExp(r.mouth.scale.y, mouthTarget, dt, 16);
      r.mouth.scale.x = M.smoothExp(r.mouth.scale.x, s.falando ? 1.2 : 1.0, dt, 12);

      // Ahoge elástico
      if (r.ahoge) {
        r.ahoge.rotation = Math.sin(t * 3.2) * 0.08 + alive.hairLag * 1.6;
      }

      // Mascote Orbe "Bit" orbitando
      if (r.bitDrone) {
        r.bitDrone.x = 84 + Math.sin(t * 1.5) * 14;
        r.bitDrone.y = -138 + Math.cos(t * 1.2) * 10 + alive.breath * 0.4;
      }

      // HUD flutuante
      if (r.hudPanel && r.hudPanel.visible) {
        r.hudPanel.y = -44 + Math.sin(t * 2.2) * 3;
      }
    }
  }

  window.AtlasAvatarEngine = Object.freeze({ AtlasAvatarEngine, POLICY, MODES, EXPRESSIONS });
})();
