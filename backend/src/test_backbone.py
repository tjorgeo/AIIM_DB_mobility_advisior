import unittest
import json
from database import init_db, get_connection
from seed_data import seed_database
from orchestrator import Orchestrator

class TestMobilityAdvisorBackbone(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """
        Runs once before any tests. Re-builds and seeds the test database.
        """
        print("🔧 Setting up test suite: building and seeding database...")
        init_db()
        seed_database()
        cls.orchestrator = Orchestrator()

    def test_database_connects(self):
        """
        Confirms the Postgres database is reachable.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS ok")
        self.assertEqual(cursor.fetchone()["ok"], 1, "Database connection failed.")
        conn.close()

    def test_personas_seeded(self):
        """
        Verifies that all 5 key traveler personas were seeded.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS n FROM users")
        count = cursor.fetchone()["n"]
        conn.close()
        self.assertEqual(count, 5, "Database must seed precisely 5 personas.")

    def test_pricing_catalog_seeded(self):
        """
        Verifies that the core DB Pricing Catalog was successfully loaded.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS n FROM pricing_catalog")
        count = cursor.fetchone()["n"]
        conn.close()
        self.assertGreater(count, 5, "Database must seed pricing models.")

    def test_orchestration_max_commuter(self):
        """
        Tests E2E pipeline for Frequent Commuter Max.
        - Baseline cost should be around €432 * 12 = €5,184
        - Recommended scenario should cancel pay-as-you-go, add Deutschlandticket (€49/mo = €588/yr)
        - Net savings should be significant
        """
        res = self.orchestrator.run_analysis("persona_max_commuter")
        
        self.assertEqual(res["status"], "ready")
        self.assertEqual(res["customer_name"], "Max Commuter")
        
        # Verify 4 agents outputs are populated in Technical Inspector
        raw = res["raw_agent_payloads"]
        self.assertIn("analyst", raw)
        self.assertIn("forecaster", raw)
        self.assertIn("optimizer", raw)
        self.assertIn("communicator", raw)
        
        # Verify optimizer recommended Scenario
        best_scen = next(s for s in res["summary"]["scenarios"] if s["id"] == res["summary"]["recommended_scenario"])
        
        # Ensure Deutschlandticket is added
        added_subs = [c["service_id"] for c in best_scen["changes"] if c["action"] == "add"]
        self.assertIn("deutschlandticket", added_subs, "Deutschlandticket must be recommended for Max Commuter.")
        
        print("✅ Max Commuter E2E optimization successful.")

    def test_orchestration_clara_consultant(self):
        """
        Tests E2E pipeline for Clara Consultant (BC25, high train travel).
        Upgrading to BC50 should save her more.
        """
        res = self.orchestrator.run_analysis("persona_clara_consultant")
        
        self.assertEqual(res["status"], "ready")
        self.assertEqual(res["customer_name"], "Clara Eco-Consultant")
        
        best_scen = next(s for s in res["summary"]["scenarios"] if s["id"] == res["summary"]["recommended_scenario"])
        added_subs = [c["service_id"] for c in best_scen["changes"] if c["action"] == "add"]
        cancelled_subs = [c["service_id"] for c in best_scen["changes"] if c["action"] == "cancel"]
        
        # Ensure upgrade path
        self.assertIn("bahncard_50_2nd", added_subs)
        self.assertIn("bahncard_25_2nd", cancelled_subs)
        
        print("✅ Clara Consultant E2E optimization successful.")

    def test_orchestration_anna_occasional(self):
        """
        Tests E2E pipeline for Anna Occasional (low travel, high subscription waste).
        Should recommend cancelling Deutschlandticket & Miles, saving her €768/yr.
        """
        res = self.orchestrator.run_analysis("persona_anna_occasional")
        
        self.assertEqual(res["status"], "ready")
        
        best_scen = next(s for s in res["summary"]["scenarios"] if s["id"] == res["summary"]["recommended_scenario"])
        cancelled_subs = [c["service_id"] for c in best_scen["changes"] if c["action"] == "cancel"]
        
        # Ensure cancellation of unused accounts
        self.assertIn("deutschlandticket", cancelled_subs)
        self.assertIn("miles_sharing", cancelled_subs)
        
        print("✅ Anna Occasional E2E optimization successful.")

    def test_orchestration_lukas_executive(self):
        """
        Tests E2E pipeline for Lukas Corporate Lead.
        Heavy long-distance, should recommend BC100 1st Class.
        """
        res = self.orchestrator.run_analysis("persona_lukas_executive")
        
        self.assertEqual(res["status"], "ready")
        
        best_scen = next(s for s in res["summary"]["scenarios"] if s["id"] == res["summary"]["recommended_scenario"])
        added_subs = [c["service_id"] for c in best_scen["changes"] if c["action"] == "add"]
        cancelled_subs = [c["service_id"] for c in best_scen["changes"] if c["action"] == "cancel"]
        
        self.assertIn("bahncard_100_1st", added_subs)
        self.assertIn("bahncard_50_1st", cancelled_subs)
        
        print("✅ Lukas E2E optimization successful.")

if __name__ == "__main__":
    unittest.main()
