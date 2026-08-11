import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

temporary_directory = tempfile.TemporaryDirectory()
os.environ["APP_ROOT"] = str(ROOT)
os.environ["DATABASE_PATH"] = str(Path(temporary_directory.name) / "monitoring.db")

from app import app  # noqa: E402
from feeds.database import initialize  # noqa: E402


class BackendStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        initialize()
        cls.client = app.test_client()

    def test_health_route(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_all_public_routes_are_registered(self) -> None:
        routes = {rule.rule for rule in app.url_map.iter_rules()}
        expected = {
            "/api/health",
            "/api/health/app",
            "/api/health/sources",
            "/api/health/sources/test",
            "/api/sources",
            "/api/sources.yml",
            "/api/sources/yaml",
            "/api/articles",
            "/api/stats",
            "/api/collect",
            "/api/refresh",
            "/api/clusters",
            "/api/clusters/<cluster_id>",
            "/api/viz/heatmap",
            "/api/viz/semantic-map",
            "/api/assistant/status",
            "/api/assistant",
        }
        self.assertTrue(expected.issubset(routes))


if __name__ == "__main__":
    unittest.main()
