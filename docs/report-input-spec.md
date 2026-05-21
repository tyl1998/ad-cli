# Midscene 报告系统：入参规范与资源清单

> **目标**：为其他 AI 实现方提供报告生成与管理所需的最小接口契约、数据结构和资源清单。  
> **范围**：仅覆盖报告生成与管理（ReportGenerator + ReportMergingTool + CLI），不涉及 Agent/TaskExecutor 的执行逻辑。

---

## 1. 核心接口契约：IReportGenerator

任何报告生成器实现只需满足此接口即可接入：

```typescript
// packages/core/src/report-generator.ts:36-67
export interface IReportGenerator {
  /**
   * 写入或更新单次执行记录。
   * 每次调用在报告 HTML 中追加一个新的 dump script 标签。
   * 前端会自动按 id 去重，保留最后一次写入。
   *
   * @param execution  当前执行的完整数据
   * @param reportMeta 报告级元数据（groupName, sdkVersion 等）
   * @param attributes 可选的自定义属性（会写入 script 标签的 data-* 属性）
   */
  onExecutionUpdate(
    execution: ExecutionDump,
    reportMeta: ReportMeta,
    attributes?: ReportAttributes,
  ): void;

  /** 等待所有排队写入操作完成 */
  flush(): Promise<void>;

  /** 完成报告。内部调用 flush() */
  finalize(): Promise<string | undefined>;

  /** 获取报告文件路径 */
  getReportPath(): string | undefined;
}
```

### 调用时序

```
onExecutionUpdate(exec1, meta)  ← 第 1 次任务完成
onExecutionUpdate(exec2, meta)  ← 第 2 次任务完成（追加写入）
onExecutionUpdate(exec3, meta)  ← 第 3 次任务完成（追加写入）
...
finalize()                      ← 测试结束，等待写入完成
```

---

## 2. 入参数据结构

### 2.1 ExecutionDump（单次执行记录）— 核心入参

这是每次 `onExecutionUpdate()` 调用时必须传入的数据结构：

```typescript
// packages/core/src/types.ts:452-459, 502-588
interface IExecutionDump {
  /** 稳定唯一标识，用于去重。同一 id 的多次写入只保留最后一次 */
  id?: string;
  /** 执行时间戳（毫秒） */
  logTime: number;
  /** 执行名称，如 "aiTap('搜索按钮')" */
  name: string;
  /** 可选描述 */
  description?: string;
  /** 任务列表（核心数据） */
  tasks: ExecutionTask[];
  /** AI 操作上下文（可选） */
  aiActContext?: string;
}
```

### 2.2 ExecutionTask（单个任务）— 最关键的嵌套结构

```typescript
// packages/core/src/types.ts:410-450
type ExecutionTask = {
  /** 任务唯一 ID */
  taskId: string;
  /** 任务类型：'Planning' | 'Insight' | 'Action Space' | 'Log' */
  type: ExecutionTaskType;
  /** 子类型，如 'LoadYaml' */
  subType?: string;
  /** 任务状态：'pending' | 'running' | 'finished' | 'failed' | 'cancelled' */
  status: string;
  /** 任务参数（类型取决于 type） */
  param?: any;
  /** AI 思考过程 */
  thought?: string;
  /** UI 上下文（含截图） */
  uiContext?: UIContext;
  /** 执行耗时详情 */
  timing?: {
    start: number;
    end?: number;
    cost?: number;
    // ... 更多细分计时
  };
  /** AI 调用用量 */
  usage?: AIUsageInfo;
  /** 录制项列表（含截图） */
  recorder?: ExecutionRecorderItem[];
  /** 缓存命中信息 */
  hitBy?: ExecutionTaskHitBy;
  /** 错误信息 */
  error?: Error;
  errorMessage?: string;
  errorStack?: string;
};
```

### 2.3 UIContext（UI 上下文 + 截图）— 截图来源

