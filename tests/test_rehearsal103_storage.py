"""Store-observer guard tests; actual Linux ownership proof remains in preflight."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import stat
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from ops.rehearsal103 import storage_probe
from tools.rehearsal101 import Failure, LABEL
from tools.rehearsal103 import validate_store_mounts


class StorageProbeTest(unittest.TestCase):
    def test_permission_denial_is_fixed_category_then_owner_access_measures_real_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample").write_bytes(b"synthetic" * 100)
            with patch.dict(storage_probe.ROOTS, {"grafana": root}, clear=True):
                output = io.StringIO()
                with patch.object(storage_probe.os, "walk", side_effect=PermissionError("PRIVATE_NATIVE_PATH_103")), redirect_stdout(output):
                    self.assertEqual(storage_probe.main(["measure", "grafana"]), 1)
                self.assertEqual(json.loads(output.getvalue()), {"status": "error", "category": "permission-denied"})
                self.assertNotIn("PRIVATE_NATIVE", output.getvalue())
                measured = storage_probe.measure("grafana")
                self.assertEqual(measured["status"], "ok")
                self.assertGreaterEqual(measured["allocated_bytes"], 900)

    def test_unknown_role_never_becomes_an_arbitrary_path_or_echo(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(storage_probe.main(["measure", "/PRIVATE_PATH_103"]), 1)
        self.assertEqual(json.loads(output.getvalue()), {"status": "error", "category": "invalid-role"})
        self.assertNotIn("PRIVATE_PATH", output.getvalue())

    def test_symlink_root_or_file_is_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            (target / "sample").write_bytes(b"synthetic")
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Native symlink permission unavailable; Linux preflight/suite repeats this guard")
            with self.assertRaisesRegex(storage_probe.ProbeError, "symlink"):
                storage_probe.allocated_tree(link)
            with self.assertRaisesRegex(storage_probe.ProbeError, "symlink"):
                storage_probe.allocated_tree(root)

    def test_foreign_device_is_rejected(self):
        value = SimpleNamespace(st_mode=stat.S_IFREG, st_dev=2)
        with patch.object(Path, "lstat", return_value=value):
            with self.assertRaisesRegex(storage_probe.ProbeError, "unexpected-device"):
                storage_probe.checked_stat(Path("ignored"), 1)

    def test_only_exact_owned_readonly_volume_mounts_are_accepted(self):
        info = {"Config": {"Labels": {LABEL: "unit-owner", "com.docker.compose.project": "unit-project"}},
            "Mounts": [{"Destination": destination, "Name": "unit-project_" + name, "Type": "volume", "RW": False}
                for destination, name in (("/metrics", "metrics"), ("/grafana", "grafana"))]}
        validate_store_mounts(info, "unit-project", "unit-owner")
        for field, changed in (("RW", True), ("Name", "foreign-volume"), ("Type", "bind")):
            original = info["Mounts"][0][field]
            info["Mounts"][0][field] = changed
            with self.assertRaises(Failure):
                validate_store_mounts(info, "unit-project", "unit-owner")
            info["Mounts"][0][field] = original
