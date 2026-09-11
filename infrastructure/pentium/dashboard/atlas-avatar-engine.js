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
      this.baseState = null;
      this.intentBehavior = null;
      this.intentBehaviorUntil = 0;
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

      // Pet State Machine (Shimeji Desktop Pet)
      this.petMode = 'PATROL'; // 'PATROL', 'SIT', 'HOP', 'POKE'
      this.hopTime = 0;
      this.hopDuration = 0.60;
      this.hopOrigin = 0;
      this.hopTarget = 0;
      this.hopTargetZ = 0;
      this.sitDwellTime = 0;
      this.pokeUntil = 0;
      this.lastCognitiveAlvo = null;
      this.lastCognitiveAcaoPet = null;

      // Mouse tracking interativo
      this.mouseTarget = { x: 0, y: 0, active: false };
      this.lastMouseMove = 0;
      this.#initMouseTracking();
      this.#initPetInteraction();
    }

    #initPetInteraction() {
      if (!this.host) return;
      this.host.style.cursor = 'pointer';
      this.host.title = 'Clique para interagir com a Atlas!';
      this.host.addEventListener('click', () => {
        this.triggerPoke();
      });
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
        await app.init({
          preference: 'webgl',
          width: 340,
          height: 380,
          resizeTo: this.host,
          backgroundAlpha: 0,
          antialias: true,
          autoDensity: true
        });
        this.host.replaceChildren(app.canvas);
        this.app = app;

        // No PixiJS v8, o carregamento de texturas precisa ser assincrono via Assets.load
        let textures = null;
        try {
          if (PIXI.Assets && typeof PIXI.Assets.load === 'function') {
            const [stand, sit, poke] = await Promise.all([
              PIXI.Assets.load('/assets/atlas-pet-standing.png').catch(() => null),
              PIXI.Assets.load('/assets/atlas-pet-sitting.png').catch(() => null),
              PIXI.Assets.load('/assets/atlas-pet-poke.png').catch(() => null),
            ]);
            if (stand && sit && poke) {
              textures = { stand, sit, poke };
            }
          }
        } catch (loadErr) {
          console.warn("[AtlasAvatarEngine] Assets.load error, using procedural fallback:", loadErr);
        }

        this.rig = this.#buildRig(textures);
        app.stage.addChild(this.rig.root);
        app.ticker.add(t => this.#tick(t.deltaMS));
        this.host.classList.add("pixi-ready");
        this.ready = true;
        return true;
      } catch (error) {
        console.error("[AtlasAvatarEngine] Pixi init error:", error);
        this.host.dataset.rendererError = error?.message || error?.name || "PixiInitError";
        return false;
      }
    }

    render(state) {
      if (!this.ready || !state || !MODES.has(state.modo) || !EXPRESSIONS.has(state.expressao)) return false;
      this.baseState = state;
      const visual = this.intentBehavior?.visual || null;
      this.state = visual ? Object.freeze({ ...state, ...visual }) : state;
      this.#applyState();
      return true;
    }

    applyIntentBehavior(behavior) {
      const next = behavior && typeof behavior === 'object' ? behavior : { clear: true };
      if (next.clear) {
        this.intentBehavior = null; this.intentBehaviorUntil = 0;
        if (this.baseState) { this.state = this.baseState; this.#applyState(); }
        if (next.returnToPatrol) { this.petMode = 'PATROL'; this.walking = true; }
        return;
      }
      this.intentBehavior = next;
      this.intentBehaviorUntil = next.oneShot ? performance.now() + Math.max(300, Number(next.durationMs) || 1600) : Number.POSITIVE_INFINITY;
      if (next.target) this.visitPanel(next.target);
      if (next.petMode === 'SIT') { this.petMode = 'SIT'; this.walking = false; this.sitDwellTime = Number.POSITIVE_INFINITY; }
      if (this.baseState) { this.state = Object.freeze({ ...this.baseState, ...(next.visual || {}) }); this.#applyState(); }
    }

    triggerPoke() {
      this.petMode = 'POKE';
      this.pokeUntil = performance.now() + 1200;
      if (this.rig?.sparkles) this.rig.sparkles.visible = true;
    }

    hopTo(targetOffset, targetZ = 0) {
      this.petMode = 'HOP';
      this.hopOrigin = this.walkOffset;
      this.hopTarget = targetOffset;
      this.hopTargetZ = targetZ;
      this.hopTime = 0;
      this.walkDirection = targetOffset >= this.walkOffset ? 1 : -1;
    }

    visitPanel(target) {
      const t = String(target || 'auto').toLowerCase();
      if (typeof window !== 'undefined' && window.anchorPetTo) {
        window.anchorPetTo(t);
      }
      if (t === 'mind' || t === 'cognitionpanel') {
        this.hopTo(-this.patrolLimit * 0.88, -0.12);
        if (this.rig?.hudPanel) this.rig.hudPanel.visible = true;
      } else if (t === 'chat' || t === 'atlaschatpanel') {
        this.hopTo(this.patrolLimit * 0.88, 0.12);
      } else if (t === 'services') {
        this.hopTo(-this.patrolLimit * 0.45, 0.05);
        if (this.rig?.hudPanel) this.rig.hudPanel.visible = true;
      } else if (t === 'core') {
        this.hopTo(-this.patrolLimit * 0.75, -0.05);
      } else if (t === 'x99') {
        this.hopTo(this.patrolLimit * 0.75, 0.05);
      } else if (t === 'deraldinho' || t === 'center') {
        this.hopTo(0, 0);
      } else if (t === 'auto') {
        this.petMode = 'PATROL';
        this.walking = true;
      } else {
        this.hopTo(0, 0);
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

    #buildRig(textures = null) {
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
      // Silhueta orgânica curva do cabelo longo anime com domo cranial superior volumoso
      hbG.moveTo(-48, -48)
        .quadraticCurveTo(-60, -92, 0, -96)
        .quadraticCurveTo(60, -92, 48, -48)
        .quadraticCurveTo(78, 20, 72, 85)
        .quadraticCurveTo(60, 128, 42, 142)
        .quadraticCurveTo(36, 105, 22, 115)
        .quadraticCurveTo(8, 148, 0, 136)
        .quadraticCurveTo(-8, 148, -22, 115)
        .quadraticCurveTo(-36, 105, -42, 142)
        .quadraticCurveTo(-60, 128, -72, 85)
        .quadraticCurveTo(-78, 20, -48, -48)
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
      hairGeo.moveTo(-50, -25)
        .quadraticCurveTo(-56, -84, 0, -90)
        .quadraticCurveTo(56, -84, 50, -25)
        .quadraticCurveTo(46, -10, 42, 25)
        .lineTo(34, -15)
        .quadraticCurveTo(0, -60, -34, -15)
        .lineTo(-42, 25)
        .quadraticCurveTo(-46, -10, -50, -25)
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
        .quadraticCurveTo(0, -86, -45, -35)
        .closePath()
        .fill(0x493366)
        .stroke({ color: 0x6e4e94, width: 1.8 });

      // Hair Halo / Angel Ring (arco luminoso no cabelo anime)
      const halo = new PIXI.Graphics();
      halo.moveTo(-30, -56).quadraticCurveTo(0, -72, 30, -56).stroke({ color: 0xc4aef0, width: 3.5, alpha: 0.75, cap: 'round' });
      fringe.addChild(hairGeo, halo);

      // Ahoge esbelto e orgânico
      const ahoge = new PIXI.Graphics();
      ahoge.moveTo(0, -86).bezierCurveTo(-16, -112, 18, -118, 26, -102).stroke({ color: 0x76539e, width: 3.2, cap: 'round' });
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

      // Se houver texturas carregadas, os sprites sao exibidos com prioridade.
      // Se nao houver, o rig vetorial procedural e mantido 100% visivel como fallback automatico.
      const hasSprites = Boolean(textures && textures.stand && textures.sit && textures.poke);
      const vectorRig = new PIXI.Container();
      vectorRig.name = "vectorRig";
      vectorRig.alpha = hasSprites ? 0 : 1;
      vectorRig.visible = !hasSprites;
      vectorRig.addChild(legL, legR, hairBack, torso, L.upper, R.upper, head);

      // Sprites e Mesh 2D Deformavel (FFD - Free-Form Deformation)
      const spriteContainer = new PIXI.Container();
      spriteContainer.name = "spriteContainer";
      spriteContainer.visible = hasSprites;

      const COLS = 8, ROWS = 12;
      function createDeformableMesh(tex, name, anchorY = 0.98) {
        if (!tex) return null;
        if (PIXI.MeshPlane) {
          try {
            const mesh = new PIXI.MeshPlane({ texture: tex, verticesX: COLS, verticesY: ROWS });
            mesh.name = name;
            mesh.pivot.set(tex.width * 0.513, tex.height * anchorY);
            mesh.position.set(0, 114);
            mesh.scale.set(0.208);
            const orig = new Float32Array(mesh.geometry.buffers[0].data);
            return { mesh, orig };
          } catch (e) {
            console.warn("[AtlasAvatarEngine] MeshPlane creation failed, using Sprite fallback:", e);
          }
        }
        const spr = new PIXI.Sprite(tex);
        spr.name = name;
        spr.anchor.set(0.513, anchorY);
        spr.position.set(0, 114);
        spr.scale.set(0.208);
        return { mesh: spr, orig: null };
      }

      const resStand = hasSprites ? createDeformableMesh(textures.stand, "spriteStanding", 0.98) : null;
      const resSit = hasSprites ? createDeformableMesh(textures.sit, "spriteSitting", 0.96) : null;
      const resPoke = hasSprites ? createDeformableMesh(textures.poke, "spritePoke", 0.98) : null;

      const spriteStanding = resStand?.mesh || PIXI.Sprite.from('/assets/atlas-pet-standing.png');
      const spriteSitting = resSit?.mesh || PIXI.Sprite.from('/assets/atlas-pet-sitting.png');
      const spritePoke = resPoke?.mesh || PIXI.Sprite.from('/assets/atlas-pet-poke.png');

      spriteStanding.visible = true;
      spriteSitting.visible = false;
      spritePoke.visible = false;

      const origStanding = resStand?.orig || null;
      const origSitting = resSit?.orig || null;
      const origPoke = resPoke?.orig || null;

      spriteContainer.addChild(spriteStanding, spriteSitting, spritePoke);

      // Montagem na hierarquia preservando todos os nós contratuais
      root.addChild(vectorRig, spriteContainer, bitDrone, hudPanel);

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
        vectorRig,
        spriteContainer,
        spriteStanding,
        spriteSitting,
        spritePoke,
        origStanding,
        origSitting,
        origPoke,
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
      r.torso._semanticRotation = semanticPosture === 'ABERTO' ? -.015 : semanticPosture === 'FECHADO' ? .025 : semanticPosture === 'ATENTO' ? -.008 : 0;

      const pressure = s.expressao === 'SOB_PRESSAO' || s.expressao === 'PREOCUPADO';
      r.browL._targetRotation = pressure ? -.12 : (s.expressao === 'CURIOSO' ? .10 : 0);
      r.browR._targetRotation = pressure ? .12 : (s.expressao === 'CURIOSO' ? -.06 : 0);
      r.root._targetScale = s.modo === 'REAGINDO' ? 1.025 : semanticPosture === 'ABERTO' ? 1.012 : 1;
      r.legL._targetRotation = g === 'ALIVIO' ? -.015 : 0;
      r.legR._targetRotation = g === 'ALIVIO' ? .015 : 0;

      if (r.sweatDrop) r.sweatDrop.visible = pressure;
      if (r.sparkles) r.sparkles.visible = s.expressao === 'RECUPERANDO' || g === 'ALIVIO';
      if (r.hudPanel) r.hudPanel.visible = s.modo === 'OBSERVANDO' || g === 'ESCUTA';

      // Controle de Locomoção e Comportamento Pet vindo de Hermes / Estado Visual
      if (s.acao_pet && s.acao_pet !== this.lastCognitiveAcaoPet) {
        this.lastCognitiveAcaoPet = s.acao_pet;
        const petAct = String(s.acao_pet).toUpperCase();
        if (petAct === 'POKE') {
          this.triggerPoke();
        } else if (petAct === 'SIT') {
          this.petMode = 'SIT';
          this.sitDwellTime = performance.now() + 9000;
        } else if (petAct === 'HOP') {
          this.hopTo(this.walkTargetOffset, this.targetZDepth);
        } else if (petAct === 'PATROL') {
          this.petMode = 'PATROL';
        }
      }

      if (s.alvo_locomocao && s.alvo_locomocao !== this.lastCognitiveAlvo) {
        this.lastCognitiveAlvo = s.alvo_locomocao;
        this.visitPanel(s.alvo_locomocao);
      } else if (s.foco_visual === 'core') {
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
      if (this.intentBehavior && Number.isFinite(this.intentBehaviorUntil) && now >= this.intentBehaviorUntil) {
        const returnToPatrol = Boolean(this.intentBehavior.returnToPatrol);
        this.intentBehavior = null; this.intentBehaviorUntil = 0;
        if (this.baseState) { this.state = this.baseState; this.#applyState(); }
        if (returnToPatrol) { this.petMode = 'PATROL'; this.walking = true; this.nextPatrolTime = now + 1200; }
      }
      const t = (now - this.startedAt) / 1000;
      const motion = this.reducedMotion ? 0 : s.intensidade_movimento;
      const alive = this.motion.step({ ...s, intensidade_movimento: motion }, dt, t);

      // COMPORTAMENTO PET DE INTERFACE (SHIMEJI: HOP, SIT, POKE, PATROL)
      let hopY = 0;
      let isSitting = false;

      // 1. Estado HOP (Salto entre janelas)
      if (this.petMode === 'HOP') {
        this.hopTime += dt;
        const progress = Math.min(1, this.hopTime / this.hopDuration);
        hopY = -Math.sin(progress * Math.PI) * 55;
        this.walkOffset = this.hopOrigin + (this.hopTarget - this.hopOrigin) * progress;
        this.zDepth = M.smoothExp(this.zDepth, this.hopTargetZ, dt, 8);
        if (progress >= 1) {
          this.petMode = Math.random() > 0.35 ? 'SIT' : 'PATROL';
          this.sitDwellTime = now + 4000 + Math.random() * 4500;
        }
      }
      // 2. Estado SIT (Sentar na borda da janela balançando perninhas)
      else if (this.petMode === 'SIT') {
        isSitting = true;
        this.walkOffset = M.smoothExp(this.walkOffset, this.walkTargetOffset, dt, 4);
        if (now > this.sitDwellTime) {
          this.petMode = 'PATROL';
          this.nextPatrolTime = now + 3500;
        }
      }
      // 3. Estado POKE (Pulinho assustado com carinho)
      else if (this.petMode === 'POKE') {
        hopY = -Math.abs(Math.sin((now - (this.pokeUntil - 1200)) * 0.012)) * 22;
        if (now >= this.pokeUntil) {
          if (this.intentBehavior?.petMode === 'SIT') { this.petMode = 'SIT'; this.walking = false; this.sitDwellTime = Number.POSITIVE_INFINITY; }
          else this.petMode = 'PATROL';
          if (r.sparkles) r.sparkles.visible = false;
        }
      }
      // 4. Estado PATROL (Caminhar sobre o topo da janela)
      else {
        if (!this.reducedMotion) {
          if (now >= this.nextPatrolTime) {
            this.walking = Math.random() > 0.20;
            if (this.walking) {
              this.walkTargetOffset = (Math.random() * (this.patrolLimit * 2)) - this.patrolLimit;
            } else if (Math.random() > 0.45) {
              this.petMode = 'SIT';
              this.sitDwellTime = now + 4500 + Math.random() * 5000;
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
      }

      const isWalking = (this.petMode === 'PATROL') && Math.abs(Math.sin(this.stepPhase)) > 0.05;
      const walkBob = isWalking ? Math.abs(Math.sin(this.stepPhase)) * 3.6 : 0;
      const legSwing = isWalking ? Math.sin(this.stepPhase) * 0.34 : 0;
      const armSwing = isWalking ? Math.sin(this.stepPhase) * 0.24 : 0;

      // CONTRATO VITAL PRESERVADO:
      r.root.x=170+alive.weightShift*.22+(this.walkOffset||0);
      r.root.y = 280 + alive.breath - walkBob + hopY + (isSitting ? 12 : 0);

      // Virada suave na direção da caminhada com profundidade 3D
      this.zDepth = M.smoothExp(this.zDepth, this.targetZDepth, dt, 5);
      const depthScale = 1.0 + this.zDepth;
      const targetScaleX = (r.root._targetScale || 1) * (this.walkDirection || 1) * depthScale;
      r.root.scale.x = M.smoothExp(r.root.scale.x, targetScaleX, dt, 6);
      const scY = (r.root._targetScale || 1) * depthScale;
      r.root.scale.y = M.smoothExp(r.root.scale.y, scY, dt, 7);

      // Alternancia e animacao dos Sprites Anime 2D de Alta Resolucao
      if (r.spriteStanding && r.spriteSitting && r.spritePoke) {
        if (this.petMode === 'SIT') {
          r.spriteSitting.visible = true;
          r.spriteStanding.visible = false;
          r.spritePoke.visible = false;
          r.spriteSitting.rotation = Math.sin(t * 2.8) * 0.025;
        } else if (this.petMode === 'POKE') {
          r.spritePoke.visible = true;
          r.spriteStanding.visible = false;
          r.spriteSitting.visible = false;
          r.spritePoke.rotation = Math.sin(now * 0.025) * 0.04;
        } else {
          r.spriteStanding.visible = true;
          r.spriteSitting.visible = false;
          r.spritePoke.visible = false;
          const walkTilt = isWalking ? Math.sin(this.stepPhase) * 0.035 : 0;
          r.spriteStanding.rotation = walkTilt + alive.headMicro * 0.35;
        }
      }

      // Pernas: Dobradas e balançando quando sentada (SIT) ou caminhando (WALK)
      if (isSitting) {
        const sitSwing = Math.sin(t * 2.8) * 0.22;
        r.legL.rotation = M.smoothExp(r.legL.rotation, 1.42 + sitSwing, dt, 8);
        r.legR.rotation = M.smoothExp(r.legR.rotation, 1.42 - sitSwing, dt, 8);
      } else if (this.petMode === 'HOP') {
        // Pernas recolhidas durante o salto
        r.legL.rotation = M.smoothExp(r.legL.rotation, 0.75, dt, 10);
        r.legR.rotation = M.smoothExp(r.legR.rotation, 0.75, dt, 10);
      } else {
        r.legL.rotation = M.smoothExp(r.legL.rotation, (r.legL._targetRotation || 0) + legSwing, dt, 12);
        r.legR.rotation = M.smoothExp(r.legR.rotation, (r.legR._targetRotation || 0) - legSwing, dt, 12);
      }

      // Tronco e Cabelo
      r.torso.rotation = M.smoothExp(r.torso.rotation, (r.torso._semanticRotation || 0) + alive.weightShift * .0025, dt, 5);
      r.hairBack.rotation = alive.hairLag + (isWalking ? -this.walkDirection * 0.04 : 0);

      // Cabeça com micro-inclinações anime e mouse tracking
      let headTilt = (r.head._targetRotation || 0) + alive.headMicro;
      if (this.mouseTarget.active) {
        headTilt += this.mouseTarget.x * 0.045;
      }
      r.head.rotation = M.smoothExp(r.head.rotation, headTilt, dt, 9);

      // Deformacao de Malha 2D (FFD): articulacao organica de respiracao, cabelo e pernas
      if (this.petMode === 'SIT' && r.origSitting) {
        this.#deformMesh(r.spriteSitting, r.origSitting, 8, 12, dt, t, { hairLag: alive.hairLag, headTilt }, false, this.stepPhase, this.petMode);
      } else if (this.petMode === 'POKE' && r.origPoke) {
        this.#deformMesh(r.spritePoke, r.origPoke, 8, 12, dt, t, { hairLag: alive.hairLag, headTilt }, false, this.stepPhase, this.petMode);
      } else if (r.origStanding) {
        this.#deformMesh(r.spriteStanding, r.origStanding, 8, 12, dt, t, { hairLag: alive.hairLag, headTilt }, isWalking, this.stepPhase, this.petMode);
      }

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

    #deformMesh(mesh, orig, cols, rows, dt, t, state, isWalking, stepPhase, petMode) {
      if (!mesh?.geometry?.buffers?.[0]?.data || !orig) return;
      const buf = mesh.geometry.buffers[0];
      const verts = buf.data;
      const isSit = petMode === 'SIT';
      const isPoke = petMode === 'POKE';

      const breath = Math.sin(t * 2.2) * 3.2;
      const hairWave = Math.sin(t * 3.6) * 4.5 + (state.hairLag || 0) * 22;
      const walkLeg = isWalking ? Math.sin(stepPhase) * 14 : 0;
      const headTilt = state.headTilt || 0;

      for (let r = 0; r < rows; r++) {
        const vY = r / (rows - 1);
        let hairOffset = 0;
        if (vY < 0.38) {
          const hairWeight = (1 - (vY / 0.38));
          hairOffset = Math.sin(t * 3.2 + vY * 3.8) * hairWave * hairWeight;
        }
        let chestExpand = 0;
        if (vY >= 0.28 && vY <= 0.68) {
          const chestWeight = Math.sin(((vY - 0.28) / 0.40) * Math.PI);
          chestExpand = breath * chestWeight;
        }

        for (let c = 0; c < cols; c++) {
          const idx = (r * cols + c) * 2;
          const ox = orig[idx];
          const oy = orig[idx + 1];
          const vX = c / (cols - 1);
          const signX = vX < 0.5 ? -1 : 1;

          let dx = signX * chestExpand;
          dx += hairOffset * (vX < 0.35 ? 1.3 : vX > 0.65 ? 1.3 : 0.35);

          let dy = 0;

          if (vY < 0.40) {
            dx += headTilt * (0.40 - vY) * 65;
          }

          if (vY > 0.62 && isWalking) {
            const legWeight = (vY - 0.62) / 0.38;
            if (vX < 0.5) {
              dy -= Math.abs(walkLeg) * legWeight * 0.45;
              dx += walkLeg * legWeight * 0.85;
            } else {
              dy -= Math.abs(-walkLeg) * legWeight * 0.45;
              dx -= walkLeg * legWeight * 0.85;
            }
          }

          if (vY > 0.68 && isSit) {
            const sitWeight = (vY - 0.68) / 0.32;
            dx += Math.sin(t * 3.0 + c * 0.8) * 3.0 * sitWeight;
            dy -= 8 * sitWeight;
          }

          if (isPoke) {
            const squash = Math.sin(t * 16.0) * 4.5;
            dy += (vY - 0.5) * squash;
            dx -= signX * squash * 0.6;
          }

          verts[idx] = ox + dx;
          verts[idx + 1] = oy + dy;
        }
      }
      buf.update();
    }
  }

  window.AtlasAvatarEngine = Object.freeze({ AtlasAvatarEngine, POLICY, MODES, EXPRESSIONS });
})();
