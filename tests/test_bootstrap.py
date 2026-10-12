import importlib
from pathlib import Path
import unittest


class ProjectBootstrapTest(unittest.TestCase):
    def test_backend_package_resolves_to_this_repository(self):
        package = importlib.import_module("backend")
        expected = Path(__file__).resolve().parents[1] / "backend" / "__init__.py"
        self.assertEqual(Path(package.__file__).resolve(), expected)


if __name__ == "__main__":
    unittest.main()
