"""`./lab ai quiet-hours` and the installer question (CONTRACT Phase 6, AI polish (a)), run for
real against a copied tree with the installer tests' fake `docker` on PATH (no daemon, never a
model call; the local URL is a closed loopback port and is never probed).

    python3 -m unittest discover -s v3/tests/ai -p 'test_lab_quiet_hours.py' -v
"""
import os
import shutil
import subprocess
import tempfile
import unittest

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(V3, "tests", "installer", "fixtures")


def env_get(path, key):
    val = None
    with open(path) as f:
        for line in f:
            if line.startswith(key + "="):
                val = line.rstrip("\n").split("=", 1)[1]
    return val


@unittest.skipUnless(shutil.which("bash") and shutil.which("openssl"), "needs bash and openssl")
class QuietHoursCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp(prefix="lab-qh.")
        tree = cls.tree = os.path.join(cls.work, "tree")
        os.makedirs(os.path.join(tree, "tests", "smoke"))
        for f in ("install.sh", "lab", "versions.env"):
            shutil.copy2(os.path.join(V3, f), tree)
        shutil.copytree(os.path.join(V3, "installer"), os.path.join(tree, "installer"))
        shutil.copy2(os.path.join(FIX, "compose.yaml"), tree)
        shutil.copy2(os.path.join(FIX, "check-env.sh"), tree)
        shutil.copy2(os.path.join(FIX, "smoke-run.sh"), os.path.join(tree, "tests", "smoke", "run.sh"))
        bindir = os.path.join(cls.work, "bin")
        os.makedirs(bindir)
        shutil.copy2(os.path.join(FIX, "docker-shim.sh"), os.path.join(bindir, "docker"))
        os.chmod(os.path.join(bindir, "docker"), 0o755)
        cls.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], NO_COLOR="1",
                       SHIM_LOG=os.path.join(cls.work, "compose.log"))
        for k in list(cls.env):
            if k.startswith("LAB_AI_") or k in ("COMPOSE_PROJECT_NAME", "LAB_TZ"):
                cls.env.pop(k)
        r = cls.run_(["install.sh", "--non-interactive", "--domain", "lab.localhost",
                      "--project-name", "v3-p6-qh-unit", "--https-port", "18643", "--http-port",
                      "18280", "--profile", "full", "--no-start",
                      "--ai-local-url", "http://127.0.0.1:9", "--ai-local-model", "m1"])
        assert r.returncode == 0, r.stdout + r.stderr
        cls.dotenv = os.path.join(tree, ".env")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    @classmethod
    def run_(cls, args, env=None, stdin=None):
        return subprocess.run(["bash", os.path.join(cls.tree, args[0])] + args[1:],
                              cwd=cls.tree, env=env or cls.env, input=stdin, text=True,
                              capture_output=True, timeout=120)

    def lab(self, *args, **kw):
        return self.run_(["lab"] + list(args), **kw)

    def sh(self, script, stdin=None):
        """Run bash with the lab's installer libraries sourced against the test tree."""
        prog = (f'V3_DIR="{self.tree}"; . "{self.tree}/installer/lib.sh"; '
                f'. "{self.tree}/installer/ai.sh"; lab_settings; {script}')
        return subprocess.run(["bash", "-c", prog], env=self.env, input=stdin, text=True,
                              capture_output=True, timeout=60)

    def test_1_default_off(self):
        self.assertIn(env_get(self.dotenv, "LAB_AI_QUIET_HOURS"), (None, ""))
        r = self.lab("ai", "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"\n  quiet +off\n")
        r = self.lab("ai", "quiet-hours")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("quiet      off", r.stdout)

    def test_2_set_and_status(self):
        r = self.lab("ai", "quiet-hours", "22:00-07:00", "--tz", "America/New_York")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_HOURS"), "22:00-07:00")
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_TZ"), "America/New_York")
        self.assertIn("hosted models are not affected", r.stdout)
        r = self.lab("ai", "status")
        self.assertRegex(r.stdout, r"quiet +22:00-07:00 America/New_York, local model only \(now: ")
        r = self.lab("ai", "quiet-hours", "08:15-09:00", "--tz=Europe/Berlin")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_TZ"), "Europe/Berlin")

    def test_3_tz_defaults_to_lab_tz(self):
        with open(self.dotenv) as f:
            before = f.read()
        try:
            self.sh('env_set "$LAB_ENV_FILE" LAB_TZ Asia/Tokyo')
            r = self.lab("ai", "quiet-hours", "23:00-06:00")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_TZ"), "Asia/Tokyo")
        finally:
            with open(self.dotenv, "w") as f:
                f.write(before)

    def test_4_invalid_refused_and_nothing_written(self):
        self.lab("ai", "quiet-hours", "22:00-07:00", "--tz", "America/New_York")
        for args in (["7:00-22:00", "--tz", "UTC"], ["22:00-22:00", "--tz", "UTC"],
                     ["24:00-07:00", "--tz", "UTC"], ["22:00-07:00", "--tz", "Mars/Olympus"],
                     ["22:00-07:00", "--tz", "../../etc/passwd"], ["off", "--tz", "UTC"],
                     ["22:00-07:00", "--bogus"], ["22:00-07:00", "--tz"]):
            r = self.lab("ai", "quiet-hours", *args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_HOURS"), "22:00-07:00", args)
            self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_TZ"), "America/New_York", args)

    def test_5_off_stores_empty(self):
        self.lab("ai", "quiet-hours", "22:00-07:00", "--tz", "America/New_York")
        r = self.lab("ai", "quiet-hours", "off")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_HOURS"), "")
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_TZ"), "")
        self.assertIn("quiet      off", self.lab("ai", "status").stdout)

    def test_6_applies_to_a_running_gateway(self):
        """With the gateway running (fake ps), the new window reaches compose from .env, not a
        stale export (REG_V3_LAB_AI_STALE_EXPORT), and a stray shell value never wins."""
        self.lab("ai", "quiet-hours", "off")
        env = dict(self.env, SHIM_PS="gw1", LAB_AI_QUIET_HOURS="01:00-02:00")
        open(self.env["SHIM_LOG"], "w").close()
        r = self.lab("ai", "quiet-hours", "22:00-07:00", "--tz", "UTC", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.env["SHIM_LOG"]) as f:
            log = f.read()
        self.assertIn("up -d --wait ai-gateway ai-keys", log)
        r = self.sh('lab_settings; printf "%s|%s" "$LAB_AI_QUIET_HOURS" "$LAB_AI_QUIET_TZ"')
        self.assertEqual(r.stdout, "22:00-07:00|UTC")

    def test_7_window_display_logic(self):
        cases = {("22:00-07:00", "23:10"): "07:00", ("22:00-07:00", "06:59"): "07:00",
                 ("22:00-07:00", "07:00"): None, ("22:00-07:00", "21:59"): None,
                 ("09:00-17:00", "09:00"): "17:00", ("09:00-17:00", "17:00"): None,
                 ("22:00-07:00", "00:00"): "07:00", ("00:00-00:30", "00:10"): "00:30"}
        for (spec, now), want in cases.items():
            r = self.sh(f'ai_quiet_end_now {spec} UTC {now}')
            if want is None:
                self.assertNotEqual(r.returncode, 0, (spec, now))
            else:
                self.assertEqual((r.returncode, r.stdout.strip()), (0, want), (spec, now))

    def test_8_installer_question(self):
        # Asked only when a local URL is set and never answered before.
        self.sh('env_unset "$LAB_ENV_FILE" LAB_AI_QUIET_HOURS; env_unset "$LAB_ENV_FILE" LAB_AI_QUIET_TZ')
        r = self.sh("ai_ask_quiet_hours", stdin="bad\n22:30-06:30\nNope/Zone\nAmerica/Chicago\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_HOURS"), "22:30-06:30")
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_TZ"), "America/Chicago")
        r = self.sh("ai_ask_quiet_hours", stdin="")          # answered once: no question
        self.assertNotIn("quiet hours", r.stdout.lower())
        self.sh('env_unset "$LAB_ENV_FILE" LAB_AI_QUIET_HOURS')
        r = self.sh("ai_ask_quiet_hours", stdin="\n")         # empty answer = off, remembered
        self.assertEqual(env_get(self.dotenv, "LAB_AI_QUIET_HOURS"), "")
        # No local model: no question at all.
        self.sh('env_unset "$LAB_ENV_FILE" LAB_AI_QUIET_HOURS; env_set "$LAB_ENV_FILE" LAB_AI_LOCAL_URL ""')
        try:
            r = self.sh("ai_ask_quiet_hours", stdin="22:00-07:00\nUTC\n")
            self.assertIsNone(env_get(self.dotenv, "LAB_AI_QUIET_HOURS"))
        finally:
            self.sh('env_set "$LAB_ENV_FILE" LAB_AI_LOCAL_URL http://host.docker.internal:9/v1')

    def test_9_help(self):
        r = self.lab("--help")
        self.assertIn("ai quiet-hours [HH:MM-HH:MM [--tz Area/City] | off]", r.stdout)


class E2eScriptOptIn(unittest.TestCase):
    """tests/ai/quiet-hours-e2e.sh configures the `local` provider (pointed at the mock) only
    with LAB_E2E_LOCAL_VIA_MOCK=1: by default it does nothing at all (quiet-hours rule on hosts
    with a real model server; REG_V3_GATEWAY_E2E_CONFIGURES_LOCAL_PROVIDER_BY_DEFAULT)."""

    def run_script(self, value):
        work = tempfile.mkdtemp(prefix="lab-qh-e2e.")
        try:
            bindir = os.path.join(work, "bin")
            os.makedirs(bindir)
            log = os.path.join(work, "docker.log")
            with open(os.path.join(bindir, "docker"), "w") as f:
                f.write(f'#!/bin/sh\necho "$@" >> "{log}"\nexit 0\n')
            os.chmod(os.path.join(bindir, "docker"), 0o755)
            env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"])
            env.pop("LAB_E2E_LOCAL_VIA_MOCK", None)
            if value is not None:
                env["LAB_E2E_LOCAL_VIA_MOCK"] = value
            r = subprocess.run(["bash", os.path.join(V3, "tests", "ai", "quiet-hours-e2e.sh")],
                               env=env, text=True, capture_output=True, timeout=60)
            return r, (open(log).read() if os.path.exists(log) else "")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_default_skips_without_any_docker_call(self):
        for value in (None, "0"):
            r, calls = self.run_script(value)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("SKIPPED (opt-in: LAB_E2E_LOCAL_VIA_MOCK=1", r.stdout)
            self.assertEqual(calls, "")

    def test_bad_switch_refused(self):
        r, calls = self.run_script("yes")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(calls, "")


if __name__ == "__main__":
    unittest.main()
