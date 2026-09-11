import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[2]

class ActionChatPackagingTests(unittest.TestCase):
    def test_atlas_installer_packages_action_chat_runtime_without_voice_restart(self):
        text=(ROOT/'install-user.sh').read_text(encoding='utf-8')
        for name in ('action_plan.py','action_plan_store.py','action_planner.py','action_policy.py','action_executors.py','chat_inbox.py','cognitive_observability.py'):
            self.assertIn(name,text)
        self.assertNotIn('restart atlas-voice.service',text)
        self.assertNotIn('enable atlas-voice.service',text)

    def test_dashboard_installer_packages_chat_and_event_store(self):
        text=(ROOT.parent/'dashboard'/'install-user.sh').read_text(encoding='utf-8')
        self.assertIn('dashboard_chat.py',text)
        self.assertIn('dashboard_event_store.py',text)
        self.assertNotIn('atlas-voice.service',text)

    def test_ci_contains_action_chat_markers(self):
        foundation=(REPO/'.github/workflows/foundation-ci.yml').read_text(encoding='utf-8')
        avatar=(REPO/'.github/workflows/atlas-avatar-ci.yml').read_text(encoding='utf-8')
        self.assertIn('DEVEX_HOMELAB_ATLAS_ACTION_PLAN_CHAT_PASS',foundation)
        self.assertIn('DEVEX_HOMELAB_ATLAS_DASHBOARD_CHAT_PASS',avatar)

if __name__=='__main__':unittest.main()
