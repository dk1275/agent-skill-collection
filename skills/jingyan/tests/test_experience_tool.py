import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "experience_tool.py"


class ExperienceToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "library"
        self.exec_tool("init")

    def tearDown(self):
        self.tmp.cleanup()

    def exec_tool(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args], text=True, capture_output=True)
        if ok and result.returncode != 0:
            self.fail(f"command failed: {result.args}\nstdout={result.stdout}\nstderr={result.stderr}")
        return result

    def add_candidate(self, method_id=None):
        args = ["candidate", "add", "--source-project", "项目A", "--source-ref", "product-map.md",
                "--title", "分清实现与验收", "--rule", "交付时分开记录已实现、已验证、已部署和待用户验收。",
                "--applies-to", "软件项目交付", "--not-for", "纯讨论任务", "--evidence", "两个项目都出现过状态误判。",
                "--risk", "状态混写会误导下一位执行者。", "--verification", "检查四种状态是否都有独立证据。", "--tags", "交付,验证"]
        if method_id:
            args += ["--method-id", method_id]
        return json.loads(self.exec_tool(*args).stdout)["candidate_id"]

    def approve(self, candidate_id):
        return json.loads(self.exec_tool("approve", candidate_id, "--approved-by", "user", "--decision-note", "明确批准用于跨项目", "--confirm", "USER_APPROVED").stdout)

    def inject(self, project="项目B", task="发布体验版", query="交付 验证"):
        self.exec_tool("inject", "--project", project, "--project-type", "小程序", "--task", task, "--query", query)
        state = json.loads((self.root / ".state.json").read_text(encoding="utf-8"))
        return max(state["injections"].values(), key=lambda item: item["created_at"])["id"]

    def test_approval_gate_and_search(self):
        candidate_id = self.add_candidate()
        blocked = self.exec_tool("approve", candidate_id, "--approved-by", "agent", "--decision-note", "自认可靠", "--confirm", "NO", ok=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(json.loads(self.exec_tool("search", "--query", "交付验证").stdout), [])
        method = self.approve(candidate_id)
        hits = json.loads(self.exec_tool("search", "--query", "交付 验证", "--project", "项目B").stdout)
        self.assertEqual(hits[0]["id"], method["method_id"])

    def test_revision_archives_and_bumps_version(self):
        first = self.approve(self.add_candidate())
        second = self.approve(self.add_candidate(first["method_id"]))
        self.assertEqual(second["version"], "1.0.1")
        self.assertTrue((self.root / "history" / first["method_id"] / "v1.0.0.md").is_file())

    def test_extract_skips_secret_like_lines(self):
        source = Path(self.tmp.name) / "handoff.md"
        source.write_text("# 历史坑点\n- 预览成功不等于真机验收，必须单独记录。\n- API_KEY=do-not-store\n", encoding="utf-8")
        result = json.loads(self.exec_tool("extract", "--source-file", str(source), "--source-project", "项目A", "--source-ref", "handoff.md").stdout)
        self.assertEqual(result["extracted"], 1)
        state = json.loads((self.root / ".state.json").read_text())
        self.assertNotIn("do-not-store", json.dumps(state, ensure_ascii=False))

    def test_extracted_candidate_requires_boundary_completion(self):
        source = Path(self.tmp.name) / "handoff.md"
        source.write_text("# 经验\n- 上传成功以后仍要单独确认真实设备上的关键业务链路。\n", encoding="utf-8")
        extracted = json.loads(self.exec_tool("extract", "--source-file", str(source), "--source-project", "项目A").stdout)
        candidate_id = extracted["candidate_ids"][0]
        blocked = self.exec_tool("approve", candidate_id, "--approved-by", "user", "--decision-note", "批准", "--confirm", "USER_APPROVED", ok=False)
        self.assertIn("候选边界未补齐", blocked.stderr)
        self.exec_tool("candidate", "update", candidate_id, "--not-for", "不涉及客户端的后端任务", "--verification", "在第二个客户端项目检查真机链路")
        approved = self.approve(candidate_id)
        self.assertEqual(approved["version"], "1.0.0")

    def test_same_second_same_title_gets_unique_ids(self):
        first = self.add_candidate()
        second = self.add_candidate()
        self.assertNotEqual(first, second)

    def test_weak_evidence_match_does_not_trigger_search(self):
        self.approve(self.add_candidate())
        hits = json.loads(self.exec_tool("search", "--query", "回滚演练", "--project", "项目A").stdout)
        self.assertEqual(hits, [])

    def test_inject_and_retro_create_auditable_files(self):
        method = self.approve(self.add_candidate())
        injected = self.exec_tool("inject", "--project", "项目B", "--project-type", "小程序", "--task", "发布体验版", "--query", "交付 验证")
        self.assertIn(method["method_id"], injected.stdout)
        injection_id = self.inject(project="项目B", task="第二次发布", query="交付 验证")
        retro = json.loads(self.exec_tool("retro", "--project", "项目B", "--task", "发布体验版", "--result", "partial",
                                    "--outcome", "已上传，尚未真机验收", "--used-method", method["method_id"],
                                    "--injection-id", injection_id, "--lesson", "上传开发版本后仍需单独确认体验版与真机验收。", "--tags", "小程序,发布").stdout)
        self.assertEqual(len(retro["candidate_ids"]), 1)
        verify = json.loads(self.exec_tool("verify").stdout)
        self.assertTrue(verify["ok"])

    def test_bootstrap_policy_enables_bulk_approval(self):
        first = self.add_candidate()
        second = self.add_candidate()
        blocked = self.exec_tool("approve-all", "--approved-by", "agent", "--decision-note", "bootstrap", "--confirm", "BOOTSTRAP_AUTHORIZED", ok=False)
        self.assertNotEqual(blocked.returncode, 0)
        policy = json.loads(self.exec_tool("policy", "set", "--approval-mode", "bootstrap_auto", "--authorized-by", "user",
                                           "--reason", "初期自动沉淀", "--confirm", "USER_AUTHORIZED").stdout)
        self.assertEqual(policy["approval_mode"], "bootstrap_auto")
        result = json.loads(self.exec_tool("approve-all", "--approved-by", "agent-under-user-authorization",
                                           "--decision-note", "用户授权初期无需逐条审批", "--confirm", "BOOTSTRAP_AUTHORIZED").stdout)
        self.assertEqual(len(result["approved"]), 2)
        self.assertEqual(result["skipped"], [])
        status = json.loads(self.exec_tool("status").stdout)
        self.assertEqual(status["pending_candidates"], 0)
        self.assertEqual(status["approval_mode"], "bootstrap_auto")

    def test_bootstrap_bulk_approval_skips_incomplete_candidates(self):
        source = Path(self.tmp.name) / "handoff.md"
        source.write_text("# 经验\n- 预览成功后仍需检查真实业务链路。\n", encoding="utf-8")
        self.exec_tool("extract", "--source-file", str(source), "--source-project", "项目A")
        self.exec_tool("policy", "set", "--approval-mode", "bootstrap_auto", "--authorized-by", "user",
                       "--reason", "初期自动沉淀", "--confirm", "USER_AUTHORIZED")
        result = json.loads(self.exec_tool("approve-all", "--approved-by", "agent-under-user-authorization",
                                           "--decision-note", "用户授权初期无需逐条审批", "--confirm", "BOOTSTRAP_AUTHORIZED").stdout)
        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["skipped"]), 1)

    def test_bootstrap_retro_auto_promotes_complete_lessons(self):
        self.exec_tool("policy", "set", "--approval-mode", "bootstrap_auto", "--authorized-by", "user",
                       "--reason", "初期自动沉淀", "--confirm", "USER_AUTHORIZED")
        injection_id = self.inject(project="项目B", task="后台交付", query="权限 回滚")
        retro = json.loads(self.exec_tool("retro", "--project", "项目B", "--task", "后台交付", "--result", "success",
                                          "--outcome", "权限和回滚验证通过",
                                          "--injection-id", injection_id, "--lesson", "持续授权必须写入机器策略和审计。",
                                          "--lesson-applies-to", "需要跨 Agent 自动沉淀的项目方法库",
                                          "--lesson-not-for", "没有可审计状态文件的一次性临时任务",
                                          "--lesson-risk", "授权未写入工具状态会造成不同 Agent 理解不一致",
                                          "--lesson-verification", "在第二个 Agent 会话检查策略、审计和方法状态一致",
                                          "--tags", "治理,审计").stdout)
        self.assertEqual(len(retro["candidate_ids"]), 1)
        self.assertEqual(len(retro["promoted_method_ids"]), 1)
        status = json.loads(self.exec_tool("status").stdout)
        self.assertEqual(status["pending_candidates"], 0)
        self.assertEqual(status["approved_methods"], 1)
        candidate_text = (self.root / "candidates" / f"{retro['candidate_ids'][0]}.md").read_text(encoding="utf-8")
        self.assertIn("升级为正式方法", candidate_text)

    def test_closure_requires_linked_retro_and_reports_open_work(self):
        method = self.approve(self.add_candidate())
        injection_id = self.inject(project="项目C", task="后台改造", query="交付 验证")
        open_result = self.exec_tool("closure", "--project", "项目C", ok=False)
        self.assertNotEqual(open_result.returncode, 0)
        self.assertIn(injection_id, open_result.stdout)
        blocked = self.exec_tool("retro", "--project", "项目C", "--task", "后台改造", "--result", "success",
                                 "--outcome", "验证完成", "--used-method", method["method_id"], "--injection-id", "I-missing", ok=False)
        self.assertNotEqual(blocked.returncode, 0)
        retro = json.loads(self.exec_tool("retro", "--project", "项目C", "--task", "后台改造", "--result", "success",
                                          "--outcome", "验证完成", "--used-method", method["method_id"], "--injection-id", injection_id).stdout)
        closed = json.loads(self.exec_tool("closure", "--project", "项目C").stdout)
        self.assertTrue(closed["ok"])
        state = json.loads((self.root / ".state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["injections"][injection_id]["status"], "closed")
        self.assertEqual(state["injections"][injection_id]["retrospective_id"], retro["retrospective_id"])

    def test_bootstrap_retro_keeps_generic_lesson_pending(self):
        self.exec_tool("policy", "set", "--approval-mode", "bootstrap_auto", "--authorized-by", "user",
                       "--reason", "初期自动沉淀", "--confirm", "USER_AUTHORIZED")
        injection_id = self.inject(project="项目D", task="页面改造", query="视觉 改造")
        retro = json.loads(self.exec_tool("retro", "--project", "项目D", "--task", "页面改造", "--result", "success",
                                          "--outcome", "页面可正常访问", "--injection-id", injection_id,
                                          "--lesson", "统一设计变量后页面更一致。", "--tags", "视觉").stdout)
        self.assertEqual(retro["promoted_method_ids"], [])
        state = json.loads((self.root / ".state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["candidates"][retro["candidate_ids"][0]]["status"], "pending")


    def test_malformed_candidate_does_not_crash_status_or_verify(self):
        candidate_id = self.add_candidate()
        state = json.loads((self.root / ".state.json").read_text(encoding="utf-8"))
        record = state["candidates"][candidate_id]
        record.pop("status")
        record.pop("title")
        (self.root / ".state.json").write_text(json.dumps(state), encoding="utf-8")
        status = json.loads(self.exec_tool("status").stdout)
        self.assertEqual(status["malformed_candidates"], 1)
        verify = self.exec_tool("verify", ok=False)
        report = json.loads(verify.stdout)
        self.assertFalse(report["ok"])
        self.assertTrue(any("invalid status" in error for error in report["errors"]), report["errors"])


if __name__ == "__main__":
    unittest.main()
