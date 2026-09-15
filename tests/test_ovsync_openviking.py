import importlib.machinery
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import openviking as ov


class ImportCmdTestCase(unittest.TestCase):
    def test_exact_command(self):
        self.assertEqual(
            ov.import_cmd("demo"),
            [
                "docker", "exec", "openviking", "ov", "add-resource",
                "/specs/.ov-stage/demo",
                "--to", "viking://resources/demo/specs",
                "--processing-mode", "vectors_only",
                "--args", "parse_mode:no_split",
            ],
        )


class ReindexCmdTestCase(unittest.TestCase):
    def test_exact_command(self):
        self.assertEqual(
            ov.reindex_cmd("demo", "architecture/adr"),
            [
                "docker", "exec", "openviking", "ov", "reindex",
                "viking://resources/demo/specs/architecture/adr",
                "--mode", "semantic_and_vectors",
                "--recursive", "true",
            ],
        )


class NoRmTestCase(unittest.TestCase):
    def test_import_and_reindex_never_use_rm(self):
        self.assertNotIn("rm", ov.import_cmd("demo"))
        self.assertNotIn("rm", ov.reindex_cmd("demo", "architecture/adr"))

    def test_source_has_no_rm_list_item(self):
        source = (REPO / "lib" / "ovsync" / "openviking.py").read_text()
        self.assertNotIn('"rm"', source)
        self.assertNotIn("'rm'", source)


class ClassifyTestCase(unittest.TestCase):
    def test_locked(self):
        self.assertEqual(
            ov.classify("[CONFLICT] lock acquire timed out after 0ms"), "locked"
        )

    def test_unavailable(self):
        self.assertEqual(
            ov.classify("Error: No such container: openviking"), "unavailable"
        )
        self.assertEqual(
            ov.classify(
                "Cannot connect to the Docker daemon at "
                "unix:///var/run/docker.sock. Is the docker daemon running?"
            ),
            "unavailable",
        )

    def test_error(self):
        self.assertEqual(ov.classify("Local path does not exist"), "error")


class HealthTestCase(unittest.TestCase):
    def test_exit_zero_is_healthy(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(args=[], returncode=0)
        )
        self.assertTrue(ov.health(run))

    def test_exit_nonzero_is_unhealthy(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(args=[], returncode=1)
        )
        self.assertFalse(ov.health(run))

    def test_missing_binary_is_unhealthy(self):
        run = mock.Mock(side_effect=FileNotFoundError())
        self.assertFalse(ov.health(run))

    def test_timeout_is_unhealthy(self):
        run = mock.Mock(
            side_effect=subprocess.TimeoutExpired(cmd="ov health", timeout=30)
        )
        self.assertFalse(ov.health(run))


class TasksTestCase(unittest.TestCase):
    def setUp(self):
        self.fixture = (REPO / "tests" / "fixtures" / "ov_task_list.json").read_text()

    def test_parses_fixture(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=self.fixture, stderr=""
            )
        )
        result = ov.tasks(run)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_invalid_json_gives_none(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="not json", stderr=""
            )
        )
        self.assertIsNone(ov.tasks(run))

    def test_ok_false_gives_none(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps({"ok": False}), stderr=""
            )
        )
        self.assertIsNone(ov.tasks(run))

    def test_nonzero_exit_gives_none(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="boom"
            )
        )
        self.assertIsNone(ov.tasks(run))

    def test_missing_binary_gives_none(self):
        run = mock.Mock(side_effect=FileNotFoundError())
        self.assertIsNone(ov.tasks(run))

    def test_timeout_gives_none(self):
        run = mock.Mock(
            side_effect=subprocess.TimeoutExpired(cmd="ov task list", timeout=30)
        )
        self.assertIsNone(ov.tasks(run))


class FindTaskTestCase(unittest.TestCase):
    def setUp(self):
        data = json.loads(
            (REPO / "tests" / "fixtures" / "ov_task_list.json").read_text()
        )
        self.task_list = data["result"]
        self.newer_id = "f35e5cc3-6342-47fc-86f7-ad3ca67d7197"
        self.newer_created_at = 1789376699.274354
        self.older_created_at = 1789376203.9732494

    def test_returns_newest_matching_task(self):
        task = ov.find_task(self.task_list, "demo", self.older_created_at - 5)
        self.assertIsNotNone(task)
        self.assertEqual(task["task_id"], self.newer_id)

    def test_none_when_all_older(self):
        task = ov.find_task(self.task_list, "demo", self.newer_created_at + 100)
        self.assertIsNone(task)

    def test_boundary_at_exactly_started_at_minus_5(self):
        older_only = [self.task_list[1]]
        started_at = self.older_created_at + 5
        task = ov.find_task(older_only, "demo", started_at)
        self.assertIsNotNone(task)

    def test_boundary_just_below_started_at_minus_5(self):
        older_only = [self.task_list[1]]
        started_at = self.older_created_at + 5.001
        task = ov.find_task(older_only, "demo", started_at)
        self.assertIsNone(task)

    def test_skips_malformed_entries(self):
        task_list = [None, "not a task", {"task_type": "add_resource",
                                           "resource_id": ov.resource_uri("demo"),
                                           "created_at": None}] + self.task_list
        task = ov.find_task(task_list, "demo", self.older_created_at - 5)
        self.assertIsNotNone(task)
        self.assertEqual(task["task_id"], self.newer_id)