```typescript
// packages/core/src/types.ts:121-149
abstract class UIContext {
  /** 当前 UI 状态截图 — 这是报告可视化的核心图片来源 */
  abstract screenshot: ScreenshotItem;
  /** 截图尺寸（缩放后） */
  abstract shotSize: Size;
  /** 缩放截图到逻辑坐标的转换比例 */
  abstract shrunkShotToLogicalRatio: number;
}
```

### 2.4 ScreenshotItem（截图封装）— 截图数据载体

```typescript
// packages/core/src/screenshot-item.ts:35-49
class ScreenshotItem {
  /** 截图唯一 ID */
  readonly id: string;
  /** 截图时间戳 */
  readonly capturedAt: number;
  /** Base64 编码的图片数据（含 data URI 前缀） */
  get base64(): string;
  /** 不含 data URI 前缀的纯 Base64 */
  get rawBase64(): string;
  /** MIME 类型，如 'image/png' */
  get mimeType(): string;
}
```

**关键点**：截图是报告可视化最核心的资源。每个 `UIContext` 和 `ExecutionRecorderItem` 都可能包含截图。

### 2.5 ExecutionRecorderItem（录制项）

```typescript
// packages/core/src/types.ts:363-368
interface ExecutionRecorderItem {
  type: 'screenshot';
  /** 时间戳 */
  ts: number;
  /** 截图（可选） */
  screenshot?: ScreenshotItem;
  /** 时机标记，如 'beforeAction' | 'afterAction' */
  timing?: string;
}
```

### 2.6 ReportMeta（报告元数据）

```typescript
// packages/core/src/types.ts:713-719
interface ReportMeta {
  /** 分组名称，用于报告页面分组显示 */
  groupName: string;
  /** 分组描述（可选） */
  groupDescription?: string;
  /** SDK 版本号 */
  sdkVersion: string;
  /** 使用的模型信息列表 */
  modelBriefs: ModelBrief[];
  /** 设备类型（可选），如 'web' | 'android' | 'ios' */
  deviceType?: string;
}
```

### 2.7 ModelBrief（模型信息）

```typescript
// packages/core/src/types.ts:739-754
interface ModelBrief {
  /** 模型用途，如 'planning' | 'vision' */
  intent?: string;
  /** 模型名称，如 'gpt-4o' */
  name?: string;
  /** 人类可读的模型描述 */
  modelDescription?: string;
}
```

### 2.8 ReportAttributes（自定义属性）

```typescript
// packages/core/src/types.ts:183-186
type ReportAttributes = Record<
  string,
  string | number | boolean | null | undefined
>;
```

这些属性会写入 HTML 中 `<script>` 标签的 `data-*` 属性，前端可用于展示测试用例名称、状态等。

---

## 3. 资源清单

### 3.1 HTML 报告模板（必需）

报告系统需要一个 HTML 模板作为"容器"。模板是一个完整的单页应用，包含：

| 资源 | 说明 |
|------|------|
| **报告查看器 HTML** | 包含内联 CSS/JS 的完整 HTML 文件，提供 Player、Sidebar、Timeline、DetailPanel 等可视化组件 |
| **模板占位符** | 模板中 `REPLACE_ME_WITH_REPORT_HTML` 字符串会被替换为实际报告数据 |

**获取方式**：
- 从 `@midscene/core` 包中提取（构建时已注入）
- 或独立构建 `apps/report` 项目获得 `dist/index.html`

**模板结构**：
```html
<!doctype html>
<html>
  <head>
    <!-- 内联 CSS 和 JS（报告查看器应用） -->
  </head>
  <body>
    <div id="root"></div>
    <!-- 报告数据通过以下标签注入 -->
    <!-- REPLACE_ME_WITH_REPORT_HTML 在此处被替换 -->
  </body>
</html>
```

### 3.2 截图资源

| 模式 | 存储方式 | 说明 |
|------|----------|------|
| **Inline** | Base64 内嵌在 HTML 的 `<script type="midscene-image">` 标签中 | 单文件，适合少量截图 |
| **Directory** | 独立 PNG 文件存储在 `screenshots/` 子目录 | 多文件，适合大量截图 |

