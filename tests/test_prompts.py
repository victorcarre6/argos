import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from rag.prompts import load_prompt, validate_prompt_config


class PromptConfigurationTest(unittest.TestCase):
    def test_repository_prompt_file_has_every_required_variable(self) -> None:
        path = Path(__file__).resolve().parents[1] / "config/prompt.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual([], validate_prompt_config(config))

    def test_prompt_loader_interpolates_the_requested_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prompt.yaml"
            path.write_text("assistant:\n  system: 'Contexte: {context}'\n")
            with patch("rag.prompts.PROMPT_CONFIG_PATH", path):
                rendered = load_prompt("assistant", "system", context="signal")
        self.assertEqual("Contexte: signal", rendered)

    def test_prompt_validation_rejects_missing_variables(self) -> None:
        config = {
            "assistant": {"system": "Sans variable"},
            "retrieval": {"query_plan": "{question}"},
            "summary": {"section": "{title} {references}"},
            "summarizer": {"telegram": "{max_chars} {report}"},
        }
        errors = validate_prompt_config(config)
        self.assertTrue(any("assistant.system" in error for error in errors))
        self.assertTrue(any("retrieval.query_plan" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