class TaskStatusTestCase(unittest.TestCase):
    def setUp(self):
        data = json.loads(
            (REPO / "tests" / "fixtures" / "ov_task_list.json").read_text()
        )
        self.completed_task, self.running_task = data["result"]

    def test_completed_and_running_from_fixture(self):
        self.assertEqual(ov.task_status(self.completed_task), "completed")
        self.assertEqual(ov.task_status(self.running_task), "running")

    def test_pending_and_failed(self):
        self.assertEqual(ov.task_status({"status": "pending"}), "pending")
        self.assertEqual(ov.task_status({"status": "failed"}), "failed")

    def test_unknown_status_maps_to_running(self):
        self.assertEqual(ov.task_status({"status": "weird"}), "running")

    def test_non_dict_maps_to_running(self):
        self.assertEqual(ov.task_status("not a task"), "running")
        self.assertEqual(ov.task_status(None), "running")


class ModelsTestCase(unittest.TestCase):
    def setUp(self):
        self.fixture = (
            REPO / "tests" / "fixtures" / "ov_observer_models.json"
        ).read_text()

    def test_parses_fixture(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=self.fixture, stderr=""
            )
        )
        self.assertEqual(
            ov.models(run), {"vlm_calls": 2734, "embedding_calls": 3804}
        )

    def test_nonzero_exit_gives_none(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="boom"
            )
        )
        self.assertIsNone(ov.models(run))

    def test_missing_binary_gives_none(self):
        run = mock.Mock(side_effect=FileNotFoundError())
        self.assertIsNone(ov.models(run))

    def test_timeout_gives_none(self):
        run = mock.Mock(
            side_effect=subprocess.TimeoutExpired(cmd="ov observer models", timeout=30)
        )
        self.assertIsNone(ov.models(run))

    def test_null_status_gives_none(self):
        stdout = json.dumps({"ok": True, "result": {"status": None}})
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
        )
        self.assertIsNone(ov.models(run))

    def test_missing_status_gives_none(self):
        stdout = json.dumps({"ok": True, "result": {}})
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
        )
        self.assertIsNone(ov.models(run))


class RetrievalTestCase(unittest.TestCase):
    def setUp(self):
        self.fixture = (
            REPO / "tests" / "fixtures" / "ov_observer_retrieval.json"
        ).read_text()

    def test_parses_fixture(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=self.fixture, stderr=""
            )
        )
        self.assertEqual(ov.retrieval(run), 123)

    def test_nonzero_exit_gives_none(self):
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="boom"
            )
        )
        self.assertIsNone(ov.retrieval(run))

    def test_missing_binary_gives_none(self):
        run = mock.Mock(side_effect=FileNotFoundError())
        self.assertIsNone(ov.retrieval(run))

    def test_timeout_gives_none(self):
        run = mock.Mock(
            side_effect=subprocess.TimeoutExpired(cmd="ov observer retrieval", timeout=30)
        )
        self.assertIsNone(ov.retrieval(run))

    def test_null_status_gives_none(self):
        stdout = json.dumps({"ok": True, "result": {"status": None}})
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
        )
        self.assertIsNone(ov.retrieval(run))

    def test_missing_status_gives_none(self):
        stdout = json.dumps({"ok": True, "result": {}})
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
        )
        self.assertIsNone(ov.retrieval(run))


class AddResourceCountTestCase(unittest.TestCase):
    def test_counts_add_resource_tasks(self):
        data = json.loads(
            (REPO / "tests" / "fixtures" / "ov_task_list.json").read_text()
        )
        self.assertEqual(ov.add_resource_count(data["result"]), 2)

    def test_skips_malformed_entries(self):
        data = json.loads(
            (REPO / "tests" / "fixtures" / "ov_task_list.json").read_text()
        )
        task_list = [None, "not a task"] + data["result"]
        self.assertEqual(ov.add_resource_count(task_list), 2)


if __name__ == "__main__":
    unittest.main()
