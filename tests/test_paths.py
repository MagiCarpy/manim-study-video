"""Generation path tests; run with the skill's Python and stdlib unittest."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


# Load only this dependency-free module, without initializing the studio package.
_spec = importlib.util.spec_from_file_location(
    "study_paths", Path(__file__).resolve().parents[1] / "studio" / "paths.py"
)
assert _spec is not None and _spec.loader is not None
paths = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(paths)


class PathsTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="study-paths-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        environment = patch.dict(os.environ, {"HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("STUDY_HOME", None)
        os.environ.pop("STUDY_LESSONS_DIR", None)
        original_cwd = Path.cwd()
        self.addCleanup(os.chdir, original_cwd)
        self.cwd = self.root / "working"
        self.cwd.mkdir()
        os.chdir(self.cwd)

    def test_default_lessons_live_in_home_study_videos(self) -> None:
        self.assertEqual(paths.lessons_dir(), self.home / "study-videos" / "lessons")

    def test_study_home_selects_workspace_root(self) -> None:
        workspace = self.root / "custom-workspace"
        os.environ["STUDY_HOME"] = str(workspace)
        self.assertEqual(paths.lessons_dir(), workspace / "lessons")

    def test_study_home_expands_tilde(self) -> None:
        os.environ["STUDY_HOME"] = "~/workspace"
        self.assertEqual(paths.lessons_dir(), self.home / "workspace" / "lessons")

    def test_relative_study_home_resolves_from_cwd(self) -> None:
        os.environ["STUDY_HOME"] = "workspace/../workspace"
        self.assertEqual(paths.lessons_dir(), self.cwd / "workspace" / "lessons")

    def test_empty_study_home_uses_default(self) -> None:
        os.environ["STUDY_HOME"] = ""
        self.assertEqual(paths.lessons_dir(), self.home / "study-videos" / "lessons")

    def test_default_is_independent_of_cwd(self) -> None:
        expected = self.home / "study-videos" / "lessons"
        self.assertEqual(paths.lessons_dir(), expected)
        os.chdir(self.home)
        self.assertEqual(paths.lessons_dir(), expected)

    def test_absolute_study_home_is_independent_of_cwd(self) -> None:
        os.environ["STUDY_HOME"] = str(self.root / "workspace")
        expected = self.root / "workspace" / "lessons"
        self.assertEqual(paths.lessons_dir(), expected)
        os.chdir(self.home)
        self.assertEqual(paths.lessons_dir(), expected)

    def test_lessons_environment_takes_precedence_over_study_home(self) -> None:
        os.environ["STUDY_HOME"] = str(self.root / "workspace")
        os.environ["STUDY_LESSONS_DIR"] = str(self.root / "env-lessons")
        self.assertEqual(paths.lessons_dir(), self.root / "env-lessons")

    def test_explicit_lessons_root_takes_precedence_over_environment(self) -> None:
        os.environ["STUDY_HOME"] = str(self.root / "workspace")
        os.environ["STUDY_LESSONS_DIR"] = str(self.root / "env-lessons")
        expected = self.root / "explicit-lessons"
        for override in (str(expected), expected):
            with self.subTest(override=override):
                self.assertEqual(paths.lessons_dir(override), expected)

    def test_empty_lessons_overrides_keep_existing_fallbacks(self) -> None:
        os.environ["STUDY_LESSONS_DIR"] = str(self.root / "env-lessons")
        self.assertEqual(paths.lessons_dir(""), self.root / "env-lessons")
        os.environ["STUDY_LESSONS_DIR"] = ""
        os.environ["STUDY_HOME"] = str(self.root / "workspace")
        self.assertEqual(paths.lessons_dir(""), self.root / "workspace" / "lessons")

    def test_lessons_environment_expands_tilde(self) -> None:
        os.environ["STUDY_LESSONS_DIR"] = "~/existing-lessons"
        self.assertEqual(paths.lessons_dir(), self.home / "existing-lessons")

    def test_explicit_lessons_root_expands_tilde(self) -> None:
        self.assertEqual(paths.lessons_dir("~/existing-lessons"), self.home / "existing-lessons")

    def test_relative_lessons_roots_keep_cwd_semantics(self) -> None:
        os.environ["STUDY_LESSONS_DIR"] = "env-lessons"
        self.assertEqual(paths.lessons_dir(), self.cwd / "env-lessons")
        self.assertEqual(paths.lessons_dir("local/../lessons"), self.cwd / "lessons")

    def test_slug_uses_default_workspace(self) -> None:
        self.assertEqual(
            paths.lesson_dir("my-lesson"), self.home / "study-videos" / "lessons" / "my-lesson"
        )

    def test_slug_uses_overridden_workspace(self) -> None:
        os.environ["STUDY_HOME"] = str(self.root / "workspace")
        self.assertEqual(paths.lesson_dir("my-lesson"), self.root / "workspace" / "lessons" / "my-lesson")

    def test_slug_honors_lessons_root_precedence(self) -> None:
        os.environ["STUDY_HOME"] = str(self.root / "workspace")
        os.environ["STUDY_LESSONS_DIR"] = str(self.root / "env-lessons")
        self.assertEqual(paths.lesson_dir("my-lesson"), self.root / "env-lessons" / "my-lesson")
        explicit = self.root / "explicit-lessons"
        for override in (str(explicit), explicit):
            with self.subTest(override=override):
                self.assertEqual(paths.lesson_dir("my-lesson", override), explicit / "my-lesson")

    def test_explicit_lesson_paths_bypass_all_root_overrides(self) -> None:
        os.environ["STUDY_HOME"] = str(self.root / "workspace")
        os.environ["STUDY_LESSONS_DIR"] = str(self.root / "env-lessons")
        for supplied, expected in (
            (str(self.root / "existing-project"), self.root / "existing-project"),
            ("existing-project/lesson", self.cwd / "existing-project" / "lesson"),
            ("./my-lesson", self.cwd / "my-lesson"),
            ("../my-lesson", self.root / "my-lesson"),
            ("~/existing-project", self.home / "existing-project"),
            (".hidden-lesson", self.cwd / ".hidden-lesson"),
        ):
            with self.subTest(supplied=supplied):
                self.assertEqual(paths.lesson_dir(supplied, self.root / "ignored"), expected)

    def test_resolving_paths_does_not_create_workspace_or_lesson(self) -> None:
        workspace = self.home / "study-videos"
        self.assertFalse(workspace.exists())
        paths.lessons_dir()
        paths.lesson_dir("my-lesson")
        self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
