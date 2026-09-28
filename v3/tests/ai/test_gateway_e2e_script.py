"""tests/ai/gateway-e2e.sh against a fake `docker` (no daemon, no lab):

- by default it never configures the `local` provider: every `compose up` it runs has an
  empty LAB_AI_LOCAL_URL, and step 3 is reported as skipped (quiet hours on the dev host);
- LAB_E2E_LOCAL_VIA_MOCK=1 runs step 3, pointed at the mock only;
- a lab whose gateway has any provider besides the mock is refused before any request.

    python3 -m unittest discover -s v3/tests/ai
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.abspath(os.path.join(HERE, "..", ".."))

# Answers just enough of the compose calls gateway-e2e.sh makes, and logs each one with the
# LAB_AI_LOCAL_URL it was called with (compose passes the caller's env to the gateway).
FAKE_DOCKER = r"""#!/usr/bin/env bash
log="$FAKE_LOG"
all="$*"
case "$all" in
  inspect*) echo true; exit 0 ;;
esac
printf 'CALL local_url=[%s] %s\n' "${LAB_AI_LOCAL_URL-}" "$all" >>"$log"
case "$all" in
  *" up "*) echo "UP local_url=[${LAB_AI_LOCAL_URL-}]" >>"$log"; exit 0 ;;
  *" ps -q ai-gateway"*) echo "cid$RANDOM$RANDOM"; exit 0 ;;
  *"ai-gateway cat /tmp/lab-ai/state.json"*) cat "$FAKE_STATE"; exit 0 ;;
  *"ai-gateway cat /tmp/lab-ai/config.yaml"*) echo '{"model_list": []}'; exit 0 ;;
  *"ai-gateway sh -c"*) exit 1 ;;
  *"ai-gateway printenv LAB_AI_LOCAL_URL"*) echo "http://ai-mock:8000/v1"; exit 0 ;;
  *"ai-gateway python3 -"*) cat >/dev/null; echo 'NO_EGRESS_RESULT {"outside": [], "ok": true}'; exit 0 ;;
  *"ai-keys python3 -c"*) echo 172.30.0.9; exit 0 ;;
  *"jupyterhub python3 -c"*) echo "gaierror timeout connected"; exit 0 ;;
  *"ai-keys python3 -"*)
    cat >/dev/null
    mode=$(printf '%s\n' "$all" | sed -n 's/.*E2E_MODE=\([a-z-]*\).*/\1/p')
    echo "PY $mode" >>"$log"
    echo 'E2E_RESULT {"checks": [], "ok": true}'; exit 0 ;;
esac
echo "fake docker: unexpected call: $all" >&2
exit 3
"""


class GatewayE2EScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        v3 = os.path.join(self.tmp, "v3")
        os.makedirs(os.path.join(v3, "tests", "ai"))
        os.makedirs(os.path.join(v3, "installer"))
        for rel in ("tests/ai/gateway-e2e.sh", "tests/ai/gateway_e2e.py", "tests/ai/no_egress_probe.py",
                    "installer/lib.sh"):
            shutil.copy(os.path.join(V3, rel), os.path.join(v3, rel))
        with open(os.path.join(v3, ".env"), "w") as f:
            f.write("COMPOSE_PROJECT_NAME=v3-fake\nLAB_PROFILE=full\nLAB_AI_MOCK=true\nLAB_AI_LOCAL_URL=\n")
        open(os.path.join(v3, "versions.env"), "w").close()
        bindir = os.path.join(self.tmp, "bin")
        os.makedirs(bindir)
        docker = os.path.join(bindir, "docker")
        with open(docker, "w") as f:
            f.write(FAKE_DOCKER)
        os.chmod(docker, os.stat(docker).st_mode | stat.S_IEXEC)
        self.script = os.path.join(v3, "tests", "ai", "gateway-e2e.sh")
        self.log = os.path.join(self.tmp, "calls.log")
        self.state = os.path.join(self.tmp, "state.json")
        self.set_state('{"configured": true, "providers": ["mock"]}')
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("LAB_", "COMPOSE_"))}
        self.env.update(PATH=bindir + os.pathsep + os.environ["PATH"], FAKE_LOG=self.log,
                        FAKE_STATE=self.state)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def set_state(self, text):
        with open(self.state, "w") as f:
            f.write(text)

    def run_script(self, **extra):
        env = dict(self.env, **extra)
        p = subprocess.run(["bash", self.script], env=env, capture_output=True, text=True, timeout=120)
        calls = ""
        if os.path.exists(self.log):
            with open(self.log) as f:
                calls = f.read()
        return p, calls

    def ups(self, calls):
        return [line for line in calls.splitlines() if line.startswith("UP ")]

    def test_default_never_configures_the_local_provider(self):
        p, calls = self.run_script()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("3. local provider path: SKIPPED", p.stdout)
        self.assertIn("AI GATEWAY E2E: PASS", p.stdout)
        ups = self.ups(calls)
        self.assertEqual(len(ups), 2, calls)  # step 2 (no provider) and step 4 (restore)
        self.assertTrue(all(u == "UP local_url=[]" for u in ups), ups)
        self.assertNotIn("PY local-via-mock", calls)
        self.assertNotIn("ai-mock:8000", calls)

    def test_opt_in_runs_step_3_against_the_mock_only(self):
        # A stray value in the caller's shell must not leak into the other steps either.
        p, calls = self.run_script(LAB_E2E_LOCAL_VIA_MOCK="1", LAB_AI_LOCAL_URL="http://example.invalid:9")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.ups(calls),
                         ["UP local_url=[]", "UP local_url=[http://ai-mock:8000/v1]", "UP local_url=[]"])
        self.assertIn("PY local-via-mock", calls)
        self.assertNotIn("example.invalid", calls)

    def test_bad_switch_value_is_refused(self):
        p, calls = self.run_script(LAB_E2E_LOCAL_VIA_MOCK="yes")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(calls, "")

    def test_lab_with_a_real_provider_is_refused_before_any_request(self):
        self.set_state('{"configured": true, "providers": ["mock", "local"]}')
        p, calls = self.run_script()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("providers other than the mock", p.stderr)
        self.assertEqual(self.ups(calls), [])
        self.assertNotIn("PY ", calls)


if __name__ == "__main__":
    unittest.main()
