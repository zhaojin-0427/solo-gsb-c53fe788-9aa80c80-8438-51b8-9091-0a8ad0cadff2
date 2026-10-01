import os
import tempfile
import unittest

os.environ.setdefault("PV_DB_PATH", os.path.join(tempfile.gettempdir(), "pv-test-trials.db"))

from fastapi.testclient import TestClient

from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def payload(self):
        return {
            "title": "测试",
            "groups": [
                {"id": "G1", "voc": "40.00", "isc": "10.00"},
                {"id": "G2", "voc": "40.00", "isc": "8.00"},
                {"id": "G3", "voc": "38.00", "isc": "9.00"},
            ],
            "baseline": [["G1", "G3"], ["G2"]],
        }

    def test_calculate_success(self):
        response = self.client.post("/api/calculate", json=self.payload())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["candidateCount"], 5)
        self.assertIn("segments", data["baseline"]["curve"])
        self.assertGreater(data["optimal"]["peak"]["power"], 0)

    def test_invalid_parameters_rejected(self):
        payload = self.payload()
        payload["groups"][0]["voc"] = "100.123"
        response = self.client.post("/api/calculate", json=payload)
        self.assertEqual(response.status_code, 400)

        payload = self.payload()
        payload["groups"][1]["isc"] = "30.01"
        response = self.client.post("/api/calculate", json=payload)
        self.assertEqual(response.status_code, 400)

        payload = self.payload()
        payload["baseline"] = [["G1", "G3"]]
        response = self.client.post("/api/calculate", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("G2", response.json()["detail"])

    def test_record_save_reopen_and_delete(self):
        calculated = self.client.post("/api/calculate", json=self.payload())
        self.assertEqual(calculated.status_code, 200)
        result = calculated.json()

        saved = self.client.post("/api/records", json={
            "title": "保存测试",
            "input": self.payload(),
            "result": result,
        })
        self.assertEqual(saved.status_code, 201)
        record_id = saved.json()["id"]

        listing = self.client.get("/api/records")
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(any(item["id"] == record_id for item in listing.json()))

        reopened = self.client.get(f"/api/records/{record_id}")
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.json()["payload"]["input"]["groups"][0]["id"], "G1")
        self.assertEqual(
            reopened.json()["payload"]["result"]["optimal"]["peak"],
            result["optimal"]["peak"],
        )

        deleted = self.client.delete(f"/api/records/{record_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get(f"/api/records/{record_id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
