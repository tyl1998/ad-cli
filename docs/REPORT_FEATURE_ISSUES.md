# Report 功能复测问题记录

记录时间：2026-05-17
场景：基于最新版 `SKILL.md`，执行“星巴克-啡快-美式加购后去结算” case 时，对新增 `report` 功能进行实际验证。

## 问题 1：已有 active report 时，`report start` 无法直接复用

### 现象

执行：

```bash
python3 main.py report start "星巴克回归用例集"
```

返回：

```json
{
  "status": "error",
  "command": "cli",
  "code": "RUNTIME_ERROR",
  "message": "已有激活中的报告：/Users/atan/Desktop/work/vscode_debug/ad-cli/src/report/交互报告验证-20260517-173536，请先 finalize"
}
```

### 影响

- 当环境里已经存在一个未结束的 active report 时，新的执行无法自然开启新报告
- AI 必须先额外判断“是复用当前报告，还是结束旧报告，再开新报告”
- 如果 skill 没明确约束，执行路径容易变得不一致

### 建议

有两种可选优化方向：

1. 工具层优化  
   `report start` 增加类似 `--reuse-active` 或 `--force-new` 语义。

2. skill 层优化  
   在工作流中明确要求：
   - 先执行 `report status`
   - 如果已有 active report，则先决定“复用”还是“finalize 后重开”

## 问题 2：`report case-pass` 和 `report finalize` 并行执行会产生竞态

### 现象

我并行执行了：

```bash
python3 main.py report case-pass --summary "已进入星巴克确认付款页；首页弹层、客制化页加购、结算后加载遮罩均被记录进报告"
python3 main.py report finalize
```

结果：

- `report finalize` 成功
- `report case-pass` 失败

失败返回：

```json
{
  "status": "error",
  "command": "report",
  "code": "REPORT_NOT_ACTIVE",
  "message": "当前没有激活中的报告，请先执行 report start"
}
```

### 根因判断

`finalize` 先完成，导致 active report 被关闭；随后 `case-pass` 再执行时，已经拿不到 active report 上下文。

这是一个典型的时序竞争问题。

### 影响

- 虽然整个报告目录成功生成
- 但 case 状态没有被正常收口
- 容易造成“suite 看起来完成了，但 case 实际仍是 unfinished”的不一致结果

### 实际验证结果

我检查了最终报告文件：

- [report.json](/Users/atan/Desktop/work/vscode_debug/ad-cli/src/report/交互报告验证-20260517-173536/report.json)

结果确认：

- suite 状态为 `passed`
- `case-002` 状态为 `unfinished`

这说明报告整体完成了，但当前 case 没有在 finalize 前成功执行 `case-end/case-pass`。

### 建议

这是当前最需要修复的问题。

建议明确约束：

```text
report case-end / case-pass / case-fail
→ report finalize
```

必须串行执行，不能并行。

如果希望工具本身更稳，也可以考虑：

1. `report finalize` 自动检查当前是否有 `running` case  
   如果有，则拒绝 finalize，提示先 `case-end`

2. `report finalize` 自动将当前 running case 收口为某种默认状态  
   例如 `unfinished`

3. `report case-end` 在没有 active report 时，给出更明确提示  
   说明可能是 finalize 已先执行

## 问题 3：`find` 与 `tap --id` 在同一元素上的一致性不足

### 现象

在客制化页，我先执行：

```bash
python3 main.py find "ivBackButton"
```

返回精确命中：

```json
{
  "status": "ok",
  "command": "find",
  "matched": "exact",
  "data": {
    "type": "ImageView",
    "text": "",
    "id": "ivBackButton",
    "center": [96, 216],
    "bounds": "[48,168][144,264]",
    "clickable": true
  }
}
```

但紧接着执行：

```bash
python3 main.py tap --id ivBackButton
```

返回：

```json
{
  "status": "error",
  "command": "tap",
  "code": "ELEMENT_NOT_FOUND",
  "message": "找不到元素 'ivBackButton'，建议先调用 dump 确认当前页面元素"
}
```

### 影响

- `find` 结果无法稳定转化为 `tap --id`
- AI 即使已经识别到元素，仍可能被迫退回到坐标点击
- 这会降低通过结构化元素实现稳定自动化的可靠性

### 建议

工具层应尽量保证：

- `find` 返回的 `id`
- 能被 `tap --id`
- 在同一页面状态下直接复用

如果暂时做不到，建议在 skill 中明确 fallback：

```text
find 命中元素
→ 先尝试 tap --id
→ 若失败但 find 返回了 center，则立即 fallback 到 tap --xy
```

## 问题 4：客制化页返回后的实际导航行为与预期不一致

### 现象

在“美式咖啡”客制化页加购后，我尝试返回上一页，预期是回到点单商品列表页。

但无论是：

- `back`
- 还是基于返回按钮坐标的 `tap --xy`

最终都回到了首页，而不是商品列表页。

### 影响

- “加购后立即去结算”的动作链被打断
- 需要重新进入 `啡快` 才能恢复购物袋上下文
- 如果 skill 没定义恢复策略，AI 可能会在首页错误地寻找 `去结算`

### 建议

这更像 App 本身的页面导航行为，不一定是工具 bug。

但 skill 应该把恢复策略写清楚：

```text
若从客制化页返回后落到首页
→ 不要继续在首页寻找去结算
→ 优先重新进入啡快
→ 再用 wait/find 恢复购物袋与结算按钮上下文
```