### 3.3 报告文件结构

**Inline 模式输出**：
```
midscene-report.html    ← 单个文件，包含所有截图 Base64
```

**Directory 模式输出**：
```
midscene-report.html    ← HTML 文件，截图引用相对路径
screenshots/
  ├── abc123.png        ← 截图文件
  ├── def456.png
  └── ...
```

---

## 4. 报告 HTML 数据格式

### 4.1 Dump Script 标签

报告数据以 `<script type="midscene_web_dump">` 标签嵌入 HTML：

```html
<script type="midscene_web_dump"
        data-group-id="uuid-xxx"
        data-sdk-version="0.20.0"
        data-group-name="测试分组"
        data-test-id="test-1"
        data-test-title="登录测试"
        data-test-status="passed">
{
  "sdkVersion": "0.20.0",
  "groupName": "测试分组",
  "executions": [
    {
      "id": "exec-001",
      "logTime": 1715000000000,
      "name": "aiTap('搜索按钮')",
      "tasks": [
        {
          "taskId": "task-001",
          "type": "Planning",
          "status": "finished",
          "param": { "userQuery": "搜索按钮" },
          "uiContext": {
            "screenshot": { "id": "screenshot-001", "mimeType": "image/png" },
            "shotSize": { "width": 1920, "height": 1080 }
          },
          "timing": { "start": 1715000000100, "end": 1715000002000, "cost": 1900 },
          "recorder": [
            { "type": "screenshot", "ts": 1715000000100, "screenshot": { "id": "screenshot-002", "mimeType": "image/png" }, "timing": "beforeAction" },
            { "type": "screenshot", "ts": 1715000002000, "screenshot": { "id": "screenshot-003", "mimeType": "image/png" }, "timing": "afterAction" }
          ]
        }
      ]
    }
  ],
  "modelBriefs": [
    { "intent": "planning", "name": "gpt-4o", "modelDescription": "GPT-4o" }
  ]
}
</script>
```

### 4.2 Image Script 标签（Inline 模式）

```html
<script type="midscene-image" data-image-id="screenshot-001">
iVBORw0KGgoAAAANSUhEUgAAB4AAAAQ4CAYAAADo08FD...（Base64 数据）
</script>
```

### 4.3 截图引用格式

在 JSON 中，截图以紧凑引用格式出现：

```json
{
  "screenshot": {
    "id": "screenshot-001",
    "mimeType": "image/png",
    "base64": "iVBORw0KGgo..."  // inline 模式
    // 或
    "relativePath": "screenshots/screenshot-001.png"  // directory 模式
  }
}
```

---

## 5. 多报告合并接口

### 5.1 ReportMergingTool

```typescript
// packages/core/src/report.ts:79-315
class ReportMergingTool {
  /**
   * 添加一个报告文件信息
   * @param reportInfo 报告文件路径及其属性
   */
  append(reportInfo: ReportFileWithAttributes): void;

  /**
   * 合并所有已添加的报告为单个 HTML 文件
   * @param outputPath 输出文件路径
   */
  mergeReports(outputPath: string): void;
}

interface ReportFileWithAttributes {
  reportFilePath: string;       // 报告 HTML 文件路径
  attributes: ReportAttributes; // 报告属性
}
```

### 5.2 合并规则

1. **版本检查**：所有报告必须使用相同 SDK 版本
2. **模式检查**：不能混合 inline 和 directory 模式
3. **去重策略**：相同 `id` 的 execution 保留最后一次写入
4. **截图迁移**：directory 模式下，截图文件复制到统一 `screenshots/` 目录

---

## 6. CLI 工具接口

### 6.1 报告拆分

```typescript
// packages/core/src/report-cli.ts:167-185
function splitReportFile(options: {
  reportPath: string;    // 输入：报告 HTML 路径
  outputDir: string;     // 输出：JSON 文件目录
}): {
  outputDir: string;
  files: string[];       // 生成的 JSON 文件列表
}
```

