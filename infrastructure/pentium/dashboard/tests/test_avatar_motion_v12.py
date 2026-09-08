from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

class AvatarMotionV12Tests(unittest.TestCase):
    def test_motion_module_exports_smoothing_blink_and_secondary_motion(self):
        source = (ROOT / 'atlas-avatar-motion.js').read_text(encoding='utf-8')
        for token in ('smoothExp', 'BlinkScheduler', 'SaccadeController', 'SecondaryMotion', 'MotionState'):
            self.assertIn(token, source)

    def test_motion_module_is_syntax_valid(self):
        subprocess.run(['node', '--check', str(ROOT / 'atlas-avatar-motion.js')], check=True)

    def test_motion_behaviour_is_bounded_and_progressive(self):
        script = r"""
const fs=require('fs'),vm=require('vm');
global.window=global;
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
const M=window.AtlasAvatarMotion;
const a=M.smoothExp(0,10,0.016,12);
if(!(a>0 && a<10)) throw new Error('smoothing');
const blink=new M.BlinkScheduler(()=>0.5);
const first=blink.nextAt(1000);
if(first<3000 || first>6500) throw new Error('blink bound');
const s=new M.SaccadeController(()=>0.5);
const p=s.update(1.0,{x:3,y:-2},1);
if(Math.abs(p.x)>3 || Math.abs(p.y)>2) throw new Error('saccade bound');
const sec=new M.SecondaryMotion(0,0.18,11);
const v=sec.update(1,0.016);
if(!(v>0 && v<1)) throw new Error('secondary');
const st=new M.MotionState();
const out=st.step({modo:'OCIOSO', intensidade_movimento:.6, velocidade_movimento:.5, falando:false, ouvindo:false, pensando:false},0.016,1.2);
for(const k of ['breath','weightShift','headMicro','hairLag']) if(!Number.isFinite(out[k])) throw new Error(k);
"""
        path = ROOT / 'atlas-avatar-motion.js'
        result = subprocess.run(['node','-e',script,str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__ == '__main__':
    unittest.main()

class AvatarMotionWiringTests(unittest.TestCase):
    def test_engine_uses_motion_state_and_articulated_rig(self):
        engine=(ROOT/'atlas-avatar-engine.js').read_text(encoding='utf-8')
        for token in ('AtlasAvatarMotion','MotionState','forearmL','forearmR','handL','handR','torso','hairBack'):
            self.assertIn(token,engine)
        self.assertIn('motion.step',engine)
        self.assertIn('saccade.update',engine)
        self.assertIn('blink.update',engine)

    def test_dashboard_loads_motion_before_engine(self):
        html=(ROOT/'dashboard.html').read_text(encoding='utf-8')
        motion=html.index('/assets/atlas-avatar-motion.js')
        engine=html.index('/assets/atlas-avatar-engine.js')
        self.assertLess(motion,engine)

class AvatarMotionPackagingTests(unittest.TestCase):
    def test_dashboard_server_and_installer_package_motion_asset(self):
        server=(ROOT/'atlas_dashboard.py').read_text(encoding='utf-8')
        installer=(ROOT/'install-user.sh').read_text(encoding='utf-8')
        self.assertIn('atlas-avatar-motion.js',server)
        self.assertIn('atlas-avatar-motion.js',installer)