## 总结

这次报告功能的新增方向是正确的，尤其是：

- 普通执行命令自动落 execution
- `report note` 可以写入 AI 判断
- `dump --screenshot` 与截图资产能够一起进报告

但当前复测中暴露出的核心问题也很明确：

1. `report start` 对已有 active report 的处理策略还不够顺手
2. `case-end` 与 `finalize` 存在明显竞态，必须优先修复
3. `find` 与 `tap --id` 的一致性还有提升空间
4. 部分页面返回后的导航恢复策略需要在 skill 中显式定义

其中优先级最高的问题是：

**`report case-end/case-pass` 与 `report finalize` 不能并行，否则会导致 case 留在 `unfinished`。**

## Skill 设计层面的补充优化建议

除了上面这些已经在复测中暴露出来的具体问题，这次讨论里还有 3 个更偏“技能设计层”的优化点，也值得一起沉淀下来。

### 建议 1：补充执行前上下文约束，减少 AI 猜测成本

当前 skill 已经把命令优先级、弹窗处理、报告流程写得比较清楚了，但还缺少一层“执行前上下文约定”。

这会导致 AI 在执行时仍然需要自行猜测一些高影响问题，例如：

- 购物车是否必须为空
- App 是否必须冷启动
- 是否允许复用上一次购物袋上下文
- “进入结算”是指点击 `去结算` 就算完成，还是进入 `确认付款` 才算完成
- 用户口语里的别名如何映射到真实页面文案
- 失败后优先重试、回退、还是重新进业务入口

### 影响

这些信息如果缺失，会让同一个 case 在不同轮执行时产生不同路径，导致：

- 报告结果不一致
- 执行步骤数量波动大
- 同一个业务目标可能被不同 agent 解读成不同终点

### 建议

建议在 `SKILL.md` 中新增一个“执行前上下文约定”小节，至少明确以下几类信息：

1. 起始状态  
   例如：购物车默认可复用还是必须清空。

2. 业务完成判定  
   例如：“进入结算”默认指到 `确认付款` 页，而不是只点击 `去结算` 按钮。

3. 业务别名映射  
   例如：
   - 非快 -> 啡快
   - 结算 -> 去结算 / 确认付款 / 支付按钮

4. 失败恢复策略  
   例如：
   - `find` 成功但 `tap --id` 失败时如何 fallback
   - 返回首页后如何恢复到点单上下文

### 建议 2：报告应该区分“技术步骤”和“业务步骤”

本次复测中，`case-002` 的 `execution_count` 是 `38`。

但从业务角度看，这个 case 实际上只有大约 8 到 10 个主要步骤，例如：

1. 打开星巴克
2. 关闭首页弹层
3. 进入啡快
4. 找到美式咖啡
5. 打开商品详情
6. 加购
7. 返回点单上下文
8. 点击去结算
9. 等待页面加载
10. 进入确认付款页

### 为什么会有 38 步

因为当前报告里记录的是**每一条底层命令 execution**，而不是业务步骤。

像下面这些全都会各算一步：

- `device info`
- `app info`
- `page info`
- `wait`
- `find`
- `dump`
- `tap`
- `report note`
- 失败重试
- fallback 动作

### 影响

对排障来说，这种粒度是有价值的；但对业务复盘和人类阅读来说，它会显得过碎：

- 用户以为执行了很多“业务操作”
- 但实际上只是很多中间确认命令
- 报告可读性下降

### 建议

报告建议拆成两层：

1. `execution` 层  
   保留当前的原子命令日志，用于排障和复现。

2. `business_step` 层  
   新增更高层的业务步骤，用于人类阅读。

理想展示方式应该是：

- Timeline 里展示 8 到 10 个业务步骤
- 每个业务步骤展开后，再能看到下层 execution 列表

这样既不丢失技术细节，也能避免“一个简单 case 看起来像跑了 38 步”的观感问题。

### 建议 3：关键步骤应有截图证据，但不应默认每步截图

本次报告里，大多数 execution 都没有截图。

实际检查结果显示，当前带截图的步骤主要来自：

- `dump --screenshot`
- `report note --screenshot`

而普通命令例如：

- `tap`
- `find`
- `wait`
- `page info`

默认都不会附带截图。

### 影响

这会带来一个明显问题：

- 关键业务动作（例如点击啡快、点击加购、点击去结算）
- 在报告中没有直观的视觉证据

所以虽然 execution 很全，但报告对业务确认的说服力不够。

### 但也不建议默认每步截图

如果给每条 execution 都自动截图，会带来新的问题：

- 报告体积显著增大
- 执行耗时上升
- 很多图片其实没有业务价值

### 建议

更合适的做法是引入“关键节点截图策略”。

建议分 3 类：

1. 默认不截图  
   例如：
   - `find`
   - `wait`
   - `exists`
   - `page info`

2. 条件截图  
   例如：
   - `tap`
   - `dump --screenshot`
   - `report note --screenshot`

3. 必须截图的关键业务节点  
   例如：
   - 首页进入前/后
   - 弹层识别或关闭前后
   - 商品加购成功后
   - 点击去结算后
   - 到达确认付款页时
   - 任意 error / timeout / fallback 发生时

### 推荐方向

报告里建议新增“证据检查点”概念，而不是要求每条 execution 都带截图。

也就是说：

- 不是所有技术步骤都要有图
- 但每个关键业务节点都应该有图

这样可以在成本和可读性之间取得更好的平衡。
