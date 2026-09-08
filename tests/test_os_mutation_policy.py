from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "os-mutation-policy.py"
POLICY = ROOT / "MUTABILITY.json"

loader = importlib.machinery.SourceFileLoader("os_mutation_policy_test_module", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
module = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = module
loader.exec_module(module)


class OsMutationPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = module.load_policy(POLICY)

    def test_usr_local_is_mutable(self) -> None:
        result = module.classify_path(self.policy, "/usr/local/bin/example")
        self.assertEqual(result["classification"], "mutable")

    def test_opt_is_mutable(self) -> None:
        result = module.classify_path(self.policy, "/opt/example/bin/tool")
        self.assertEqual(result["classification"], "mutable")

    def test_environment_is_mutable_exact_path(self) -> None:
        result = module.classify_path(self.policy, "/etc/environment")
        self.assertEqual(result["classification"], "mutable")

    def test_systemd_definition_is_mutable_but_guarded(self) -> None:
        result = module.classify_path(self.policy, "/etc/systemd/system/example.service")
        self.assertEqual(result["classification"], "mutable")
        self.assertIn("service enablement", result["guard"])

    def test_shadow_requires_candidate(self) -> None:
        result = module.classify_path(self.policy, "/etc/shadow")
        self.assertEqual(result["classification"], "candidate-required")

    def test_boot_requires_candidate(self) -> None:
        result = module.classify_path(self.policy, "/boot/vmlinuz-test")
        self.assertEqual(result["classification"], "candidate-required")

    def test_reaper_binary_requires_candidate(self) -> None:
        result = module.classify_path(self.policy, "/mnt/data/ubuntu-desktop-workspace/apps/REAPER/reaper")
        self.assertEqual(result["classification"], "candidate-required")

    def test_unknown_system_path_requires_candidate(self) -> None:
        result = module.classify_path(self.policy, "/usr/bin/example")
        self.assertEqual(result["classification"], "candidate-required")

    def test_path_traversal_rejected(self) -> None:
        with self.assertRaises(ValueError):
            module.classify_path(self.policy, "/opt/../etc/shadow")

    def test_normal_package_is_mutable(self) -> None:
        result = module.classify_package(self.policy, "cmake")
        self.assertEqual(result["classification"], "mutable")

    def test_kernel_package_requires_candidate(self) -> None:
        result = module.classify_package(self.policy, "linux-image-amd64")
        self.assertEqual(result["classification"], "candidate-required")

    def test_core_package_requires_candidate(self) -> None:
        result = module.classify_package(self.policy, "systemd")
        self.assertEqual(result["classification"], "candidate-required")


if __name__ == "__main__":
    unittest.main()
