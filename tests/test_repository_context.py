import tempfile
import unittest
from pathlib import Path

from agent.context.repository import inspect_repository


class RepositoryContextTests(unittest.TestCase):
    def test_context_includes_task_relevant_source_and_project_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "README.md").write_text(
                "# Example project\nParser validation project.", encoding="utf-8"
            )
            source = workspace / "src" / "parser.py"
            source.parent.mkdir()
            source.write_text(
                "def validate_parser_input(value):\n"
                "    return value.strip()\n",
                encoding="utf-8",
            )
            unrelated = workspace / "src" / "renderer.py"
            unrelated.write_text(
                "def draw_sunrise():\n    return 'orange'\n",
                encoding="utf-8",
            )
            (workspace / ".env").write_text(
                "LLM_API_KEY=must-not-appear", encoding="utf-8"
            )

            context = inspect_repository(
                workspace, "Fix parser input validation"
            )

            self.assertIn("Task: Fix parser input validation", context)
            self.assertIn("--- README.md ---", context)
            self.assertIn("--- Relevant file: src/parser.py ---", context)
            self.assertIn("validate_parser_input", context)
            self.assertNotIn("must-not-appear", context)
            self.assertNotIn("LLM_API_KEY", context)

    def test_context_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "README.md").write_text("x" * 50_000, encoding="utf-8")
            context = inspect_repository(workspace, "review this project")
            self.assertLessEqual(len(context), 18_000)


if __name__ == "__main__":
    unittest.main()
