#!/usr/bin/env python3

from dataclasses import replace
from pathlib import Path
import unittest

from infrastructure.pentium.agent.managed_inventory import (
    HostNotManagedError,
    ManagedHost,
    ManagedInventory,
    UnknownManagedHostError,
)


class ManagedInventoryTests(unittest.TestCase):
    def make_host(self) -> ManagedHost:
        return ManagedHost(
            host_id="x99",
            enrollment="MANAGED",
            user="deral",
            host="192.168.88.20",
            identity_file=Path("/keys/x99"),
            known_hosts_file=Path("/ssh/known_hosts"),
            platform="windows",
            allowed_reads=frozenset({"uptime"}),
        )

    def test_require_managed_returns_registered_managed_host(self):
        host = self.make_host()
        self.assertEqual(ManagedInventory([host]).require_managed("x99"), host)

    def test_unknown_host_fails_closed(self):
        inventory = ManagedInventory([self.make_host()])
        with self.assertRaises(UnknownManagedHostError):
            inventory.require_managed("ghost")

    def test_non_managed_enrollment_fails_closed(self):
        identified = replace(self.make_host(), enrollment="IDENTIFIED")
        inventory = ManagedInventory([identified])
        with self.assertRaises(HostNotManagedError):
            inventory.require_managed("x99")

    def test_duplicate_host_ids_are_rejected(self):
        host = self.make_host()
        with self.assertRaises(ValueError):
            ManagedInventory([host, host])

    def test_invalid_host_contract_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(self.make_host(), connect_timeout_seconds=0)
        with self.assertRaises(ValueError):
            replace(self.make_host(), host_id="")


if __name__ == "__main__":
    unittest.main()
