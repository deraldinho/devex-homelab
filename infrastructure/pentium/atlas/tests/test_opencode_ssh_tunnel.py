import unittest
from infrastructure.pentium.atlas.opencode_ssh_tunnel import TunnelSpec
class TunnelTests(unittest.TestCase):
    def test_no_public_listener(self):
        command=TunnelSpec().command()
        self.assertIn("127.0.0.1:49375:127.0.0.1:49374",command)
        self.assertEqual(command[-1],"x99")
        self.assertIn("ExitOnForwardFailure=yes",command)
    def test_rejects_shell_injection(self):
        with self.assertRaises(ValueError):
            TunnelSpec(host="x99;echo unsafe").command()
    def test_rejects_invalid_ports(self):
        with self.assertRaises(ValueError):TunnelSpec(listen_port=0).command()
    def test_endpoint_stays_loopback(self):
        self.assertEqual(TunnelSpec().endpoint(),"http://127.0.0.1:49375")
if __name__=="__main__":unittest.main()
