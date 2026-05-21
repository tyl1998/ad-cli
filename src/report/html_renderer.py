"""HTML 报告渲染模块 — 将报告数据渲染为单文件 index.html。"""

from __future__ import annotations

import json
from html import escape


def build_root_index_html(runs: list[dict]) -> str:
    """
    生成 report/ 根目录的 index.html，列出所有用例集执行记录。
    runs: 每个元素 { run_id, suite_name, status, started_at, finished_at,
                    total_cases, passed, failed, skipped, report_dir, run_dir_name }
    """
    rows_html = ""
    for r in runs:
        status = r.get("status", "unknown")
        badge_color = {"finished": "#15803d", "running": "#2563eb", "failed": "#b91c1c"}.get(status, "#6b7280")
        badge_label = {"finished": "完成", "running": "进行中", "failed": "失败"}.get(status, status)
        total = r.get("total_cases", 0)
        passed = r.get("passed", 0)
        failed_cnt = r.get("failed", 0)
        skipped = r.get("skipped", 0)
        suite_name = escape(r.get("suite_name", r.get("run_id", "-")))
        run_dir = escape(r.get("run_dir_name", ""))
        started = (r.get("started_at") or "")[:19].replace("T", " ")
        finished = (r.get("finished_at") or "")[:19].replace("T", " ")
        rows_html += f'''
        <a class="run-card" href="{run_dir}/index.html">
          <div class="run-header">
            <span class="run-name">{suite_name}</span>
            <span class="badge" style="background:{badge_color}">{badge_label}</span>
          </div>
          <div class="run-meta">
            <span>🕐 {started}</span>
            {"<span>→ " + finished + "</span>" if finished else ""}
          </div>
          <div class="run-stats">
            <span class="stat total">共 {total} 个 case</span>
            {"<span class='stat ok'>✓ " + str(passed) + " 通过</span>" if passed else ""}
            {"<span class='stat err'>✗ " + str(failed_cnt) + " 失败</span>" if failed_cnt else ""}
            {"<span class='stat skip'>— " + str(skipped) + " 跳过</span>" if skipped else ""}
          </div>
        </a>'''

    if not rows_html:
        rows_html = '<div class="empty">暂无报告</div>'

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ad-cli 测试报告</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f3f6fb; color: #111827; min-height: 100vh; }}
    .topbar {{ background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 28px 32px; }}
    .topbar h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 6px; }}
    .topbar p  {{ color: rgba(255,255,255,.65); font-size: 13px; }}
    .content {{ max-width: 860px; margin: 28px auto; padding: 0 16px; }}
    .section-title {{ font-size: 13px; font-weight: 600; color: #6b7280;
                      text-transform: uppercase; letter-spacing: .05em; margin-bottom: 12px; }}
    .run-card {{ display: block; text-decoration: none; color: inherit;
                 background: #fff; border: 1px solid #e5e7eb; border-radius: 16px;
                 padding: 18px 20px; margin-bottom: 12px;
                 box-shadow: 0 4px 16px rgba(15,23,42,.05);
                 transition: all .15s ease; }}
    .run-card:hover {{ border-color: #93c5fd; box-shadow: 0 8px 24px rgba(37,99,235,.10); transform: translateY(-1px); }}
    .run-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
    .run-name {{ font-size: 16px; font-weight: 700; flex: 1; }}
    .badge {{ border-radius: 999px; color: #fff; padding: 3px 10px; font-size: 12px; white-space: nowrap; }}
    .run-meta {{ font-size: 12px; color: #6b7280; display: flex; gap: 12px; margin-bottom: 8px; }}
    .run-stats {{ display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; }}
    .stat {{ padding: 2px 8px; border-radius: 6px; background: #f3f4f6; color: #374151; }}
    .stat.ok {{ background: #dcfce7; color: #15803d; }}
    .stat.err {{ background: #fee2e2; color: #b91c1c; }}
    .stat.skip {{ background: #fef9c3; color: #a16207; }}
    .empty {{ text-align: center; color: #9ca3af; padding: 48px 0; font-size: 15px; }}
  </style>
</head>
<body>
  <div class="topbar">
    <h1>📋 ad-cli 测试报告</h1>
    <p>共 {len(runs)} 份执行记录，点击查看详情</p>
  </div>
  <div class="content">
    <div class="section-title">执行记录（最新优先）</div>
    {rows_html}
  </div>
</body>
</html>'''


def build_html(data: dict) -> str:
    meta = data.get("meta", {})
    report_summary = meta.get("summary", {})
    cases = data.get("cases", [])
    executions = data.get("executions", [])
    total_cases = len(cases)
    total_executions = len(executions)
    passed_cases = len([c for c in cases if c.get("status") == "passed"])
    failed_cases = len([c for c in cases if c.get("status") == "failed"])
    business_step_count = report_summary.get("business_step_count", 0)
    evidence_count = report_summary.get("evidence_count", 0)
    issue_count = report_summary.get("issue_count", 0)

    payload = json.dumps(
        {
            "meta": meta,
            "cases": cases,
            "executions": executions,
        },
        ensure_ascii=False,
    ).replace("</script>", "<\\/script>")

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(meta.get("suite_name", "ad-cli report"))}</title>
    <style>
        :root {{
            --bg: #0b1020;
            --panel: #ffffff;
            --panel-soft: #f8fafc;
            --line: #e5e7eb;
            --text: #111827;
            --sub: #6b7280;
            --brand: #2563eb;
            --brand-soft: #dbeafe;
            --ok: #15803d;
            --err: #b91c1c;
            --warn: #a16207;
        }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f3f6fb; color: var(--text); }}
        .topbar {{ background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 24px; }}
        .topbar h1 {{ margin: 0 0 8px; font-size: 28px; }}
        .topbar-meta {{ color: rgba(255,255,255,.8); font-size: 13px; display: flex; gap: 16px; flex-wrap: wrap; }}
        .summary {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }}
        .summary-card {{ background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.08); border-radius: 14px; padding: 14px; }}
        .summary-card .label {{ font-size: 12px; opacity: .8; }}
        .summary-card .value {{ margin-top: 6px; font-size: 24px; font-weight: 700; }}
        .summary-card .sub {{ margin-top: 6px; font-size: 12px; opacity: .75; }}
        .layout {{ display: grid; grid-template-columns: 300px 420px minmax(360px, 1fr); gap: 16px; padding: 16px; height: calc(100vh - 200px); align-items: stretch; }}
        .panel {{ background: var(--panel); border-radius: 16px; border: 1px solid var(--line); box-shadow: 0 8px 30px rgba(15,23,42,.06); display: flex; flex-direction: column; overflow: hidden; }}
        .panel-header {{ padding: 14px 16px; border-bottom: 1px solid var(--line); font-weight: 700; background: var(--panel-soft); flex: 0 0 auto; }}
        .sidebar-list, .timeline-list {{ padding: 8px; overflow-y: auto; flex: 1 1 0; min-height: 0; }}
        .case-item, .timeline-item {{ border: 1px solid transparent; border-radius: 12px; padding: 12px; cursor: pointer; transition: all .15s ease; }}
        .case-item:hover, .timeline-item:hover {{ background: #f8fafc; border-color: #dbeafe; }}
        .case-item.active, .timeline-item.active {{ background: var(--brand-soft); border-color: #93c5fd; }}
        .timeline-item.active {{ padding-bottom: 10px; }}
        .case-title, .timeline-title {{ font-weight: 700; }}
        .case-sub, .timeline-sub {{ color: var(--sub); font-size: 12px; margin-top: 4px; word-break: break-word; }}
        .case-metrics {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; font-size: 11px; color: var(--sub); }}
        .timeline-children {{ margin-top: 10px; border-top: 1px dashed #cbd5e1; padding-top: 10px; display: grid; gap: 8px; }}
        .timeline-child {{ border: 1px solid #dbe3f0; border-radius: 10px; padding: 9px 10px; background: white; cursor: pointer; transition: all .15s ease; }}
        .timeline-child:hover {{ border-color: #93c5fd; background: #f8fbff; }}
        .timeline-child.active {{ border-color: #60a5fa; background: #eff6ff; box-shadow: inset 0 0 0 1px rgba(37,99,235,.08); }}
        .timeline-child-title {{ font-size: 13px; font-weight: 700; }}
        .timeline-child-sub {{ margin-top: 4px; font-size: 11px; color: var(--sub); word-break: break-word; }}
        .badge {{ display: inline-block; border-radius: 999px; color: #fff; padding: 3px 10px; font-size: 12px; margin-top: 8px; }}
        .detail-wrap {{ padding: 0; overflow: hidden; flex: 1 1 0; min-height: 0; display: flex; flex-direction: column; }}
        .detail-scroll {{ flex: 1 1 0; overflow-y: auto; padding: 16px; min-height: 0; }}
        .panel-tools {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 10px 12px; border-bottom: 1px solid var(--line); background: #fff; flex: 0 0 auto; }}
        .tool-btn {{ border: 1px solid #cbd5e1; background: white; color: var(--text); border-radius: 10px; padding: 8px 12px; font-size: 13px; cursor: pointer; }}
        .tool-btn:hover {{ background: #f8fafc; }}
        .tool-btn.primary {{ background: var(--brand); color: white; border-color: var(--brand); }}
        .tool-btn.primary:hover {{ filter: brightness(1.05); }}
        .tool-select {{ border: 1px solid #cbd5e1; background: white; border-radius: 10px; padding: 8px 10px; font-size: 13px; }}
        .tool-spacer {{ flex: 1 1 auto; }}
        .playback-status {{ font-size: 12px; color: var(--sub); }}
        .timeline-mode-tabs {{ display: inline-flex; background: #eef2ff; padding: 4px; border-radius: 12px; gap: 4px; margin-right: 4px; }}
        .timeline-mode-btn {{ border: 0; background: transparent; color: var(--sub); padding: 7px 10px; border-radius: 10px; cursor: pointer; font-size: 12px; font-weight: 700; }}
        .timeline-mode-btn.active {{ background: white; color: var(--brand); box-shadow: 0 1px 3px rgba(15, 23, 42, .08); }}
        .timeline-filter-tabs {{ display: inline-flex; background: #f3f4f6; padding: 4px; border-radius: 12px; gap: 4px; margin-right: 4px; }}
        .timeline-filter-btn {{ border: 0; background: transparent; color: var(--sub); padding: 7px 10px; border-radius: 10px; cursor: pointer; font-size: 12px; font-weight: 700; }}
        .timeline-filter-btn.active {{ background: white; color: #111827; box-shadow: 0 1px 3px rgba(15, 23, 42, .08); }}
        .viewer-tabs {{ display: inline-flex; background: #eaf1ff; padding: 4px; border-radius: 12px; gap: 4px; margin-bottom: 14px; }}
        .viewer-tab {{ border: 0; background: transparent; color: var(--sub); padding: 8px 12px; border-radius: 10px; cursor: pointer; font-size: 13px; font-weight: 600; }}
        .viewer-tab.active {{ background: white; color: var(--brand); box-shadow: 0 1px 3px rgba(15, 23, 42, .08); }}
        .detail-head {{ display: flex; align-items: start; justify-content: space-between; gap: 12px; }}
        .detail-title {{ font-size: 20px; font-weight: 800; }}
        .detail-sub {{ margin-top: 6px; color: var(--sub); font-size: 13px; word-break: break-word; }}
        .meta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }}
        .meta-card {{ background: var(--panel-soft); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }}
        .meta-card .k {{ font-size: 12px; color: var(--sub); }}
        .meta-card .v {{ margin-top: 4px; font-size: 14px; font-weight: 600; word-break: break-word; }}
        .section-title {{ margin-top: 18px; margin-bottom: 10px; font-size: 14px; font-weight: 800; }}
        .shot img {{ width: 100%; border-radius: 12px; border: 1px solid var(--line); background: white; }}
        .json-box {{ white-space: pre-wrap; word-break: break-word; background: #0f172a; color: #e5e7eb; padding: 14px; border-radius: 12px; font-size: 12px; overflow: auto; }}
        .empty {{ color: var(--sub); padding: 16px; }}
        .timeline-dot {{ width: 10px; height: 10px; border-radius: 999px; background: var(--brand); margin-top: 6px; flex: 0 0 auto; }}
        .timeline-row {{ display: grid; grid-template-columns: 18px 1fr; gap: 10px; }}
        .tiny {{ font-size: 12px; color: var(--sub); }}
        .thumb-strip {{ display: none; }}
        .thumb-item {{ border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: white; cursor: pointer; }}
        .thumb-item.active {{ border-color: #60a5fa; box-shadow: 0 0 0 2px rgba(37,99,235,.12); }}
        .thumb-item img {{ width: 100%; height: 90px; object-fit: cover; display: block; background: #f8fafc; }}
        .thumb-meta {{ padding: 8px; font-size: 11px; color: var(--sub); }}
        /* ── Playback player (Midscene-style) ── */
        .playback-layout {{ display: flex; flex-direction: column; gap: 0; flex: 1 1 0; min-height: 0; overflow: hidden; background: #111318; }}
        .canvas-container {{ flex: 1 1 0; min-height: 0; background: #000; border-radius: 10px; margin: 10px 10px 4px; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; }}
        .canvas-container img {{ max-width: 100%; max-height: 100%; width: auto; height: auto; display: block; object-fit: contain; }}
        .control-bar {{ position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(transparent, rgba(0,0,0,.72)); padding: 32px 14px 10px; z-index: 2; pointer-events: none; }}
        .ctrl-top {{ display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 7px; gap: 8px; }}
        .ctrl-name {{ color: #fff; font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }}
        .ctrl-step {{ color: rgba(255,255,255,.65); font-size: 12px; white-space: nowrap; flex-shrink: 0; }}
        .ctrl-chips {{ display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 8px; }}
        .ctrl-chip {{ display: inline-flex; align-items: center; background: rgba(255,255,255,.18); -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px); border-radius: 999px; padding: 2px 8px; font-size: 11px; color: rgba(255,255,255,.9); }}
        .ctrl-chip.warn {{ background: rgba(251,191,36,.22); color: #fbbf24; }}
        .seek-bar {{ height: 3px; background: rgba(255,255,255,.28); border-radius: 2px; overflow: hidden; }}
        .seek-bar-fill {{ height: 100%; background: #2b83ff; border-radius: 2px; transition: width .2s; }}
        .focus-badge {{ position: absolute; bottom: 72px; right: 10px; background: rgba(0,0,0,.80); border: 1px solid rgba(255,255,255,.22); border-radius: 10px; padding: 6px; z-index: 3; }}
        .focus-badge img {{ display: block; width: 160px; height: auto; border-radius: 6px; }}
        .focus-badge-label {{ font-size: 10px; color: rgba(255,255,255,.55); padding: 4px 2px 0; text-align: center; }}
        /* Film strip */
        .film-strip {{ flex: 0 0 auto; background: #1a1d26; border-top: 1px solid rgba(255,255,255,.06); overflow-x: auto; display: flex; align-items: center; gap: 5px; padding: 6px 10px; scrollbar-width: none; }}
        .film-strip::-webkit-scrollbar {{ display: none; }}
        .film-strip .thumb-item {{ flex: 0 0 auto; cursor: pointer; border: 2px solid transparent; border-radius: 5px; overflow: hidden; opacity: .55; transition: opacity .15s, border-color .15s; }}
        .film-strip .thumb-item:hover {{ opacity: .85; }}
        .film-strip .thumb-item.active {{ border-color: #2b83ff; opacity: 1; }}
        .film-strip .thumb-item img {{ display: block; width: 46px; height: 76px; object-fit: cover; }}
        .film-strip-empty {{ flex: 0 0 auto; padding: 8px 4px; font-size: 12px; color: rgba(255,255,255,.4); }}
        .viewer-empty {{ flex: 1; display: flex; align-items: center; justify-content: center; color: rgba(255,255,255,.4); font-size: 13px; text-align: center; padding: 24px; }}
        .summary-block {{ background: var(--panel-soft); border: 1px solid var(--line); border-radius: 14px; padding: 14px; margin-bottom: 16px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 10px; }}
        .summary-item {{ background: white; border: 1px solid var(--line); border-radius: 12px; padding: 10px; }}
        .summary-item .k {{ font-size: 12px; color: var(--sub); }}
        .summary-item .v {{ margin-top: 4px; font-size: 14px; font-weight: 700; word-break: break-word; }}
        .step-list {{ display: grid; gap: 10px; margin-top: 10px; }}
        .step-card {{ border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: white; }}
        .step-card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
        .step-card-title {{ font-weight: 700; }}
        .step-card-sub {{ margin-top: 4px; font-size: 12px; color: var(--sub); }}
        .evidence-strip {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; margin-top: 10px; }}
        .evidence-card {{ border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: white; cursor: pointer; }}
        .evidence-card img {{ width: 100%; height: 100px; object-fit: cover; display: block; }}
        .evidence-card .meta {{ padding: 8px; font-size: 11px; color: var(--sub); }}
        .risk-list {{ display: grid; gap: 10px; margin-top: 10px; }}
        .risk-card {{ border: 1px solid #fecaca; background: #fff7f7; border-radius: 12px; padding: 12px; cursor: pointer; }}
        .risk-card:hover {{ border-color: #f87171; background: #fff1f2; }}
        .risk-title {{ font-size: 13px; font-weight: 700; color: #991b1b; }}
        .risk-sub {{ margin-top: 4px; font-size: 12px; color: #7f1d1d; word-break: break-word; }}
        @media (max-width: 1200px) {{ .layout {{ grid-template-columns: 280px 1fr; height: auto; min-height: calc(100vh - 200px); }} .panel {{ min-height: 400px; }} .panel.detail {{ grid-column: 1 / -1; }} }}
        @media (max-width: 900px) {{ .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .summary-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .layout {{ grid-template-columns: 1fr; height: auto; }} .panel {{ min-height: 320px; }} }}
    </style>
</head>
<body>
    <div class="topbar">
        <h1>{escape(meta.get("suite_name", "ad-cli report"))}</h1>
        <div class="topbar-meta">
            <span>Run ID: {escape(meta.get("run_id", ""))}</span>
            <span>开始：{escape(meta.get("started_at", ""))}</span>
            <span>结束：{escape(str(meta.get("finished_at") or "-"))}</span>
            <span>状态：{escape(meta.get("status", "unknown"))}</span>
        </div>
        <div class="summary">
            <div class="summary-card"><div class="label">Case 数</div><div class="value">{total_cases}</div><div class="sub">已完成 {report_summary.get("completed_case_count", total_cases)}</div></div>
            <div class="summary-card"><div class="label">通过</div><div class="value">{passed_cases}</div><div class="sub">失败 {failed_cases}</div></div>
            <div class="summary-card"><div class="label">业务步骤</div><div class="value">{business_step_count}</div><div class="sub">更贴近业务阅读</div></div>
            <div class="summary-card"><div class="label">执行步数</div><div class="value">{total_executions}</div><div class="sub">原子命令日志</div></div>
            <div class="summary-card"><div class="label">证据点</div><div class="value">{evidence_count}</div><div class="sub">关键截图 / 留证节点</div></div>
            <div class="summary-card"><div class="label">风险/偏航</div><div class="value">{issue_count}</div><div class="sub">error / warning / fallback</div></div>
        </div>
    </div>

    <div class="layout">
        <section class="panel sidebar">
            <div class="panel-header">Cases</div>
            <div id="caseList" class="sidebar-list"></div>
        </section>

        <section class="panel timeline">
            <div class="panel-header">Timeline</div>
            <div class="panel-tools">
                <div class="timeline-mode-tabs">
                    <button id="businessModeBtn" class="timeline-mode-btn active" data-timeline-mode="business">业务步骤</button>
                    <button id="executionModeBtn" class="timeline-mode-btn" data-timeline-mode="execution">执行步骤</button>
                </div>
                <div class="timeline-filter-tabs">
                    <button class="timeline-filter-btn active" data-timeline-filter="all">全部</button>
                    <button class="timeline-filter-btn" data-timeline-filter="evidence">关键截图</button>
                    <button class="timeline-filter-btn" data-timeline-filter="risk">风险/偏航</button>
                </div>
                <button id="prevBtn" class="tool-btn">上一条</button>
                <button id="playBtn" class="tool-btn primary">播放</button>
                <button id="nextBtn" class="tool-btn">下一条</button>
                <select id="speedSelect" class="tool-select">
                    <option value="2500">0.5x</option>
                    <option value="1500" selected>1x</option>
                    <option value="800">2x</option>
                    <option value="400">4x</option>
                </select>
                <div class="tool-spacer"></div>
                <div id="playbackStatus" class="playback-status">未播放</div>
            </div>
            <div id="timelineList" class="timeline-list"></div>
        </section>

        <section class="panel detail">
            <div class="panel-header">Viewer</div>
            <div id="detailPanel" class="detail-wrap"></div>
        </section>
    </div>

    <script id="report-data" type="application/json">{payload}</script>
    <script>
        const raw = document.getElementById('report-data').textContent;
        const state = JSON.parse(raw);
        const caseListEl = document.getElementById('caseList');
        const timelineListEl = document.getElementById('timelineList');
        const detailPanelEl = document.getElementById('detailPanel');
        const prevBtn = document.getElementById('prevBtn');
        const playBtn = document.getElementById('playBtn');
        const nextBtn = document.getElementById('nextBtn');
        const speedSelect = document.getElementById('speedSelect');
        const playbackStatusEl = document.getElementById('playbackStatus');
        const timelineModeButtons = Array.from(document.querySelectorAll('[data-timeline-mode]'));
        const timelineFilterButtons = Array.from(document.querySelectorAll('[data-timeline-filter]'));

        const STATUS_COLORS = {{
            ok: '#15803d',
            error: '#b91c1c',
            passed: '#15803d',
            failed: '#b91c1c',
            skipped: '#a16207',
            running: '#2563eb',
            unfinished: '#6b7280',
            info: '#2563eb',
            warning: '#a16207',
            uncategorized: '#6b7280',
            unknown: '#374151',
        }};

        const cases = [...state.cases];
        const executions = [...state.executions];
        const grouped = new Map();
        executions.forEach(exec => {{
            const key = exec.case_id || '__uncategorized__';
            if (!grouped.has(key)) grouped.set(key, []);
            grouped.get(key).push(exec);
        }});
        if (grouped.has('__uncategorized__')) {{
            cases.push({{
                id: '__uncategorized__',
                name: '未归属 Case',
                description: '未在 case-start / case-end 范围内执行的命令',
                status: 'uncategorized'
            }});
        }}

        let selectedCaseId = cases[0] ? cases[0].id : null;
        let selectedExecutionId = null;
        let selectedBusinessStepId = null;
        let playbackTimer = null;
        let isPlaying = false;
        let activeDetailTab = 'playback';
        let timelineMode = 'business';
        let timelineFilter = 'all';

        function badge(status) {{
            const color = STATUS_COLORS[status] || STATUS_COLORS.unknown;
            return `<span class="badge" style="background:${{color}}">${{status || 'unknown'}}</span>`;
        }}

        function escapeHtml(value) {{
            return String(value ?? '')
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#39;');
        }}

        function currentTimeline() {{
            return grouped.get(selectedCaseId) || [];
        }}

        function currentCase() {{
            return cases.find(item => item.id === selectedCaseId) || null;
        }}

        function currentExecutions() {{
            const list = grouped.get(selectedCaseId) || [];
            return list.filter(item => matchesTimelineFilter(item));
        }}

        function currentBusinessSteps() {{
            const current = currentCase();
            const list = current && current.business_steps ? current.business_steps : [];
            return list.filter(item => matchesTimelineFilter(item));
        }}

        function currentTimelineItems() {{
            return timelineMode === 'business' ? currentBusinessSteps() : currentExecutions();
        }}

        function rawExecutions() {{
            return grouped.get(selectedCaseId) || [];
        }}

        function matchesTimelineFilter(item) {{
            if (timelineFilter === 'all') return true;
            if (timelineFilter === 'evidence') {{
                if (item.analysis) return item.analysis.evidence_level === 'checkpoint';
                return (item.evidence_execution_ids || []).length > 0;
            }}
            if (timelineFilter === 'risk') {{
                if (item.analysis) return (item.analysis.issue_flags || []).length > 0;
                return (item.issue_flags || []).length > 0;
            }}
            return true;
        }}

        function findExecutionById(executionId) {{
            return rawExecutions().find(item => item.id === executionId) || null;
        }}

        function findBusinessStepById(stepId) {{
            return currentBusinessSteps().find(item => item.id === stepId) || null;
        }}

        function currentExecutionIndex() {{
            const list = currentExecutions();
            return list.findIndex(item => item.id === selectedExecutionId);
        }}

        function currentTimelineIndex() {{
            const list = currentTimelineItems();
            if (timelineMode === 'business') {{
                return list.findIndex(item => item.id === selectedBusinessStepId);
            }}
            return list.findIndex(item => item.id === selectedExecutionId);
        }}

        function parseBounds(bounds) {{
            if (!bounds) return null;
            const match = String(bounds).match(/\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]/);
            if (!match) return null;
            return {{
                x1: Number(match[1]),
                y1: Number(match[2]),
                x2: Number(match[3]),
                y2: Number(match[4]),
            }};
        }}

        function getViewport(exec) {{
            if (exec && exec.spotlight && exec.spotlight.viewport) return exec.spotlight.viewport;
            const resolution = state.meta && state.meta.device ? state.meta.device.resolution : null;
            const match = resolution ? String(resolution).match(/(\\d+)x(\\d+)/) : null;
            if (!match) return null;
            return {{ width: Number(match[1]), height: Number(match[2]) }};
        }}

        function percent(value, total) {{
            if (!total) return 0;
            return Math.max(0, Math.min(100, (value / total) * 100));
        }}

        function findPlaybackFrame(exec) {{
            const list = currentTimeline();
            if (!list.length) return null;
            if (exec && exec.screenshot) return {{ frame: exec, exact: true }};
            const currentIndex = exec ? list.findIndex(item => item.id === exec.id) : -1;
            if (currentIndex >= 0) {{
                for (let i = currentIndex; i >= 0; i -= 1) {{
                    if (list[i].screenshot) return {{ frame: list[i], exact: false }};
                }}
                for (let i = currentIndex + 1; i < list.length; i += 1) {{
                    if (list[i].screenshot) return {{ frame: list[i], exact: false }};
                }}
            }}
            const first = list.find(item => item.screenshot);
            return first ? {{ frame: first, exact: false }} : null;
        }}

        function setDetailTab(tab) {{
            activeDetailTab = tab;
            const current = findExecutionById(selectedExecutionId) || currentExecutions()[0];
            renderDetail(current || null);
        }}

        function stopPlayback() {{
            if (playbackTimer) {{
                clearInterval(playbackTimer);
                playbackTimer = null;
            }}
            isPlaying = false;
            playBtn.textContent = '播放';
            updatePlaybackStatus();
        }}

        function updatePlaybackStatus() {{
            const list = currentTimelineItems();
            if (!list.length) {{
                playbackStatusEl.textContent = '当前 Case 无步骤';
                return;
            }}
            const index = Math.max(currentTimelineIndex(), 0);
            const speedLabel = speedSelect.options[speedSelect.selectedIndex].text;
            const label = timelineMode === 'business' ? '业务' : '执行';
            playbackStatusEl.textContent = `${{isPlaying ? '播放中' : '已暂停'}} · ${{label}}第 ${{index + 1}} / ${{list.length}} 步 · ${{speedLabel}}`;
        }}

        function selectExecution(executionId) {{
            selectedExecutionId = executionId;
            const businessStep = currentBusinessSteps().find(step => (step.execution_ids || []).includes(executionId));
            if (businessStep) selectedBusinessStepId = businessStep.id;
            renderTimeline();
        }}

        function selectBusinessStep(stepId) {{
            selectedBusinessStepId = stepId;
            const step = findBusinessStepById(stepId);
            if (step && step.execution_ids && step.execution_ids[0]) {{
                selectedExecutionId = step.execution_ids[0];
            }}
            renderTimeline();
        }}

        function stepExecution(direction) {{
            const list = currentTimelineItems();
            if (!list.length) return;
            let index = currentTimelineIndex();
            if (index < 0) index = 0;
            const nextIndex = Math.min(Math.max(index + direction, 0), list.length - 1);
            if (timelineMode === 'business') {{
                const step = list[nextIndex];
                selectedBusinessStepId = step.id;
                if (step.execution_ids && step.execution_ids[0]) selectedExecutionId = step.execution_ids[0];
            }} else {{
                selectedExecutionId = list[nextIndex].id;
            }}
            renderTimeline();
        }}

        function setTimelineMode(mode) {{
            if (timelineMode === mode) return;
            timelineMode = mode;
            timelineModeButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.timelineMode === mode));
            if (mode === 'business') {{
                const businessSteps = currentBusinessSteps();
                if (!selectedBusinessStepId && businessSteps[0]) selectedBusinessStepId = businessSteps[0].id;
                const step = findBusinessStepById(selectedBusinessStepId) || businessSteps[0];
                if (step && step.execution_ids && step.execution_ids[0]) selectedExecutionId = step.execution_ids[0];
            }} else if (!selectedExecutionId && currentExecutions()[0]) {{
                selectedExecutionId = currentExecutions()[0].id;
            }}
            renderTimeline();
        }}

        function setTimelineFilter(filter) {{
            timelineFilter = filter;
            timelineFilterButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.timelineFilter === filter));
            const filteredExecutions = currentExecutions();
            const filteredSteps = currentBusinessSteps();
            if (timelineMode === 'business') {{
                if (!filteredSteps.find(step => step.id === selectedBusinessStepId)) {{
                    selectedBusinessStepId = filteredSteps[0] ? filteredSteps[0].id : null;
                    const step = filteredSteps[0];
                    selectedExecutionId = step && step.execution_ids && step.execution_ids[0] ? step.execution_ids[0] : null;
                }}
            }} else if (!filteredExecutions.find(item => item.id === selectedExecutionId)) {{
                selectedExecutionId = filteredExecutions[0] ? filteredExecutions[0].id : null;
            }}
            renderTimeline();
        }}

        function togglePlayback() {{
            const list = currentTimelineItems();
            if (!list.length) return;
            if (isPlaying) {{
                stopPlayback();
                return;
            }}

            activeDetailTab = 'playback';
            isPlaying = true;
            playBtn.textContent = '暂停';
            updatePlaybackStatus();

            const tick = () => {{
                const steps = currentTimelineItems();
                if (!steps.length) {{
                    stopPlayback();
                    return;
                }}
                let index = currentTimelineIndex();
                if (index < 0) {{
                    if (timelineMode === 'business') {{
                        selectedBusinessStepId = steps[0].id;
                        selectedExecutionId = (steps[0].execution_ids || [])[0] || selectedExecutionId;
                    }} else {{
                        selectedExecutionId = steps[0].id;
                    }}
                    renderTimeline();
                    return;
                }}
                if (index >= steps.length - 1) {{
                    stopPlayback();
                    return;
                }}
                if (timelineMode === 'business') {{
                    const nextStep = steps[index + 1];
                    selectedBusinessStepId = nextStep.id;
                    selectedExecutionId = (nextStep.execution_ids || [])[0] || selectedExecutionId;
                }} else {{
                    selectedExecutionId = steps[index + 1].id;
                }}
                renderTimeline();
            }};

            playbackTimer = setInterval(tick, Number(speedSelect.value || 1500));
        }}

        function renderCases() {{
            if (!cases.length) {{
                caseListEl.innerHTML = '<div class="empty">暂无 Case</div>';
                return;
            }}
            caseListEl.innerHTML = cases.map(item => `
                <div class="case-item ${{selectedCaseId === item.id ? 'active' : ''}}" data-case-id="${{item.id}}">
                    <div class="case-title">${{escapeHtml(item.name)}}</div>
                    <div class="case-sub">${{escapeHtml(item.description || '')}}</div>
                    <div class="case-metrics">
                        <span>执行：${{(grouped.get(item.id) || []).length}}</span>
                        <span>业务：${{(item.business_steps || []).length}}</span>
                        <span>证据：${{(item.evidence_execution_ids || []).length}}</span>
                    </div>
                    ${{badge(item.status || 'unknown')}}
                </div>
            `).join('');
            caseListEl.querySelectorAll('.case-item').forEach(el => {{
                el.addEventListener('click', () => {{
                    stopPlayback();
                    selectedCaseId = el.dataset.caseId;
                    selectedExecutionId = null;
                    selectedBusinessStepId = null;
                    renderCases();
                    renderTimeline();
                }});
            }});
        }}

        function renderTimeline() {{
            const executionList = currentExecutions();
            const businessList = currentBusinessSteps();
            const list = currentTimelineItems();
            if (!selectedExecutionId && executionList[0]) selectedExecutionId = executionList[0].id;
            if (!selectedBusinessStepId && businessList[0]) selectedBusinessStepId = businessList[0].id;
            if (!list.length) {{
                timelineListEl.innerHTML = '<div class="empty">当前 Case 暂无步骤</div>';
                detailPanelEl.innerHTML = '<div class="empty">暂无详情</div>';
                updatePlaybackStatus();
                return;
            }}
            timelineListEl.innerHTML = timelineMode === 'business'
                ? list.map(step => `
                    <div class="timeline-item ${{selectedBusinessStepId === step.id ? 'active' : ''}}" data-step-id="${{step.id}}">
                        <div class="timeline-row">
                            <div class="timeline-dot" style="background:${{STATUS_COLORS[step.status] || STATUS_COLORS.unknown}}"></div>
                            <div>
                                <div class="timeline-title">${{escapeHtml(step.title || '')}}</div>
                                <div class="timeline-sub">执行 ${{(step.execution_ids || []).length}} 步 · 证据 ${{(step.evidence_execution_ids || []).length}} 个</div>
                                <div class="tiny">${{escapeHtml(step.finished_at || '')}} · ${{escapeHtml(step.kind || '')}}</div>
                            </div>
                        </div>
                        ${{selectedBusinessStepId === step.id ? `
                            <div class="timeline-children">
                                ${{(step.execution_ids || []).map(execId => {{
                                    const exec = findExecutionById(execId);
                                    if (!exec) return '';
                                    return `
                                        <div class="timeline-child ${{selectedExecutionId === exec.id ? 'active' : ''}}" data-child-exec-id="${{exec.id}}">
                                            <div class="timeline-child-title">${{escapeHtml(exec.name || '')}}</div>
                                            <div class="timeline-child-sub">${{escapeHtml((exec.argv || []).join(' '))}}</div>
                                            <div class="tiny">${{escapeHtml(exec.finished_at || '')}} · ${{exec.duration_ms || 0}} ms</div>
                                        </div>`;
                                }}).join('')}}
                            </div>` : ''}}
                    </div>
                `).join('')
                : list.map(exec => `
                    <div class="timeline-item ${{selectedExecutionId === exec.id ? 'active' : ''}}" data-exec-id="${{exec.id}}">
                        <div class="timeline-row">
                            <div class="timeline-dot" style="background:${{STATUS_COLORS[exec.status] || STATUS_COLORS.unknown}}"></div>
                            <div>
                                <div class="timeline-title">${{escapeHtml(exec.name)}}</div>
                                <div class="timeline-sub">${{escapeHtml((exec.argv || []).join(' '))}}</div>
                                <div class="tiny">${{escapeHtml(exec.finished_at || '')}} · ${{exec.duration_ms || 0}} ms</div>
                            </div>
                        </div>
                    </div>
                `).join('');
            timelineListEl.querySelectorAll('.timeline-item').forEach(el => {{
                el.addEventListener('click', () => {{
                    if (timelineMode === 'business') {{
                        selectBusinessStep(el.dataset.stepId);
                    }} else {{
                        selectExecution(el.dataset.execId);
                    }}
                }});
            }});
            timelineListEl.querySelectorAll('.timeline-child').forEach(el => {{
                el.addEventListener('click', (event) => {{
                    event.stopPropagation();
                    stopPlayback();
                    selectExecution(el.dataset.childExecId);
                }});
            }});
            updatePlaybackStatus();
            renderDetail(findExecutionById(selectedExecutionId) || executionList[0] || null);
        }}

        function renderDetail(exec) {{
            if (!exec) {{
                detailPanelEl.innerHTML = '<div class="empty">暂无详情</div>';
                return;
            }}
            const resultJson = escapeHtml(JSON.stringify(exec.result || {{}}, null, 2));
            const note = exec.note || null;
            const page = exec.page || {{}};
            const dump = exec.dump_summary || {{}};
            const spotlight = exec.spotlight || null;
            const analysis = exec.analysis || {{}};
            const currentCaseData = currentCase() || {{}};
            const summaryCard = currentCaseData.summary_card || {{}};
            const businessSteps = currentCaseData.business_steps || [];
            const currentList = rawExecutions();
            const currentSequence = currentTimelineItems();
            const activeIndex = Math.max(currentTimelineIndex(), 0);
            const progress = currentSequence.length ? Math.round(((activeIndex + 1) / currentSequence.length) * 100) : 0;
            const screenshots = currentList.filter(item => item.screenshot);
            const playbackFrame = findPlaybackFrame(exec);
            const playbackExec = playbackFrame ? playbackFrame.frame : null;

            const noteBlock = note
                ? `<div class="section-title">AI 备注</div><div class="meta-card"><div class="k">标题</div><div class="v">${{escapeHtml(note.title || '')}}</div><div class="k" style="margin-top:8px;">内容</div><div class="v">${{escapeHtml(note.content || '')}}</div></div>`
                : '';
            const evidenceExecutions = currentList.filter(item => item.analysis && item.analysis.evidence_level === 'checkpoint' && item.screenshot);
            const riskExecutions = currentList.filter(item => item.analysis && (item.analysis.issue_flags || []).length > 0);
            const evidenceBlock = evidenceExecutions.length
                ? `<div class="section-title">证据检查点</div>
                   <div class="evidence-strip">${{evidenceExecutions.slice(0, 6).map(item => `
                        <div class="evidence-card" data-evidence-id="${{item.id}}">
                            <img src="${{escapeHtml(item.screenshot)}}" alt="${{escapeHtml(item.name || '')}}">
                            <div class="meta">${{escapeHtml(item.name || '')}} · ${{escapeHtml((item.analysis || {{}}).evidence_reason || '')}}</div>
                        </div>`).join('')}}</div>`
                : '';
            const riskBlock = riskExecutions.length
                ? `<div class="section-title">风险 / 偏航</div>
                   <div class="risk-list">${{riskExecutions.slice(0, 6).map(item => `
                        <div class="risk-card" data-risk-id="${{item.id}}">
                            <div class="risk-title">${{escapeHtml(item.name || '')}}</div>
                            <div class="risk-sub">${{escapeHtml(((item.analysis || {{}}).issue_flags || []).join(' / ') || '存在异常或恢复动作')}}</div>
                        </div>`).join('')}}</div>`
                : '';
            const businessStepBlock = businessSteps.length
                ? `<div class="section-title">业务步骤</div>
                   <div class="step-list">${{businessSteps.slice(0, 8).map(step => `
                        <div class="step-card">
                            <div class="step-card-head">
                                <div>
                                    <div class="step-card-title">${{escapeHtml(step.title || '')}}</div>
                                    <div class="step-card-sub">执行 ${{(step.execution_ids || []).length}} 步 · 证据 ${{(step.evidence_execution_ids || []).length}} 个</div>
                                </div>
                                ${{badge(step.status || 'unknown')}}
                            </div>
                        </div>`).join('')}}</div>`
                : '';
            const pageBefore = exec.result && exec.result.page_before ? exec.result.page_before : {{}};
            const pageAfter = exec.result && exec.result.page_after ? exec.result.page_after : {{}};
            const pageCompareBlock = (pageBefore.package || pageBefore.activity || pageAfter.package || pageAfter.activity)
                ? `<div class="section-title">页面前后对比</div>
                   <div class="meta-grid">
                       <div class="meta-card"><div class="k">前置页面</div><div class="v">${{escapeHtml((pageBefore.package || '') + ' ' + (pageBefore.activity || ''))}}</div></div>
                       <div class="meta-card"><div class="k">结果页面</div><div class="v">${{escapeHtml((pageAfter.package || '') + ' ' + (pageAfter.activity || ''))}}</div></div>
                   </div>`
                : '';
            const interactionBlock = (analysis.interaction_kind || analysis.interaction_reason)
                ? `<div class="section-title">点击解释</div>
                   <div class="meta-grid">
                       <div class="meta-card"><div class="k">交互类型</div><div class="v">${{escapeHtml(analysis.interaction_kind || '')}}</div></div>
                       <div class="meta-card"><div class="k">原因</div><div class="v">${{escapeHtml(analysis.interaction_reason || '未填写')}}</div></div>
                   </div>`
                : '';
            const caseSummaryBlock = summaryCard.case_name
                ? `<div class="summary-block">
                        <div class="detail-head">
                            <div>
                                <div class="detail-title">${{escapeHtml(summaryCard.case_name || '')}}</div>
                                <div class="detail-sub">${{escapeHtml(summaryCard.conclusion || '')}}</div>
                            </div>
                            ${{badge(summaryCard.status || 'unknown')}}
                        </div>
                        <div class="summary-grid">
                            <div class="summary-item"><div class="k">业务步骤</div><div class="v">${{summaryCard.business_step_count || 0}}</div></div>
                            <div class="summary-item"><div class="k">执行步数</div><div class="v">${{summaryCard.execution_count || 0}}</div></div>
                            <div class="summary-item"><div class="k">关键证据</div><div class="v">${{summaryCard.evidence_count || 0}}</div></div>
                            <div class="summary-item"><div class="k">普通留痕</div><div class="v">${{summaryCard.supporting_screenshot_count || 0}}</div></div>
                            <div class="summary-item"><div class="k">Fallback</div><div class="v">${{summaryCard.fallback_count || 0}}</div></div>
                            <div class="summary-item"><div class="k">风险/偏航</div><div class="v">${{summaryCard.issue_count || 0}}</div></div>
                        </div>
                    </div>`
                : '';

            const playbackPanel = playbackExec
                ? `
                <div class="playback-layout">
                    <div class="canvas-container">
                        <img src="${{escapeHtml(playbackExec.screenshot)}}" alt="playback frame">
                        ${{playbackExec.focus_preview ? `
                        <div class="focus-badge">
                            <div class="focus-badge-label">聚焦点位</div>
                            <img src="${{escapeHtml(playbackExec.focus_preview)}}" alt="focus">
                        </div>` : ''}}
                        <div class="control-bar">
                            <div class="ctrl-chips">
                                <span class="ctrl-chip">${{timelineMode === 'business' ? '业务步骤' : '执行步骤'}}</span>
                                <span class="ctrl-chip">${{escapeHtml((playbackExec.analysis || {{}}).evidence_level || 'supporting')}}</span>
                                ${{playbackFrame && !playbackFrame.exact ? '<span class="ctrl-chip warn">最近留证图</span>' : ''}}
                            </div>
                            <div class="ctrl-top">
                                <div class="ctrl-name">${{escapeHtml(playbackExec.name || '')}} <span style="opacity:.55;font-weight:400">${{escapeHtml((playbackExec.argv || []).join(' '))}}</span></div>
                                <div class="ctrl-step">${{activeIndex + 1}} / ${{currentSequence.length || 1}}</div>
                            </div>
                            <div class="seek-bar"><div class="seek-bar-fill" style="width:${{progress}}%"></div></div>
                        </div>
                    </div>
                    <div class="film-strip" id="film-strip">
                        ${{screenshots.length ? screenshots.map(item => `
                            <div class="thumb-item ${{item.id === exec.id ? 'active' : ''}}" data-thumb-id="${{item.id}}">
                                <img src="${{escapeHtml(item.screenshot)}}" alt="${{escapeHtml(item.name || '')}}">
                            </div>`).join('') : '<div class="film-strip-empty">暂无截图留证</div>'}}
                    </div>
                </div>`
                : `
                <div class="playback-layout">
                    <div class="viewer-empty">
                        当前 Case 暂无可播放媒体。<br>
                        建议在点击步骤中使用自动截图，或执行 screenshot / dump --screenshot 留证。
                    </div>
                </div>`;

            const detailView = `
                ${{caseSummaryBlock}}
                <div class="detail-head">
                    <div>
                        <div class="detail-title">${{escapeHtml(exec.name || '')}}</div>
                        <div class="detail-sub">${{escapeHtml((exec.argv || []).join(' '))}}</div>
                    </div>
                    ${{badge(exec.status || 'unknown')}}
                </div>

                <div class="meta-grid">
                    <div class="meta-card"><div class="k">开始时间</div><div class="v">${{escapeHtml(exec.started_at || '')}}</div></div>
                    <div class="meta-card"><div class="k">耗时</div><div class="v">${{exec.duration_ms || 0}} ms</div></div>
                    <div class="meta-card"><div class="k">包名</div><div class="v">${{escapeHtml(page.package || '')}}</div></div>
                    <div class="meta-card"><div class="k">Activity</div><div class="v">${{escapeHtml(page.activity || '')}}</div></div>
                </div>

                ${{interactionBlock}}
                ${{pageCompareBlock}}
                ${{spotlight ? `
                    <div class="section-title">点击留证</div>
                    <div class="meta-grid">
                        <div class="meta-card"><div class="k">动作</div><div class="v">${{escapeHtml(spotlight.action || '')}}</div></div>
                        <div class="meta-card"><div class="k">点位</div><div class="v">${{escapeHtml(`(${{spotlight.x}}, ${{spotlight.y}})`)}}</div></div>
                        <div class="meta-card"><div class="k">元素 ID</div><div class="v">${{escapeHtml(spotlight.target_id || '')}}</div></div>
                        <div class="meta-card"><div class="k">元素文本</div><div class="v">${{escapeHtml(spotlight.target_text || '')}}</div></div>
                    </div>` : ''}}

                ${{(dump.mode || dump.returned || dump.total_elements) ? `
                    <div class="section-title">Dump 摘要</div>
                    <div class="meta-grid">
                        <div class="meta-card"><div class="k">模式</div><div class="v">${{escapeHtml(dump.mode || '')}}</div></div>
                        <div class="meta-card"><div class="k">返回元素</div><div class="v">${{escapeHtml(String(dump.returned ?? ''))}}</div></div>
                        <div class="meta-card"><div class="k">总元素</div><div class="v">${{escapeHtml(String(dump.total_elements ?? ''))}}</div></div>
                        <div class="meta-card"><div class="k">原因</div><div class="v">${{escapeHtml(dump.reason || '')}}</div></div>
                    </div>` : ''}}

                ${{noteBlock}}
                ${{evidenceBlock}}
                ${{riskBlock}}
                ${{businessStepBlock}}

                <div class="section-title">返回 JSON</div>
                <pre class="json-box">${{resultJson}}</pre>
            `;

            detailPanelEl.innerHTML = `
                <div style="flex:0 0 auto;padding:10px 14px 0;">
                    <div class="viewer-tabs">
                        <button class="viewer-tab ${{activeDetailTab === 'playback' ? 'active' : ''}}" data-view-tab="playback">播放</button>
                        <button class="viewer-tab ${{activeDetailTab === 'detail' ? 'active' : ''}}" data-view-tab="detail">详情</button>
                    </div>
                </div>
                ${{activeDetailTab === 'playback'
                    ? playbackPanel
                    : `<div class="detail-scroll">${{detailView}}</div>`
                }}
            `;

            detailPanelEl.querySelectorAll('.viewer-tab').forEach(el => {{
                el.addEventListener('click', () => {{
                    setDetailTab(el.dataset.viewTab);
                }});
            }});

            detailPanelEl.querySelectorAll('.thumb-item').forEach(el => {{
                el.addEventListener('click', () => {{
                    stopPlayback();
                    activeDetailTab = 'playback';
                    selectExecution(el.dataset.thumbId);
                }});
            }});

            detailPanelEl.querySelectorAll('.evidence-card').forEach(el => {{
                el.addEventListener('click', () => {{
                    stopPlayback();
                    activeDetailTab = 'playback';
                    selectExecution(el.dataset.evidenceId);
                }});
            }});

            const activeThumb = detailPanelEl.querySelector('#film-strip .thumb-item.active');
            if (activeThumb) activeThumb.scrollIntoView({{ behavior: 'smooth', inline: 'center', block: 'nearest' }});

            detailPanelEl.querySelectorAll('.risk-card').forEach(el => {{
                el.addEventListener('click', () => {{
                    stopPlayback();
                    activeDetailTab = 'detail';
                    selectExecution(el.dataset.riskId);
                }});
            }});
        }}

        prevBtn.addEventListener('click', () => {{
            stopPlayback();
            stepExecution(-1);
        }});

        nextBtn.addEventListener('click', () => {{
            stopPlayback();
            stepExecution(1);
        }});

        playBtn.addEventListener('click', () => {{
            togglePlayback();
        }});

        speedSelect.addEventListener('change', () => {{
            if (isPlaying) {{
                stopPlayback();
                togglePlayback();
            }} else {{
                updatePlaybackStatus();
            }}
        }});

        document.addEventListener('keydown', (event) => {{
            if (event.target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) return;
            if (event.key === 'ArrowLeft') {{
                stopPlayback();
                stepExecution(-1);
            }}
            if (event.key === 'ArrowRight') {{
                stopPlayback();
                stepExecution(1);
            }}
            if (event.key === ' ') {{
                event.preventDefault();
                togglePlayback();
            }}
        }});

        timelineModeButtons.forEach(button => {{
            button.addEventListener('click', () => {{
                stopPlayback();
                setTimelineMode(button.dataset.timelineMode);
            }});
        }});

        timelineFilterButtons.forEach(button => {{
            button.addEventListener('click', () => {{
                stopPlayback();
                setTimelineFilter(button.dataset.timelineFilter);
            }});
        }});

        renderCases();
        renderTimeline();
    </script>
</body>
</html>'''
