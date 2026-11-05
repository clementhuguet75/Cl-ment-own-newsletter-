"""Non-billable mocked tests of LLM recovery, preservation and publication."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import weekly
from guardrails import RecoverableDigestError
from test_guardrails import CANDIDATES, sample

class TestPipeline(unittest.TestCase):
    def _response(self, status, report=None):
        return SimpleNamespace(status=status, output_text=json.dumps(report) if report else "",
                               usage={"output_tokens":20})

    def test_incomplete_json_retries_once_and_recovers(self):
        fake = unittest.mock.MagicMock()
        fake.responses.create.side_effect = [
            self._response("incomplete"),
            self._response("completed",sample()),
        ]
        with patch.object(weekly,"OpenAI",return_value=fake):
            output=weekly.structured_digest("rules","research notes",CANDIDATES,"draft")
        self.assertEqual(output["title"],sample()["title"])
        self.assertEqual(fake.responses.create.call_count,2)

    def test_twice_incomplete_is_recoverable_not_published(self):
        fake=unittest.mock.MagicMock()
        fake.responses.create.return_value=self._response("incomplete")
        with patch.object(weekly,"OpenAI",return_value=fake):
            with self.assertRaises(RecoverableDigestError):
                weekly.structured_digest("rules","notes",CANDIDATES,"draft")
        self.assertEqual(fake.responses.create.call_count,2)

    def test_bad_citations_retry_then_stop(self):
        invalid=sample()
        invalid["sections"][0]["source_ids"]=[999999]
        fake=unittest.mock.MagicMock()
        fake.responses.create.return_value=self._response("completed",invalid)
        with patch.object(weekly,"OpenAI",return_value=fake):
            with self.assertRaises(RecoverableDigestError):
                weekly.structured_digest("rules","notes",CANDIDATES,"revision")
        self.assertEqual(fake.responses.create.call_count,2)

    def test_expected_model_error_keeps_previous_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"output"
            summary=Path(tmp)/"summary"
            with patch.dict("os.environ",{"GITHUB_OUTPUT":str(output),"GITHUB_STEP_SUMMARY":str(summary)}), \
                 patch.object(weekly,"collect",return_value=CANDIDATES), \
                 patch.object(weekly,"make_digest",side_effect=RecoverableDigestError("Invalid result")), \
                 patch.object(weekly,"publish") as publisher:
                weekly.main()
            self.assertEqual(output.read_text(),"published=false\n")
            self.assertIn("previous edition kept",summary.read_text())
            publisher.assert_not_called()

    def test_valid_issue_publishes_and_sets_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"output"
            source=sample()
            with patch.dict("os.environ",{"GITHUB_OUTPUT":str(output)}), \
                 patch.object(weekly,"collect",return_value=CANDIDATES), \
                 patch.object(weekly,"make_digest",return_value=(source,"research",CANDIDATES)), \
                 patch.object(weekly,"audit_digest",return_value=source), \
                 patch.object(weekly,"publish") as publisher:
                weekly.main()
            self.assertEqual(output.read_text(),"published=true\n")
            publisher.assert_called_once()

    def test_real_publish_bug_remains_visible_as_failure(self):
        with patch.dict("os.environ",{"GITHUB_OUTPUT":""}), \
             patch.object(weekly,"collect",return_value=CANDIDATES), \
             patch.object(weekly,"make_digest",return_value=(sample(),"research",CANDIDATES)), \
             patch.object(weekly,"audit_digest",return_value=sample()), \
             patch.object(weekly,"publish",side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                weekly.main()

if __name__=="__main__":
    unittest.main()