### 6.2 Markdown 转换

```typescript
// packages/core/src/report-cli.ts:187-201
async function reportFileToMarkdown(
  htmlPath: string,      // 输入：报告 HTML 路径
  outputDir: string,     // 输出：Markdown + 截图目录
): Promise<void>
```

---

## 7. 集成方案：如何在其他仓库中使用 Midscene 报告查看器

Midscene 的报告查看器是一个**完全自包含的 HTML 文件**（CSS/JS 全部内联，零外部依赖）。其他仓库只需拿到这个 HTML 模板，然后按规范注入数据即可生成可视化报告。

### 7.1 方案对比

| 方案 | 适用场景 | 复杂度 | 是否需要 Midscene 依赖 |
|------|----------|--------|----------------------|
| **方案 A：直接复制模板 HTML** | 任何语言/框架，最小依赖 | 低 | 否 |
| **方案 B：依赖 `@midscene/core` npm 包** | Node.js/TypeScript 项目 | 中 | 是（npm 包） |
| **方案 C：仅生成数据 JSON，用户自行打开** | 只需生成报告数据 | 最低 | 否 |

### 7.2 方案 A：直接复制模板 HTML（推荐，零依赖）

这是最简单的方案，适用于任何编程语言。

#### 步骤 1：获取报告查看器模板

从 Midscene 项目构建产物中提取：

```bash
# 在 Midscene 仓库中
cd apps/report
pnpm install
pnpm run build
# 构建产物在 apps/report/dist/index.html
```

或者直接从已发布的 `@midscene/core` npm 包中提取（模板已内嵌在 dist 目录的 JS 文件中）。

**最简单的方式**：直接复制 `apps/report/dist/index.html` 构建产物到你的项目中，重命名为 `report-template.html`。

#### 步骤 2：在模板中标记注入点

模板 HTML 的结构如下：

```html
<!doctype html>
<html>
  <head>
    <!-- 内联 CSS 和 JS（报告查看器应用，约 2-3MB） -->
  </head>
  <body>
    <div id="root"></div>
    <!-- 在此处注入报告数据 -->
  </body>
</html>
```

你需要在 `</body>` 之前（或 `</html>` 之前）插入报告数据标签。

#### 步骤 3：注入报告数据

**Inline 模式**（单文件，截图 Base64 内嵌）：

```python
# Python 示例
import json

template = open('report-template.html', 'r', encoding='utf-8').read()

# 1. 注入截图数据
for screenshot in screenshots:
    image_tag = f'<script type="midscene-image" data-image-id="{screenshot["id"]}">{screenshot["base64"]}</script>'
    template = template.replace('</body>', image_tag + '\n</body>')

# 2. 注入报告数据
dump_json = json.dumps(report_dump, ensure_ascii=False)
dump_tag = f'<script type="midscene_web_dump" data-sdk-version="1.0.0" data-group-name="测试报告">{dump_json}</script>'
template = template.replace('</body>', dump_tag + '\n</body>')

open('report.html', 'w', encoding='utf-8').write(template)
```

```javascript
// Node.js 示例
const fs = require('fs');

const template = fs.readFileSync('report-template.html', 'utf-8');

// 构建注入内容
const dumpScript = `<script type="midscene_web_dump" data-sdk-version="1.0.0">${JSON.stringify(reportDump)}</script>`;
const imageScripts = screenshots.map(s =>
  `<script type="midscene-image" data-image-id="${s.id}">${s.base64}</script>`
).join('\n');

// 在 </body> 前注入
const report = template.replace('</body>', imageScripts + '\n' + dumpScript + '\n</body>');
fs.writeFileSync('report.html', report);
```

**Directory 模式**（截图存为独立文件）：

