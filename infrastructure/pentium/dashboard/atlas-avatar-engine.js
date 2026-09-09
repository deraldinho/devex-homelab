(() => {
  "use strict";
  const MODES=new Set(["OCIOSO","OBSERVANDO","CONVERSANDO","REAGINDO"]);
  const EXPRESSIONS=new Set(["SERENO","ENGAJADO","CURIOSO","ATENTO","PREOCUPADO","SOB_PRESSAO","RECUPERANDO"]);
  const POLICY = Object.freeze({ defaultTransitionMs: 400, criticalTransitionMs: 160, minArchetypeDwellMs: 1200 });
  const M=window.AtlasAvatarMotion;

  class AtlasAvatarEngine {
    constructor(host){
      this.host=host;this.ready=false;this.state=null;this.app=null;this.rig=null;
      this.startedAt=performance.now();this.motion=M?new M.MotionState():null;
      this.reducedMotion=window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches===true;
      this.hidden=document.hidden;document.addEventListener("visibilitychange",()=>{this.hidden=document.hidden;});
    }
    async init(){
      if(!this.host||!window.PIXI||!M)return false;
      try{const app=new PIXI.Application();await app.init({resizeTo:this.host,backgroundAlpha:0,antialias:true,autoDensity:true});
        this.host.replaceChildren(app.canvas);this.app=app;this.rig=this.#buildRig();app.stage.addChild(this.rig.root);app.ticker.add(t=>this.#tick(t.deltaMS));this.host.classList.add("pixi-ready");this.ready=true;return true;
      }catch(error){this.host.dataset.rendererError=error?.name||"PixiInitError";return false;}
    }
    render(state){if(!this.ready||!state||!MODES.has(state.modo)||!EXPRESSIONS.has(state.expressao))return false;this.state=state;this.#applyState();return true;}

    #arm(side){
      const upper=new PIXI.Container();const sign=side==='L'?-1:1;upper.position.set(49*sign,-82);
      upper.addChild(new PIXI.Graphics().roundRect(side==='L'?-15:-10,0,25,58,12).fill(0x14253f));
      const forearm=new PIXI.Container();forearm.position.set(0,49);forearm.addChild(new PIXI.Graphics().roundRect(-11,0,22,55,10).fill(0x1a2d49));
      const hand=new PIXI.Graphics().ellipse(0,56,10,13).fill(0xf0d4c6);forearm.addChild(hand);upper.addChild(forearm);return {upper,forearm,hand};
    }
    #buildRig(){
      const root=new PIXI.Container();root.position.set(170,280);
      const legL=new PIXI.Container();legL.position.set(-25,28);legL.addChild(new PIXI.Graphics().roundRect(-16,0,29,105,13).fill(0x172238),new PIXI.Graphics().roundRect(-20,91,36,20,8).fill(0x0c111b));
      const legR=new PIXI.Container();legR.position.set(25,28);legR.addChild(new PIXI.Graphics().roundRect(-13,0,29,105,13).fill(0x172238),new PIXI.Graphics().roundRect(-16,91,36,20,8).fill(0x0c111b));
      const torso=new PIXI.Container();
      const body=new PIXI.Graphics().roundRect(-52,-112,104,150,28).fill(0x14253f).stroke({color:0x273d60,width:3});
      const shirt=new PIXI.Graphics().poly([-28,-95,28,-95,42,15,-42,15]).fill(0xf2f4f8);torso.addChild(body,shirt);
      const hairBack=new PIXI.Graphics().ellipse(0,-154,74,92).fill(0x49376e).stroke({color:0x7d61ad,width:3});
      const head=new PIXI.Container();head.position.set(0,-155);const face=new PIXI.Graphics().ellipse(0,0,55,67).fill(0xf0d4c6);const fringe=new PIXI.Graphics().poly([-52,-18,-38,-55,-4,-68,30,-58,52,-22,28,-40,4,-50,-18,-35]).fill(0x5a4380);
      const eyeL=new PIXI.Container();eyeL.position.set(-19,-4);const eyeR=new PIXI.Container();eyeR.position.set(19,-4);
      for(const eye of [eyeL,eyeR]){eye.addChild(new PIXI.Graphics().ellipse(0,0,10,7).fill(0xf8ffff));const iris=new PIXI.Graphics().circle(0,0,5).fill(0x43d17d);iris.name="iris";eye.addChild(iris);}
      const mouth=new PIXI.Graphics().roundRect(-12,23,24,4,2).fill(0x9a5662);const browL=new PIXI.Graphics().roundRect(-30,-22,21,3,2).fill(0x4a3658);const browR=new PIXI.Graphics().roundRect(9,-22,21,3,2).fill(0x4a3658);head.addChild(face,fringe,browL,browR,eyeL,eyeR,mouth);
      const L=this.#arm('L'),R=this.#arm('R');root.addChild(legL,legR,hairBack,torso,L.upper,R.upper,head);
      return {root,torso,hairBack,head,eyeL,eyeR,mouth,browL,browR,armL:L.upper,armR:R.upper,forearmL:L.forearm,forearmR:R.forearm,handL:L.hand,handR:R.hand,legL,legR};
    }

    #lookTarget(s){const d=String(s.direcao_olhar||'centro').toLowerCase();return{x:d==='esquerda'?-3:d==='direita'?3:0,y:d==='cima'?-2:d==='baixo'?2:0};}
    #applyState(){
      const s=this.state,r=this.rig,i=s.intensidade_expressao;
      const curious=s.expressao==='CURIOSO'||s.duvida_identidade;r.head._targetRotation=curious?.08+i*.06:0;
      const g=String(s.gesto_atual||'NENHUM').toUpperCase();r.armL._targetRotation=g==='ACENO'?-.72:g==='DUVIDA'?-.28:g==='FECHADO'?.2:.08;r.armR._targetRotation=g==='ESCUTA'?.48:g==='ABERTO'?.22:g==='SURPRESA'?-.34:-.08;
      r.forearmL._targetRotation=g==='ACENO'?-.45:g==='DUVIDA'?-.2:0;r.forearmR._targetRotation=g==='ESCUTA'?-.62:g==='ABERTO'?.12:g==='SURPRESA'?.28:0;
      const pressure=s.expressao==='SOB_PRESSAO'||s.expressao==='PREOCUPADO';r.browL._targetRotation=pressure?-.12:0;r.browR._targetRotation=pressure?.12:0;
      r.root._targetScale=s.modo==='REAGINDO'?1.025:1;r.legL._targetRotation=g==='ALIVIO'?-.015:0;r.legR._targetRotation=g==='ALIVIO'?.015:0;
    }

    #tick(deltaMs){
      if(!this.ready||!this.state||this.hidden)return;const s=this.state,r=this.rig,dt=Math.min(.05,Math.max(0,deltaMs/1000));const t=(performance.now()-this.startedAt)/1000;const motion=this.reducedMotion?0:s.intensidade_movimento;
      const alive=this.motion.step({...s,intensidade_movimento:motion},dt,t);r.root.y=280+alive.breath;r.root.x=170+alive.weightShift*.22;r.torso.rotation=M.smoothExp(r.torso.rotation,alive.weightShift*.0025,dt,5);r.hairBack.rotation=alive.hairLag;
      r.head.rotation=M.smoothExp(r.head.rotation,(r.head._targetRotation||0)+alive.headMicro,dt,9);r.armL.rotation=M.smoothExp(r.armL.rotation,r.armL._targetRotation||0,dt,7);r.armR.rotation=M.smoothExp(r.armR.rotation,r.armR._targetRotation||0,dt,7);r.forearmL.rotation=M.smoothExp(r.forearmL.rotation,r.forearmL._targetRotation||0,dt,8);r.forearmR.rotation=M.smoothExp(r.forearmR.rotation,r.forearmR._targetRotation||0,dt,8);
      r.browL.rotation=M.smoothExp(r.browL.rotation,r.browL._targetRotation||0,dt,10);r.browR.rotation=M.smoothExp(r.browR.rotation,r.browR._targetRotation||0,dt,10);r.legL.rotation=M.smoothExp(r.legL.rotation,r.legL._targetRotation||0,dt,6);r.legR.rotation=M.smoothExp(r.legR.rotation,r.legR._targetRotation||0,dt,6);
      const sc=r.root._targetScale||1;r.root.scale.x=M.smoothExp(r.root.scale.x,sc,dt,7);r.root.scale.y=M.smoothExp(r.root.scale.y,sc,dt,7);
      const gaze=this.motion.saccade.update(dt,this.#lookTarget(s),motion,performance.now());for(const eye of [r.eyeL,r.eyeR]){const iris=eye.getChildByName('iris');iris.x=gaze.x;iris.y=gaze.y;}
      const blink=!this.reducedMotion&&this.motion.blink.update(performance.now());r.eyeL.scale.y=M.smoothExp(r.eyeL.scale.y,blink?.12:1,dt,32);r.eyeR.scale.y=M.smoothExp(r.eyeR.scale.y,blink?.12:1,dt,32);
      const mouthTarget=s.falando&&motion>0?1.1+Math.abs(Math.sin(t*8.5))*1.5:(s.expressao==='SERENO'||s.expressao==='RECUPERANDO'?.7:1);r.mouth.scale.y=M.smoothExp(r.mouth.scale.y,mouthTarget,dt,16);
    }
  }
  window.AtlasAvatarEngine=Object.freeze({AtlasAvatarEngine,POLICY,MODES,EXPRESSIONS});
})();
