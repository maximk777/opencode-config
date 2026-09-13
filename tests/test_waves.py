import importlib.machinery
import unittest

W = importlib.machinery.SourceFileLoader("waves", "bin/waves").load_module()


def b(task, files, depends="", skeleton=False):
    return {"task": task, "files": files, "depends": [d for d in depends.split(",") if d], "skeleton": skeleton}


class Waves(unittest.TestCase):
    def test_shared_file_splits_waves(self):
        ws = W.plan_waves([b("1", ["internal/report/service.go"]), b("2", ["internal/report/service.go"])], set())
        self.assertEqual([[t["task"] for t in w] for w in ws], [["1"], ["2"]])

    def test_same_go_package_splits_waves(self):
        ws = W.plan_waves([b("1", ["pkg/a/x.go"]), b("2", ["pkg/a/y.go"])], set())
        self.assertEqual(len(ws), 2)

    def test_disjoint_tasks_share_a_wave(self):
        ws = W.plan_waves([b("1", ["a.ts"]), b("2", ["b.ts"])], set())
        self.assertEqual(len(ws), 1)

    def test_concurrency_limit(self):
        ws = W.plan_waves([b(str(i), [f"f{i}.ts"]) for i in range(1, 6)], set(), concurrency=3)
        self.assertEqual([len(w) for w in ws], [3, 2])

    def test_dependencies_respected(self):
        ws = W.plan_waves([b("1", ["a.ts"]), b("2", ["b.ts"], depends="1")], set())
        self.assertEqual([[t["task"] for t in w] for w in ws], [["1"], ["2"]])

    def test_done_tasks_skipped(self):
        ws = W.plan_waves([b("1", ["a.ts"]), b("2", ["b.ts"], depends="1")], {"1"})
        self.assertEqual([[t["task"] for t in w] for w in ws], [["2"]])

    def test_tier_rules(self):
        self.assertEqual(W.tier(b("1", ["a", "b", "c", "d"])), "executor-strong")
        self.assertEqual(W.tier(b("1", ["a", "b", "c", "d"], skeleton=True)), "executor")
        self.assertEqual(W.tier(b("1", ["a", "b"])), "executor")


if __name__ == "__main__":
    unittest.main()
