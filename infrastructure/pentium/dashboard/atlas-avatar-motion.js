(() => {
  "use strict";
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,Number(v)||0));
  const smoothExp=(current,target,dt,speed=10)=>current+(target-current)*(1-Math.exp(-Math.max(0,dt)*speed));

  class BlinkScheduler {
    constructor(rng=Math.random){this.rng=rng;this.next=0;this.until=0;}
    nextAt(now){const interval=2200+clamp(this.rng(),0,1)*3200;this.next=now+interval;return this.next;}
    update(now){if(!this.next)this.nextAt(now);if(now>=this.next){this.until=now+80+this.rng()*60;this.nextAt(now);}return now<this.until;}
  }

  class SaccadeController {
    constructor(rng=Math.random){this.rng=rng;this.x=0;this.y=0;this.tx=0;this.ty=0;this.next=0;}
    update(dt,look,motion=1,now=performance?.now?.()??0){
      if(now>=this.next){const jitter=(this.rng()-.5)*1.2*motion;this.tx=clamp((look?.x||0)+jitter,-3,3);this.ty=clamp((look?.y||0)+(this.rng()-.5)*.8*motion,-2,2);this.next=now+600+this.rng()*1400;}
      this.x=smoothExp(this.x,this.tx,dt,7);this.y=smoothExp(this.y,this.ty,dt,7);return {x:this.x,y:this.y};
    }
  }

  class SecondaryMotion {
    constructor(value=0,damping=.16,stiffness=14){this.value=value;this.velocity=0;this.damping=damping;this.stiffness=stiffness;}
    update(target,dt){const step=Math.min(.05,Math.max(0,dt));this.velocity+=(target-this.value)*this.stiffness*step;this.velocity*=Math.exp(-this.damping*60*step);this.value+=this.velocity*step;return this.value;}
  }

  class MotionState {
    constructor(rng=Math.random){this.rng=rng;this.blink=new BlinkScheduler(rng);this.saccade=new SaccadeController(rng);this.hair=new SecondaryMotion();}
    step(state,dt,t){
      const intensity=Math.max(0.4,clamp(state?.intensidade_movimento,0,1));
      const speed=0.85+clamp(state?.velocidade_movimento,0,1)*1.4;
      const active=state?.modo==='REAGINDO'?1.4:state?.modo==='CONVERSANDO'?1.2:1;
      const floatHover=Math.sin(t*speed*0.9)*5.5*intensity*active;
      const breath=floatHover+Math.sin(t*speed*1.8)*2.8*intensity;
      const weightShift=Math.sin(t*speed*0.5+0.8)*4.5*intensity;
      const headMicro=(Math.sin(t*0.8)+Math.sin(t*1.3)*0.5)*0.035*intensity;
      const hairLag=this.hair.update(headMicro*1.4+weightShift*0.006,dt);
      return {breath,weightShift,headMicro,hairLag};
    }
  }

  window.AtlasAvatarMotion=Object.freeze({clamp,smoothExp,BlinkScheduler,SaccadeController,SecondaryMotion,MotionState});
})();

