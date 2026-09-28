"""User DAGs (CONTRACT Phase 4, E3): the Airflow cluster policy and the hub's per-user folder.

Runs without Airflow or JupyterHub: the policy module has a fallback exception type, and the
hub helper is taken out of jupyterhub_config.py with `ast` (the config needs a running hub).
"""
import ast
import importlib.util
import os
import tempfile
import unittest

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY = os.path.join(V3, "config", "airflow", "policy", "airflow_local_settings.py")
HUB = os.path.join(V3, "config", "jupyterhub", "jupyterhub_config.py")


def load_policy():
    spec = importlib.util.spec_from_file_location("lab_user_dag_policy", POLICY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_hub_helper():
    """ensure_user_dag_folder and the constants it uses, from jupyterhub_config.py."""
    with open(HUB, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "ensure_user_dag_folder":
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, (ast.Name, ast.Tuple)) and any(
                    getattr(n, "id", "") in ("DAGS_USER_NAME_RE", "WORKSPACE_UID", "WORKSPACE_GID")
                    for n in ([t] if isinstance(t, ast.Name) else t.elts)) for t in node.targets):
            keep.append(node)
    ns = {"os": os}
    exec(compile(ast.Module(body=keep, type_ignores=[]), HUB, "exec"), ns)  # noqa: S102
    return ns


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.p = load_policy()
        self.tmp = tempfile.TemporaryDirectory()
        self.dags = self.tmp.name
        for u in ("eddie", "eddie_x", "alice"):
            os.makedirs(os.path.join(self.dags, "user", u))

    def tearDown(self):
        self.tmp.cleanup()

    def f(self, *parts):
        return os.path.join(self.dags, "user", *parts)

    def test_own_prefix_ok(self):
        self.assertEqual(self.p.check("u_eddie_orders_summary", self.f("eddie", "d.py"), self.dags), "eddie")
        self.assertEqual(self.p.check("u_eddie_x_report", self.f("eddie_x", "d.py"), self.dags), "eddie_x")

    def test_longer_users_prefix_refused(self):
        with self.assertRaises(self.p.AirflowClusterPolicyViolation) as e:
            self.p.check("u_eddie_x_report", self.f("eddie", "d.py"), self.dags)
        self.assertIn("belong to user eddie_x", str(e.exception))

    def test_longer_prefix_allowed_without_that_user(self):
        self.assertEqual(self.p.check("u_eddie_y_report", self.f("eddie", "d.py"), self.dags), "eddie")

    def test_wrong_prefix_and_top_level(self):
        with self.assertRaises(self.p.AirflowClusterPolicyViolation):
            self.p.check("u_alice_x", self.f("eddie", "d.py"), self.dags)
        with self.assertRaises(self.p.AirflowClusterPolicyViolation):
            self.p.check("u_eddie_x", self.f("d.py"), self.dags)
        with self.assertRaises(self.p.AirflowClusterPolicyViolation):
            self.p.check("u_eddie", self.f("eddie", "d.py"), self.dags)

    def test_lab_dags(self):
        self.assertIsNone(self.p.check("lab_ingest", os.path.join(self.dags, "lab_ingest.py"), self.dags))
        with self.assertRaises(self.p.AirflowClusterPolicyViolation):
            self.p.check("u_eddie_x", os.path.join(self.dags, "lab.py"), self.dags)


class HubFolderTest(unittest.TestCase):
    def setUp(self):
        self.ns = load_hub_helper()
        self.tmp = tempfile.TemporaryDirectory()
        self.me = (os.getuid(), os.getgid())

    def tearDown(self):
        self.tmp.cleanup()

    def ensure(self, name):
        return self.ns["ensure_user_dag_folder"](self.tmp.name, name, *self.me)

    def test_creates_and_is_idempotent(self):
        p = self.ensure("eddie")
        self.assertTrue(os.path.isdir(p))
        self.assertEqual(self.ensure("eddie"), p)
        self.assertEqual(self.ensure("a.b-c_d"), os.path.join(self.tmp.name, "a.b-c_d"))

    def test_refuses_bad_names(self):
        for bad in ("", ".", "..", ".hidden", "eddie\n", "a/b", "../x", "Eddie", "a b", "x" * 64):
            with self.assertRaises(ValueError, msg=bad):
                self.ensure(bad)

    def test_refuses_symlink_and_file(self):
        os.symlink("/etc", os.path.join(self.tmp.name, "alice"))
        with self.assertRaises(ValueError):
            self.ensure("alice")
        open(os.path.join(self.tmp.name, "bob"), "w").close()
        with self.assertRaises(ValueError):
            self.ensure("bob")


if __name__ == "__main__":
    unittest.main()
