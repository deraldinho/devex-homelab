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

      // Locomoção & Patrulha
      this.walkOffset = 0;
      this.walkTargetOffset = 0;
      this.walkDirection = 1;
      this.stepPhase = 0;
      this.walking = true;
      this.nextPatrolTime = performance.now() + 2500;

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
        if (dist < 900) updateMouse(e);
      });
      this.host.addEventListener("mouseleave", () => {
        setTimeout(() => { if (performance.now() - this.lastMouseMove > 2000) this.mouseTarget.active = false; }, 2000);
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

    #arm(side) {
      const upper = new PIXI.Container();
      const sign = side === 'L' ? -1 : 1;
      upper.position.set(46 * sign, -78);

      // Manga cyber estilizada
      const sleeve = new PIXI.Graphics();
      sleeve.roundRect(side === 'L' ? -14 : -9, 0, 23, 56, 11).fill(0x132238).stroke({ color: 0x223a5e, width: 2 });
      sleeve.rect(side === 'L' ? -13 : -8, 48, 21, 3).fill(0x2ee4b0);
      upper.addChild(sleeve);

      const forearm = new PIXI.Container();
      forearm.position.set(0, 48);
      const armG = new PIXI.Graphics();
      armG.roundRect(-10, 0, 20, 52, 9).fill(0x182c46);
      armG.circle(0, 36, 4).fill(0x2ee4b0);
      forearm.addChild(armG);

      // Mão delicada de anime
      const hand = new PIXI.Graphics();
      hand.ellipse(0, 52, 8, 11).fill(0xf6dcd0);
      hand.circle(side === 'L' ? -4 : 4, 50, 3).fill(0xf6dcd0);
      forearm.addChild(hand);

      upper.addChild(forearm);
      return { upper, forearm, hand };
    }

    #buildRig() {
      const root = new PIXI.Container();
      root.position.set(170,280);

      // Sombra sob os pés
      const shadow = new PIXI.Graphics().ellipse(0, 114, 52, 10).fill({ color: 0x000000, alpha: 0.35 });
      root.addChild(shadow);

      // Pernas articuladas para o Walk Cycle
      const legL = new PIXI.Container();
      legL.position.set(-20, 26);
      const legLG = new PIXI.Graphics();
      legLG.roundRect(-13, 0, 26, 100, 12).fill(0x151f33).stroke({ color: 0x243754, width: 2 });
      legLG.roundRect(-15, 88, 30, 20, 7).fill(0x0a0f18);
      legLG.rect(-14, 88, 28, 3).fill(0x2ee4b0);
      legL.addChild(legLG);

      const legR = new PIXI.Container();
      legR.position.set(20, 26);
      const legRG = new PIXI.Graphics();
      legRG.roundRect(-13, 0, 26, 100, 12).fill(0x151f33).stroke({ color: 0x243754, width: 2 });
      legRG.roundRect(-15, 88, 30, 20, 7).fill(0x0a0f18);
      legRG.rect(-14, 88, 28, 3).fill(0x2ee4b0);
      legR.addChild(legRG);

      // Cabelo Traseiro Anime volumoso e fluido com inércia
      const hairBack = new PIXI.Container();
      hairBack.position.set(0, -150);
      const hbG = new PIXI.Graphics();
      hbG.poly([
        -45, -20, -78, 30, -70, 95, -45, 125, -20, 90, 0, 120,
        20, 90, 45, 125, 70, 95, 78, 30, 45, -20
      ]).fill(0x3e2d58).stroke({ color: 0x614885, width: 3 });
      hbG.poly([-35, 10, -60, 60, -45, 90]).fill(0x4f3a6f);
      hbG.poly([35, 10, 60, 60, 45, 90]).fill(0x4f3a6f);
      hairBack.addChild(hbG);

      // Tronco Cyber-Anime elegante
      const torso = new PIXI.Container();
      const body = new PIXI.Graphics();
      body.roundRect(-48, -108, 96, 142, 24).fill(0x121e33).stroke({ color: 0x223654, width: 3 });
      const shirt = new PIXI.Graphics();
      shirt.poly([-24, -92, 24, -92, 36, 12, -36, 12]).fill(0xf0f4fa);
      const reactor = new PIXI.Graphics();
      reactor.poly([-6, -88, 6, -88, 0, -42]).fill(0x20324e);
      reactor.circle(0, -38, 8).fill(0x2ee4b0);
      reactor.circle(0, -38, 12).fill({ color: 0x43d17d, alpha: 0.35 });
      reactor.circle(0, -38, 4).fill(0xffffff);
      torso.addChild(body, shirt, reactor);

      // Braços articulados
      const L = this.#arm('L');
      const R = this.#arm('R');

      // Cabeça & Rosto Anime
      const head = new PIXI.Container();
      head.position.set(0, -155);

      const face = new PIXI.Graphics();
      face.poly([
        -48, -45, -50, 5, -36, 42, -18, 58, 0, 64, 18, 58, 36, 42, 50, 5, 48, -45, 0, -62
      ]).fill(0xf5ded3);
      const commL = new PIXI.Graphics().roundRect(-53, 2, 7, 22, 4).fill(0x182436).stroke({ color: 0x2ee4b0, width: 1.5 });
      const commR = new PIXI.Graphics().roundRect(46, 2, 7, 22, 4).fill(0x182436).stroke({ color: 0x2ee4b0, width: 1.5 });

      // Blush rosado anime com hachuras
      const blushL = new PIXI.Graphics();
      blushL.ellipse(-26, 20, 11, 6).fill({ color: 0xff6b8b, alpha: 0.45 });
      blushL.moveTo(-31, 22).lineTo(-28, 18).stroke({ color: 0xff9bb0, width: 1.5 });
      blushL.moveTo(-27, 22).lineTo(-24, 18).stroke({ color: 0xff9bb0, width: 1.5 });

      const blushR = new PIXI.Graphics();
      blushR.ellipse(26, 20, 11, 6).fill({ color: 0xff6b8b, alpha: 0.45 });
      blushR.moveTo(23, 22).lineTo(26, 18).stroke({ color: 0xff9bb0, width: 1.5 });
      blushR.moveTo(27, 22).lineTo(30, 18).stroke({ color: 0xff9bb0, width: 1.5 });

      // Olhos de Anime Expressivos
      const eyeL = new PIXI.Container();
      eyeL.position.set(-21, -4);
      const eyeR = new PIXI.Container();
      eyeR.position.set(21, -4);

      for (const [eye, isLeft] of [[eyeL, true], [eyeR, false]]) {
        const sclera = new PIXI.Graphics().ellipse(0, 0, 12, 9).fill(0xf6faff);
        const lash = new PIXI.Graphics();
        lash.arc(0, -3, 13, Math.PI * 0.95, Math.PI * 2.05).stroke({ color: 0x18141f, width: 3.5 });
        lash.moveTo(isLeft ? -13 : 13, -3).lineTo(isLeft ? -17 : 17, -7).stroke({ color: 0x18141f, width: 2.5 });
        const lowerLash = new PIXI.Graphics();
        lowerLash.arc(0, 4, 10, Math.PI * 0.2, Math.PI * 0.8).stroke({ color: 0x3d3045, width: 1.5 });

        // Íris com DUPLO CATCHLIGHT clássico de anime
        const iris = new PIXI.Container();
        iris.name = "iris";
        const irisBase = new PIXI.Graphics();
        irisBase.circle(0, 0, 6.2).fill(0x0f5b3a);
        irisBase.circle(0, 0, 5.0).fill(0x2ee4b0);
        irisBase.circle(0, 0, 2.8).fill(0x0b1612);

        // CATCHLIGHTS DUPLOS BRANCOS (Alma e Brilho do Anime)
        const highlightBig = new PIXI.Graphics().circle(-2.2, -2.4, 2.4).fill(0xffffff);
        const highlightSmall = new PIXI.Graphics().circle(2.2, 2.0, 1.3).fill(0xffffff);
        iris.addChild(irisBase, highlightBig, highlightSmall);

        eye.addChild(sclera, iris, lash, lowerLash);
      }

      // Sobrancelhas finas
      const browL = new PIXI.Graphics();
      browL.arc(0, 0, 18, Math.PI * 1.15, Math.PI * 1.8).stroke({ color: 0x483256, width: 2.5, cap: 'round' });
      browL.position.set(-21, -19);

      const browR = new PIXI.Graphics();
      browR.arc(0, 0, 18, Math.PI * 1.2, Math.PI * 1.85).stroke({ color: 0x483256, width: 2.5, cap: 'round' });
      browR.position.set(21, -19);

      // Boca anime delicada
      const mouth = new PIXI.Graphics();
      mouth.moveTo(-9, 0).quadraticCurveTo(0, 4, 9, 0).stroke({ color: 0x9e4c5e, width: 2.5, cap: 'round' });
      mouth.position.set(0, 36);

      // Franja Anime pontiaguda com mechas laterais e Hair Halo
      const fringe = new PIXI.Container();
      const hairGeo = new PIXI.Graphics();
      hairGeo.poly([-48, -35, -54, 18, -44, 48, -40, 15, -45, -20]).fill(0x563e77);
      hairGeo.poly([48, -35, 54, 18, 44, 48, 40, 15, 45, -20]).fill(0x563e77);
      hairGeo.poly([
        -48, -38, -32, 2, -22, -18, -12, 10, -2, -16,
        10, 8, 20, -16, 32, 2, 48, -38, 0, -68
      ]).fill(0x523b72).stroke({ color: 0x76569e, width: 2 });
      const halo = new PIXI.Graphics();
      halo.arc(0, -42, 38, Math.PI * 1.15, Math.PI * 1.85).stroke({ color: 0xb599dd, width: 3, alpha: 0.65 });
      fringe.addChild(hairGeo, halo);

      const ahoge = new PIXI.Graphics();
      ahoge.moveTo(0, -64).bezierCurveTo(-12, -88, 18, -94, 26, -82).stroke({ color: 0x6e4e94, width: 3, cap: 'round' });
      ahoge.name = "ahoge";

      const sweatDrop = new PIXI.Graphics();
      sweatDrop.poly([0, -14, 6, 0, 0, 6, -6, 0]).fill({ color: 0x60d2ff, alpha: 0.85 });
      sweatDrop.position.set(38, -26);
      sweatDrop.visible = false;
      sweatDrop.name = "sweatDrop";

      const sparkles = new PIXI.Container();
      sparkles.name = "sparkles";
      sparkles.visible = false;
      for (const [sx, sy] of [[-45, -70], [42, -65], [52, -10]]) {
        const star = new PIXI.Graphics();
        star.poly([0, -8, 2, -2, 8, 0, 2, 2, 0, 8, -2, 2, -8, 0, -2, -2]).fill(0xffec70);
        star.position.set(sx, sy);
        sparkles.addChild(star);
      }

      head.addChild(face, commL, commR, blushL, blushR, browL, browR, eyeL, eyeR, mouth, fringe, ahoge, sweatDrop, sparkles);

      // Mini-Drone Mascote Flutuante "Bit"
      const bitDrone = new PIXI.Container();
      bitDrone.name = "bitDrone";
      bitDrone.position.set(85, -130);
      const droneBody = new PIXI.Graphics();
      droneBody.circle(0, 0, 11).fill(0x142032).stroke({ color: 0x2ee4b0, width: 2 });
      droneBody.circle(0, 0, 6).fill(0x2ee4b0);
      droneBody.circle(-2, -2, 2).fill(0xffffff);
      const droneWingL = new PIXI.Graphics().ellipse(-14, -4, 5, 2).fill({ color: 0x43d17d, alpha: 0.6 });
      const droneWingR = new PIXI.Graphics().ellipse(14, -4, 5, 2).fill({ color: 0x43d17d, alpha: 0.6 });
      bitDrone.addChild(droneBody, droneWingL, droneWingR);

      // Tela HUD Holográfica de Diagnósticos
      const hudPanel = new PIXI.Container();
      hudPanel.name = "hudPanel";
      hudPanel.position.set(40, -40);
      hudPanel.visible = false;
      const hudBg = new PIXI.Graphics();
      hudBg.roundRect(0, 0, 56, 38, 6).fill({ color: 0x10283c, alpha: 0.65 }).stroke({ color: 0x2ee4b0, width: 1.5 });
      hudBg.rect(6, 8, 28, 3).fill(0x43d17d);
      hudBg.rect(6, 16, 44, 2).fill({ color: 0x2ee4b0, alpha: 0.8 });
      hudBg.rect(6, 22, 34, 2).fill({ color: 0x2ee4b0, alpha: 0.6 });
      hudBg.rect(6, 28, 20, 2).fill({ color: 0x2ee4b0, alpha: 0.4 });
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

      if (s.foco_visual === 'core') {
        this.walkTargetOffset = -42;
        this.walking = true;
      } else if (s.foco_visual === 'x99') {
        this.walkTargetOffset = 42;
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

      // LOCAMOÇÃO & PATRULHA (WALK CYCLE DE ANIME)
      if (!this.reducedMotion) {
        if (now >= this.nextPatrolTime) {
          this.walking = Math.random() > 0.25;
          if (this.walking) {
            this.walkTargetOffset = (Math.random() * 90) - 45;
          }
          this.nextPatrolTime = now + 3500 + Math.random() * 4000;
        }

        const distToTarget = this.walkTargetOffset - this.walkOffset;
        if (Math.abs(distToTarget) > 2 && this.walking) {
          this.walkDirection = distToTarget > 0 ? 1 : -1;
          const speed = 28 * (0.8 + motion * 0.5);
          this.walkOffset += this.walkDirection * speed * dt;
          this.stepPhase += dt * 5.2 * (0.8 + motion * 0.4);
        } else {
          this.stepPhase = M.smoothExp(this.stepPhase, 0, dt, 4);
        }
      }

      const isWalking = Math.abs(Math.sin(this.stepPhase)) > 0.05;
      const walkBob = isWalking ? Math.abs(Math.sin(this.stepPhase)) * 3.8 : 0;
      const legSwing = isWalking ? Math.sin(this.stepPhase) * 0.32 : 0;
      const armSwing = isWalking ? Math.sin(this.stepPhase) * 0.22 : 0;

      r.root.x=170+alive.weightShift*.22+(this.walkOffset||0);
      r.root.y = 280 + alive.breath - walkBob;

      const targetScaleX = (r.root._targetScale || 1) * (this.walkDirection || 1);
      r.root.scale.x = M.smoothExp(r.root.scale.x, targetScaleX, dt, 6);
      const scY = r.root._targetScale || 1;
      r.root.scale.y = M.smoothExp(r.root.scale.y, scY, dt, 7);

      r.legL.rotation = M.smoothExp(r.legL.rotation, (r.legL._targetRotation || 0) + legSwing, dt, 12);
      r.legR.rotation = M.smoothExp(r.legR.rotation, (r.legR._targetRotation || 0) - legSwing, dt, 12);

      r.torso.rotation = M.smoothExp(r.torso.rotation, (r.torso._semanticRotation || 0) + alive.weightShift * .0025, dt, 5);
      r.hairBack.rotation = alive.hairLag + (isWalking ? -this.walkDirection * 0.04 : 0);

      let headTilt = (r.head._targetRotation || 0) + alive.headMicro;
      if (this.mouseTarget.active) {
        headTilt += this.mouseTarget.x * 0.04;
      }
      r.head.rotation = M.smoothExp(r.head.rotation, headTilt, dt, 9);

      r.armL.rotation = M.smoothExp(r.armL.rotation, (r.armL._targetRotation || 0) - armSwing, dt, 7);
      r.armR.rotation = M.smoothExp(r.armR.rotation, (r.armR._targetRotation || 0) + armSwing, dt, 7);
      r.forearmL.rotation = M.smoothExp(r.forearmL.rotation, r.forearmL._targetRotation || 0, dt, 8);
      r.forearmR.rotation = M.smoothExp(r.forearmR.rotation, r.forearmR._targetRotation || 0, dt, 8);

      r.browL.rotation = M.smoothExp(r.browL.rotation, r.browL._targetRotation || 0, dt, 10);
      r.browR.rotation = M.smoothExp(r.browR.rotation, r.browR._targetRotation || 0, dt, 10);

      // OLHAR DINÂMICO (MOUSE TRACKING + SACCADES)
      let lookPoint = this.#lookTarget(s);
      if (this.mouseTarget.active && (now - this.lastMouseMove < 3000)) {
        lookPoint = {
          x: this.mouseTarget.x * 3.2,
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

      const blink = !this.reducedMotion && this.motion.blink.update(now);
      r.eyeL.scale.y = M.smoothExp(r.eyeL.scale.y, blink ? .08 : 1, dt, 34);
      r.eyeR.scale.y = M.smoothExp(r.eyeR.scale.y, blink ? .08 : 1, dt, 34);

      const mouthTarget = s.falando && motion > 0
        ? 1.1 + Math.abs(Math.sin(t * 8.5)) * 1.6
        : (s.expressao === 'SERENO' || s.expressao === 'RECUPERANDO' ? .75 : 1);
      r.mouth.scale.y = M.smoothExp(r.mouth.scale.y, mouthTarget, dt, 16);
      r.mouth.scale.x = M.smoothExp(r.mouth.scale.x, s.falando ? 1.25 : 1.0, dt, 12);

      if (r.ahoge) {
        r.ahoge.rotation = Math.sin(t * 3.5) * 0.08 + alive.hairLag * 1.5;
      }

      if (r.bitDrone) {
        r.bitDrone.x = 88 + Math.sin(t * 1.6) * 12;
        r.bitDrone.y = -135 + Math.cos(t * 1.2) * 9 + alive.breath * 0.4;
      }

      if (r.hudPanel && r.hudPanel.visible) {
        r.hudPanel.y = -42 + Math.sin(t * 2.4) * 3;
      }
    }
  }

  window.AtlasAvatarEngine = Object.freeze({ AtlasAvatarEngine, POLICY, MODES, EXPRESSIONS });
})();
