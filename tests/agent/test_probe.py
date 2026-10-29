import json
import os
import tempfile
import unittest

from icarus.agent.pilot.probe import is_secret_name, load_guide, probe

CLAUDE_LIKE = {
    "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "icarus-approve"}]}]},
    "mcpServers": {"x": {"command": "node"}},
    "permissions": {"allow": ["Read"]},
}


class TestProbe(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name

    def tearDown(self):
        self.td.cleanup()

    def put(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def test_guide_loads_and_marks_everything_unverified(self):
        g = load_guide()
        self.assertIn("UNVERIFIED", g["note"])
        self.assertTrue({"model_slot", "approval_channel", "tool_registry"} <= set(g["surfaces"]))

    def test_finds_three_surfaces_and_the_harness_from_evidence(self):
        self.put(".claude/settings.json", json.dumps(CLAUDE_LIKE))
        r = probe(self.root, env={"ANTHROPIC_BASE_URL": "http://localhost:9"}, which=lambda b: "/bin/claude" if b == "claude" else None)
        self.assertEqual((r.status, r.harness), ("FOUND", "claude-code"))
        self.assertEqual({e.detail for e in r.surfaces["approval_channel"]} >= {"hooks", "PreToolUse", "permissions"}, True)
        self.assertEqual([e.detail for e in r.surfaces["tool_registry"]], ["mcpServers"])
        self.assertEqual(r.surfaces["model_slot"][0].kind, "env")
        self.assertEqual(r.surfaces["process"][0].where, "claude")

    def test_nothing_found_is_blocked_and_lists_what_was_checked(self):
        r = probe(self.root, env={}, which=lambda b: None)
        self.assertEqual((r.status, r.harness), ("BLOCKED", "unknown"))
        self.assertEqual(r.surfaces, {})
        self.assertTrue(any(c.startswith("env:") for c in r.checked))
        self.assertTrue(any(c.startswith("binary:") for c in r.checked))

    def test_unknown_harness_is_found_by_its_config_alone(self):
        self.put(".mystery/config.yml", "base_url: http://x\nmcp_servers:\n  a: b\n")
        r = probe(self.root, env={}, which=lambda b: None)
        self.assertEqual((r.status, r.harness), ("FOUND", "unknown"))
        self.assertEqual(r.surfaces["model_slot"][0].where, ".mystery/config.yml")
        self.assertEqual(r.surfaces["tool_registry"][0].detail, "mcp_servers")

    def test_values_are_never_stored(self):
        marker = "VALUE-" + "Z" * 12
        self.put(".mystery/config.json", json.dumps({"base_url": marker, "hooks": marker}))
        r = probe(self.root, env={"OPENAI_BASE_URL": marker}, which=lambda b: None)
        self.assertNotIn(marker, repr(r))

    def test_secret_files_are_never_opened(self):
        opened = []
        self.put(".mystery/auth.json", json.dumps({"base_url": "x"}))
        self.put(".mystery/token.json", json.dumps({"base_url": "x"}))
        self.put(".claude/settings.json", json.dumps(CLAUDE_LIKE))

        def spy(path):
            opened.append(os.path.basename(path))
            with open(path) as f:
                return f.read()
        r = probe(self.root, env={}, which=lambda b: None, read=spy)
        self.assertEqual(opened, ["settings.json"])
        self.assertEqual(sorted(r.skipped_secret_files), [".mystery/auth.json", ".mystery/token.json"])
        self.assertTrue(is_secret_name("/x/.env") and is_secret_name("id_rsa") and not is_secret_name("settings.json"))

    def test_skip_dirs_and_project_files_outside_dot_dirs_are_not_scanned(self):
        self.put(".ssh/config.json", json.dumps({"base_url": "x"}))
        self.put("project/config.json", json.dumps({"base_url": "x"}))
        r = probe(self.root, env={}, which=lambda b: None)
        self.assertEqual(r.status, "BLOCKED")

    def test_root_level_project_files_are_not_scanned(self):
        self.put("config.json", json.dumps({"base_url": "x"}))
        self.assertEqual(probe(self.root, env={}, which=lambda b: None).status, "BLOCKED")

    def test_files_actually_read_are_listed_as_checked(self):
        self.put(".claude/settings.json", json.dumps(CLAUDE_LIKE))
        r = probe(self.root, env={}, which=lambda b: None)
        self.assertIn("file:.claude/settings.json", r.checked)

    def test_oversized_file_is_skipped(self):
        self.put(".big/config.json", json.dumps({"base_url": "x"}) + " " * 300000)
        self.assertEqual(probe(self.root, env={}, which=lambda b: None).status, "BLOCKED")

    def test_caller_given_command_counts_as_a_process_surface(self):
        r = probe(self.root, env={}, which=lambda b: None, command=os.path.join(self.root, "nope"))
        self.assertEqual(r.status, "BLOCKED")
        exe = os.path.join(self.root, "harness-bin")
        open(exe, "w").close()
        r = probe(self.root, env={}, which=lambda b: None, command=exe)
        self.assertEqual((r.status, r.surfaces["process"][0].kind), ("FOUND", "command"))


if __name__ == "__main__":
    unittest.main()