```python
# Python 示例
import os, shutil, base64, json

# 1. 创建输出目录
os.makedirs('output/screenshots', exist_ok=True)

# 2. 保存截图为 PNG 文件
for screenshot in screenshots:
    with open(f'output/screenshots/{screenshot["id"]}.png', 'wb') as f:
        f.write(base64.b64decode(screenshot['base64']))

# 3. 注入报告数据（截图引用相对路径）
# 注意：directory 模式下，JSON 中的截图引用使用 relativePath 而非 base64
template = open('report-template.html', 'r', encoding='utf-8').read()
dump_tag = f'<script type="midscene_web_dump">{json.dumps(report_dump)}</script>'
report = template.replace('</body>', dump_tag + '\n</body>')

# 4. 复制模板到输出目录并写入注入后的内容
shutil.copy('report-template.html', 'output/report.html')
open('output/report.html', 'w', encoding='utf-8').write(report)
```

#### 步骤 4：分发

- **Inline 模式**：只需分发单个 `report.html` 文件，用户用浏览器直接打开即可
- **Directory 模式**：分发整个 `output/` 目录（保持 `screenshots/` 子目录结构），用户打开 `report.html`

### 7.3 方案 B：依赖 `@midscene/core` npm 包

适用于 Node.js/TypeScript 项目，可直接使用 Midscene 提供的工具函数：

```bash
npm install @midscene/core
```

```typescript
import {
  getReportTpl,                    // 获取报告模板 HTML
  reportHTMLContent,               // 将 dump 数据包装为完整 HTML
  insertScriptBeforeClosingHtml,   // 高性能追加写入
  generateDumpScriptTag,           // 生成 <script type="midscene_web_dump"> 标签
  generateImageScriptTag,          // 生成 <script type="midscene-image"> 标签
  ReportMergingTool,               // 多报告合并
} from '@midscene/core';

// 方式 1：一次性生成完整报告
const html = reportHTMLContent(
  JSON.stringify(reportDump),
  { groupName: '测试报告', sdkVersion: '1.0.0' }
);
fs.writeFileSync('report.html', html);

// 方式 2：追加写入（支持多次 onExecutionUpdate）
const tpl = getReportTpl();
fs.writeFileSync('report.html', tpl);
// 每次任务完成时追加
insertScriptBeforeClosingHtml('report.html', generateDumpScriptTag(dumpJson));
// 追加截图
fs.appendFileSync('report.html', generateImageScriptTag(id, base64));
```

### 7.4 方案 C：仅生成数据 JSON

如果不想依赖 Midscene 的报告查看器，可以只生成符合规范的 JSON 数据，让用户自行用 Midscene 报告查看器打开：

```typescript
// 生成符合 IReportActionDump 格式的 JSON
const reportDump = {
  sdkVersion: '1.0.0',
  groupName: '测试报告',
  groupDescription: '可选描述',
  modelBriefs: [
    { intent: 'planning', name: 'gpt-4o', modelDescription: 'GPT-4o' }
  ],
  executions: [
    {
      id: 'exec-001',
      logTime: Date.now(),
      name: 'aiTap("搜索按钮")',
      tasks: [ /* ... */ ]
    }
  ],
  deviceType: 'web'
};

// 保存为 JSON 文件
fs.writeFileSync('report-dump.json', JSON.stringify(reportDump));
```

用户可以通过 Midscene 的 CLI 工具将此 JSON 转换为可视化报告：

```bash
npx @midscene/core report-tool convert --input report-dump.json --output report.html
```

### 7.5 需要复制的文件清单

| 文件 | 来源 | 大小 | 说明 |
|------|------|------|------|
| `apps/report/dist/index.html` | 构建产物 | ~2-3MB | 报告查看器模板（自包含，内联 CSS/JS） |
| 或 `@midscene/core` 包中的模板 | npm 包 | 同上 | 已注入到 `dist/**/*.js` 中 |

**不需要**复制的文件：
- ❌ 所有 `.less` 样式文件 — 已编译内联到模板 HTML 中
- ❌ 所有 `.tsx` 组件源码 — 已编译内联到模板 HTML 中
- ❌ `rsbuild.config.ts` — 仅用于构建，运行时不需要
- ❌ `packages/visualizer/` — 已编译内联到模板 HTML 中

### 7.6 样式说明

