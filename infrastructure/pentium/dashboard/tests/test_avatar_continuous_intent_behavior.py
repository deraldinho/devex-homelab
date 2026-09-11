import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "atlas-avatar-renderer.js"
ENGINE = ROOT / "atlas-avatar-engine.js"


def run_node(script: str):
    return subprocess.run(["node", "-e", script], capture_output=True, text=True)


class ContinuousIntentBehaviorTests(unittest.TestCase):
    def test_active_projects_stable_tracking_behavior(self):
        script = f"""
global.window={{}}; global.document={{getElementById:()=>null}}; global.performance={{now:()=>0}};
require({str(RENDERER)!r});
const p=window.AtlasAvatarRenderer.projectIntentBehavior({{communication_mode:'silent_tracking',intent:{{intencao_id:'i1',estado:'ATIVA',assunto_id:'observacao:core',entidade_id:'core'}}}});
console.log(JSON.stringify(p));
"""
        result = run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"target":"services"', result.stdout)
        self.assertIn('"petMode":"SIT"', result.stdout)
        self.assertIn('"expressao":"ATENTO"', result.stdout)
        self.assertIn('"gesto_atual":"ESCUTA"', result.stdout)

    def test_waiting_projects_chat_listening_behavior(self):
        script = f"""
global.window={{}}; global.document={{getElementById:()=>null}}; global.performance={{now:()=>0}};
require({str(RENDERER)!r});
const p=window.AtlasAvatarRenderer.projectIntentBehavior({{intent:{{intencao_id:'i1',estado:'AGUARDANDO',assunto_id:'observacao:core',entidade_id:'core'}}}});
console.log(JSON.stringify(p));
"""
        result = run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"target":"chat"', result.stdout)
        self.assertIn('"petMode":"SIT"', result.stdout)
        self.assertIn('"postura_atual":"ABERTO"', result.stdout)
        self.assertIn('"gesto_atual":"ESCUTA"', result.stdout)

    def test_completed_projects_one_shot_relief_then_patrol(self):
        script = f"""
global.window={{}}; global.document={{getElementById:()=>null}}; global.performance={{now:()=>0}};
require({str(RENDERER)!r});
const p=window.AtlasAvatarRenderer.projectIntentBehavior({{intent:{{intencao_id:'i1',estado:'CONCLUIDA',assunto_id:'observacao:core',entidade_id:'core'}}}});
console.log(JSON.stringify(p));
"""
        result = run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"oneShot":true', result.stdout)
        self.assertIn('"gesto_atual":"ALIVIO"', result.stdout)
        self.assertIn('"returnToPatrol":true', result.stdout)

    def test_apply_is_idempotent_for_same_intent_state(self):
        script = f"""
global.window={{}}; global.document={{getElementById:()=>null}}; global.performance={{now:()=>0}};
require({str(RENDERER)!r});
const calls=[]; const fake={{applyIntentBehavior:(p)=>calls.push(p)}};
const state={{communication_mode:'silent_tracking',intent:{{intencao_id:'i1',estado:'ATIVA',assunto_id:'observacao:core',entidade_id:'core'}}}};
window.AtlasAvatarRenderer.applyIntentBehavior(fake,state);
window.AtlasAvatarRenderer.applyIntentBehavior(fake,state);
console.log(calls.length);
"""
        result = run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual("1", result.stdout.strip())

    def test_overlay_failure_is_isolated_and_retried_on_next_poll(self):
        script = f"""
global.window={{}}; global.document={{getElementById:()=>null}}; global.performance={{now:()=>0}};
require({str(RENDERER)!r});
let calls=0; const fake={{applyIntentBehavior:()=>{{calls+=1;if(calls===1) throw new Error('overlay');}}}};
const state={{intent:{{intencao_id:'i1',estado:'ATIVA',assunto_id:'observacao:core',entidade_id:'core'}}}};
const first=window.AtlasAvatarRenderer.applyIntentBehavior(fake,state);
const second=window.AtlasAvatarRenderer.applyIntentBehavior(fake,state);
console.log(JSON.stringify({{first,second,calls}}));
"""
        result = run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"first":false', result.stdout)
        self.assertIn('"second":true', result.stdout)
        self.assertIn('"calls":2', result.stdout)

    def test_engine_exposes_bounded_intent_overlay_hook(self):
        source = ENGINE.read_text(encoding="utf-8")
        for token in ("applyIntentBehavior", "intentBehavior", "returnToPatrol", "Number.POSITIVE_INFINITY"):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
