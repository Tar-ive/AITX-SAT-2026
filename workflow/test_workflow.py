import unittest
from pathlib import Path
from daily_deals import categorize, discord_message, parse_command, recommend
class WorkflowTests(unittest.TestCase):
 def test_discord_command_uses_canonical_parser(self): self.assertEqual(parse_command("!deals daily at 9am")["cron"], "0 14 * * *")
 def test_online_wins_near_tie(self):
  groups=categorize([{"title":"A","price":100,"shipping":0,"fulfillment":"offline","condition":"new","baseline_price":120},{"title":"B","price":105,"shipping":0,"fulfillment":"online","condition":"new","baseline_price":120}])
  self.assertEqual(recommend(groups,Path(__file__).with_name("user.md").read_text())[0]["title"],"B")
 def test_daily_message_has_links_but_no_run_identifier(self):
  message=discord_message([{"title":"Example","url":"https://example.test/item","total":99,"store":"Shop","channel":"online","saving_percent":10}],"hidden-run-id")
  self.assertIn("[Example](https://example.test/item)",message)
  self.assertNotIn("hidden-run-id",message)
 def test_store_option_discloses_location_and_stock_link(self):
  message=discord_message([{"title":"Example","url":"https://example.test/item","stock_check_url":"https://example.test/stock","location":"Austin, TX","total":99,"store":"Shop","channel":"offline","saving_percent":10}])
  self.assertIn("**In-store / pickup**",message)
  self.assertIn("location: Austin, TX",message)
  self.assertIn("[check local stock](https://example.test/stock)",message)
if __name__ == "__main__": unittest.main()