报告查看器的所有样式（22 个 LESS 文件，约 4,500+ 行）在构建时通过 Rsbuild 的 [`injectStyles: true`](apps/report/rsbuild.config.ts:159) 配置全部内联到 HTML 中。包括：

- **报告页面**：全局布局、Sidebar 任务表格、DetailPanel 详情面板、Timeline 时间轴、ReportOverview 统计卡片、PlaywrightCaseSelector 用例选择器、DetailSide 详情侧边栏、GlobalHoverPreview 悬停预览
- **Visualizer 共享组件**：Player 播放器、Blackboard 元素高亮、ShinyText 闪光文字、ScreenshotViewer 截图查看器等

**所有组件均支持亮色/暗色双主题**，通过 `[data-theme='dark']` 选择器切换。设计令牌主色为 `#2B83FF`，强调色为 `#F9483E`。

**结论**：其他仓库集成时完全不需要关心样式，模板 HTML 已包含一切。

### 7.7 模板更新策略

当 Midscene 报告查看器更新时（新功能、bug 修复），只需重新构建并替换模板 HTML：

```bash
cd apps/report && pnpm run build
cp dist/index.html /path/to/your/project/report-template.html
```

模板向后兼容：新版本查看器能解析旧格式的 dump 数据。

---

## 8. 最小实现清单

如果另一个 AI 要从零实现报告生成与管理，以下是**最小必需**的内容：

### 8.1 必须实现的接口

| 接口/类 | 优先级 | 说明 |
|---------|--------|------|
| `IReportGenerator` | **必需** | 报告生成核心接口 |
| `ReportMergingTool` | **必需** | 多报告合并 |
| `splitReportFile()` | 可选 | 报告拆分 CLI |
| `reportFileToMarkdown()` | 可选 | Markdown 转换 CLI |

### 8.2 必须处理的数据结构

| 结构 | 优先级 | 说明 |
|------|--------|------|
| `ExecutionDump` | **必需** | 单次执行记录，含 `tasks[]` |
| `ExecutionTask` | **必需** | 任务详情，含 `uiContext.screenshot`、`recorder[]`、`timing` |
| `ScreenshotItem` | **必需** | 截图数据（Base64 或文件路径） |
| `ReportMeta` | **必需** | 报告元数据 |
| `ModelBrief` | 推荐 | 模型信息 |
| `ReportAttributes` | 推荐 | 自定义属性 |

### 8.3 必须处理的资源

| 资源 | 优先级 | 说明 |
|------|--------|------|
| HTML 报告模板 | **必需** | 可视化查看器容器 |
| 截图 Base64 数据 | **必需** | 核心可视化数据 |
| `screenshots/` 目录 | 可选 | Directory 模式截图存储 |

### 8.4 输出格式要求

最终输出必须是**自包含的 HTML 文件**（inline 模式）或 **HTML + screenshots/ 目录**（directory 模式），其中：

1. HTML 包含完整的报告查看器应用（内联 CSS/JS）
2. 报告数据以 `<script type="midscene_web_dump">` 标签嵌入
3. 截图以 `<script type="midscene-image">` 标签嵌入（inline）或相对路径引用（directory）
4. 支持多次追加写入（append-only），前端自动去重

---

## 9. 数据流总结

```
                        ┌──────────────────────────┐
                        │   另一个 AI 实现方         │
                        │   需要提供以下入参：        │
                        │                           │
                        │  • ExecutionDump[]        │
                        │  • ReportMeta             │
                        │  • ScreenshotItem[]       │
                        │  • ReportAttributes       │
                        └──────────┬───────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────┐
                        │   IReportGenerator        │
                        │                           │
                        │  onExecutionUpdate()      │
                        │  flush()                  │
                        │  finalize()               │
                        └──────────┬───────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────┐
                        │   输出：报告 HTML 文件      │
                        │                           │
                        │  • 自包含 HTML（inline）   │
                        │  • HTML + screenshots/    │
                        │    （directory）           │
                        └──────────────────────────┘