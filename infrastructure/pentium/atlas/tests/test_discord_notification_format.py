import unittest
from infrastructure.pentium.atlas.discord_notification_format import format_atlas_alert
class AtlasDiscordNaturalTests(unittest.TestCase):
    def test_natural_message_has_no_hermes_or_alert_prefix(self):
        self.assertEqual(format_atlas_alert("Passei para te avisar que os modelos continuam disponíveis.",
              narrated_by="atlas_llm"),
              "Passei para te avisar que os modelos continuam disponíveis.")
    def test_non_llm_alert_identifies_atlas(self):
        result=format_atlas_alert("Cuidado: serviço offline")
        self.assertTrue(result.startswith("**[ALERTA ATLAS]**"))
        self.assertNotIn("HERMES",result)
    def test_invalid_message_denied(self):
        with self.assertRaises(ValueError):format_atlas_alert("")
        with self.assertRaises(ValueError):format_atlas_alert("x"*2000)
if __name__=="__main__":unittest.main()
