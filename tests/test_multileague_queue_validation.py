import unittest
from ex_multileague_queue_validation import validate


class QueueValidationTests(unittest.TestCase):
    def setUp(self):
        self.queue={"ex_final_allowed":False,"score_verified":False,
                    "total_review_queue":2,"queue_version":2,
                    "exported":1,"truncated":True,"fixtures":[
                        {"league":"en.1","review_status":"REQUIRES_INDEPENDENT_SOURCE_REVIEW"}]}
        self.diag={"unmatched_total":2,"by_league":{"en.1":{"count":2}}}

    def test_guarded_queue(self):
        result=validate(self.queue,self.diag)
        self.assertEqual(result["total"],2)
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_missing_export(self):
        with self.assertRaises(ValueError):
            validate({**self.queue,"exported":2},self.diag)

    def test_rejects_unsafe_final(self):
        with self.assertRaises(ValueError):
            validate({**self.queue,"ex_final_allowed":True},self.diag)


if __name__=="__main__":
    unittest.main()
