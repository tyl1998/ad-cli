"""
执行记录分析模块
- _build_execution_analysis: 分析单条 execution 的证据等级、问题标记
- _derive_business_steps:    将 execution 列表聚合为业务步骤
- _build_report_summary:     生成整体报告统计摘要
"""
from __future__ import annotations


def build_execution_analysis(execution: dict) -> dict:
    """分析单条 execution，返回 analysis 字典"""
    result = execution.get("result") or {}
    command = execution.get("name") or ""
    argv = execution.get("argv") or []
    note = execution.get("note") or {}
    interaction = result.get("interaction") or {}
    has_screenshot = bool(execution.get("screenshot"))
    issue_flags: list[str] = []

    if execution.get("status") == "error" or result.get("status") == "error":
        issue_flags.append("error")
    note_level = note.get("level")
    if note_level in {"warning", "error"}:
        issue_flags.append(f"note:{note_level}")
    if interaction.get("fallback"):
        issue_flags.append("fallback")

    evidence_level = None
    evidence_reason = None
    if has_screenshot:
        if command == "screenshot":
            evidence_level = "checkpoint"
            evidence_reason = "手动留证截图"
        elif command == "dump" and ("--screenshot" in argv or result.get("screenshot")):
            evidence_level = "checkpoint"
            evidence_reason = "页面结构留证"
        elif command == "report-note":
            evidence_level = "checkpoint"
            evidence_reason = "人工/AI 标记的关键节点"
        elif issue_flags:
            evidence_level = "checkpoint"
            evidence_reason = "异常或风险节点留证"
        elif command in {"tap", "input"}:
                evidence_level = "checkpoint"
                evidence_reason = "点击操作截图"
    return {
        "evidence_level": evidence_level,
        "evidence_reason": evidence_reason,
        "interaction_kind": interaction.get("kind"),
        "interaction_reason": interaction.get("reason"),
        "is_fallback": bool(interaction.get("fallback")),
        "issue_flags": issue_flags,
    }


# ── business step 推导 ───────────────────────────────────────

def derive_business_steps(executions: list[dict]) -> list[dict]:
    """将 execution 列表聚合为业务步骤列表"""
    steps: list[dict] = []
    current_step: dict | None = None

    for execution in executions:
        if _should_start_business_step(execution, current_step):
            current_step = _make_business_step(execution, len(steps))
            steps.append(current_step)

        if current_step is None:
            current_step = _make_business_step(execution, len(steps))
            steps.append(current_step)

        current_step["execution_ids"].append(execution["id"])
        current_step["finished_at"] = execution.get("finished_at")

        analysis = execution.get("analysis", {})
        if analysis.get("evidence_level") == "checkpoint":
            current_step["evidence_execution_ids"].append(execution["id"])
        for issue in analysis.get("issue_flags", []):
            if issue not in current_step["issue_flags"]:
                current_step["issue_flags"].append(issue)
        if execution.get("status") == "error":
            current_step["status"] = "error"

    return steps


def _make_business_step(execution: dict, index: int) -> dict:
    return {
        "id": f"bstep-{index + 1:03d}",
        "title": _business_step_title(execution),
        "kind": _business_step_kind(execution),
        "status": execution.get("status", "unknown"),
        "started_at": execution.get("started_at"),
        "finished_at": execution.get("finished_at"),
        "execution_ids": [],
        "evidence_execution_ids": [],
        "issue_flags": [],
    }


def _should_start_business_step(execution: dict, current_step: dict | None) -> bool:
    if current_step is None:
        return True
    command = execution.get("name")
    analysis = execution.get("analysis", {})
    if command in {"app", "tap", "input", "scroll", "back", "keyevent", "screenshot"}:
        return True
    if command == "dump" and analysis.get("evidence_level") == "checkpoint":
        return True
    if command == "report-note":
        return True
    return False


def _business_step_kind(execution: dict) -> str:
    command = execution.get("name") or "unknown"
    if command == "tap":
        return "interaction"
    if command == "input":
        return "input"
    if command == "report-note":
        return "observation"
    if command == "dump":
        return "checkpoint"
    return command


def _business_step_title(execution: dict) -> str:
    command = execution.get("name") or "步骤"
    result = execution.get("result") or {}
    note = execution.get("note") or {}
    interaction = result.get("interaction") or {}

    if command == "app":
        action = (execution.get("argv") or [""])[1] if len(execution.get("argv") or []) > 1 else ""
        package = ((result.get("data") or {}).get("package") or "应用")
        mapping = {"launch": "启动", "stop": "关闭", "install": "安装"}
        return f"{mapping.get(action, action or '操作')} {package}".strip()
    if command == "tap":
        target = result.get("target") or {}
        label = target.get("text") or target.get("id") or target.get("xy") or "目标区域"
        return f"点击 {label}"
    if command == "input":
        target = result.get("target") or {}
        label = target.get("text") or target.get("id") or "输入框"
        return f"输入 {label}"
    if command == "screenshot":
        return "截图留证"
    if command == "dump":
        return "页面结构留证"
    if command == "report-note":
        return note.get("title") or "观察记录"
    if command == "wait":
        query = ((result.get("data") or {}).get("query") or (execution.get("argv") or ["", ""])[1])
        return f"等待 {query}".strip()
    if command == "find":
        query = (execution.get("argv") or ["", ""])[1] if len(execution.get("argv") or []) > 1 else "目标"
        return f"查找 {query}"
    kind = interaction.get("kind")
    if kind:
        return f"{command} · {kind}"
    return command


# ── report summary ───────────────────────────────────────────

def build_report_summary(data: dict) -> dict:
    """生成整体报告统计摘要"""
    cases = data.get("cases", [])
    executions = data.get("executions", [])
    business_step_count = sum(len(case.get("business_steps", [])) for case in cases)
    evidence_count = sum(
        1 for e in executions
        if e.get("analysis", {}).get("evidence_level") == "checkpoint"
    )
    supporting_count = sum(
        1 for e in executions
        if e.get("analysis", {}).get("evidence_level") == "supporting"
    )
    fallback_count = sum(
        1 for e in executions if e.get("analysis", {}).get("is_fallback")
    )
    issue_count = sum(
        1 for e in executions if e.get("analysis", {}).get("issue_flags")
    )
    completed_case_count = len(
        [c for c in cases if c.get("status") in {"passed", "failed", "skipped"}]
    )
    return {
        "case_count": len(cases),
        "completed_case_count": completed_case_count,
        "business_step_count": business_step_count,
        "execution_count": len(executions),
        "evidence_count": evidence_count,
        "supporting_screenshot_count": supporting_count,
        "fallback_count": fallback_count,
        "issue_count": issue_count,
    }
