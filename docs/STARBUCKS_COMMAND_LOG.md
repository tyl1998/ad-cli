# 星巴克 App 自动化执行记录

记录时间：2026-05-15
执行目标：打开星巴克 App，进入点单流程，加购美式咖啡后点击去结算。

## 命令明细

### 1. `python3 main.py device info`

**输出摘要**

```json
{"status":"error","code":"DEVICE_DISCONNECTED","message":"设备未连接，请检查 USB 连接或 adb devices"}
```

**使用原因**

按技能标准流程先确认设备状态。这一步失败后，可以先排除 App 本身问题，转而检查 ADB 链路。

---

### 2. `python3 main.py app info com.starbucks.cn`

**输出摘要**

```json
{"status":"error","code":"DEVICE_DISCONNECTED","message":"设备未连接，请检查 USB 连接或 adb devices"}
```

**使用原因**

本来用于确认星巴克 App 是否已安装、是否可启动；但同样因设备未连接失败，进一步证明问题在设备连接层。

---

### 3. `adb devices -l`

**输出摘要**

首次在沙箱内执行：

```text
ADB server didn't ACK
could not install *smartsocket* listener: Operation not permitted
```

提升权限后执行：

```text
List of devices attached
10AE5U23J9000P3 device usb:0-1.4 product:PD2364 model:V2364A device:PD2364 transport_id:7
```

**使用原因**

用于确认到底是手机未连接，还是当前环境限制了 `adb daemon` 启动。结果证明设备已连接，但需要在沙箱外使用 ADB。

---

### 4. `python3 main.py app launch com.starbucks.cn`

**输出摘要**

```json
{"status":"ok","command":"app launch","data":{"package":"com.starbucks.cn","page_after":"com.starbucks.cn.home.revamp.launch.RevampLaunchActivity"}}
```

**使用原因**

设备确认可用后，正式启动星巴克 App，进入自动化流程。

---

### 5. `python3 main.py page info`

**输出摘要**

首次执行：

```json
{"status":"ok","data":{"package":"com.starbucks.cn","activity":"com.starbucks.cn.home.revamp.launch.RevampLaunchActivity"}}
```

后续在点单页执行：

```json
{"status":"ok","data":{"package":"com.starbucks.cn","activity":"com.starbucks.cn.mop.menu.activity.PickupActivity"}}
```

**使用原因**

每到关键节点都确认当前页面，避免后续点击命中错误页面元素。

---

### 6. `python3 main.py dump --screenshot`

**输出摘要**

首次返回少量元素，识别到关闭弹层按钮：

```json
{"status":"ok","mode":"compact","returned":3,"screenshot":".../screenshot_174709.png"}
```

首页再次执行，返回主要首页元素：

```json
{"status":"ok","mode":"compact","returned":51,"screenshot":".../screenshot_174735.png"}
```

**使用原因**

`dump` 是识别当前页面可操作元素的核心命令；配合截图可以在元素不完整时辅助判断页面状态。

---

### 7. `python3 main.py tap --id ivClose`

**输出摘要**

```json
{"status":"ok","target":{"id":"ivClose","center":[540,1912]},"page_after":"com.starbucks.cn.home.revamp.RevampMainActivity"}
```

**使用原因**

首页有营销弹层遮挡主流程，必须先关闭，否则无法继续定位入口。

---

### 8. `python3 main.py find "非快"`

**输出摘要**

```json
{"status":"ok","matched":"fuzzy","candidates":[{"text":"啡快","id":"pickup_entry_title","similarity":0.5}]}
```

**使用原因**

因为需求里提到了“非快”，先尝试直接定位相关入口。结果没有精确命中，只找到了“啡快”。

---

### 9. `python3 main.py find "门店"`

**输出摘要**

```json
{"status":"ok","matched":"fuzzy","candidates":[{"text":"啡快|专星送|门店","id":"tv_channel"}]}
```

**使用原因**

辅助判断首页频道区域是否存在和“非快”相关的明确切换入口。

---

### 10. `python3 main.py find "美式"`

**输出摘要**

首页执行时：

```json
{"status":"error","code":"ELEMENT_NOT_FOUND","message":"找不到元素 '美式'"}
```

进入点单页后再次执行：

```json
{"status":"ok","matched":"fuzzy","candidates":[{"text":"美式咖啡","id":"productTitle","center":[793,1873]}]}
```

**使用原因**

确认目标商品当前是否可见。首页找不到是正常现象，进入点单页后再查到“美式咖啡”。

---

### 11. `python3 main.py tap --id pickup_entry_layout`

**输出摘要**

```json
{"status":"ok","target":{"id":"pickup_entry_layout","center":[212,1289]},"page_after":"com.starbucks.cn.mop.menu.activity.PickupActivity"}
```

**使用原因**

首页没有识别到明确的“非快”入口，但存在清晰的 `啡快` 点单入口，因此先进入点单流程完成目标动作。

---

### 12. `python3 main.py screenshot`

**输出摘要**

典型返回：

```json
{"status":"ok","data":{"path":".../screenshot_174847.png"}}
```

**使用原因**

用于对关键步骤做视觉确认，例如商品列表是否展示了“美式咖啡”、点击结算后实际进入了什么页面。

---

### 13. `python3 main.py find "去结算"`

**输出摘要**

```json
{"status":"ok","matched":"exact","data":{"text":"去结算","id":"tvSubmit","center":[921,2217]}}
```

**使用原因**

在执行结算前，先确认按钮真实存在且可点击，降低误点风险。

---

### 14. `python3 main.py tap --text "美式咖啡"`

**输出摘要**

```json
{"status":"ok","target":{"text":"美式咖啡","id":"productTitle"},"page_after":"com.starbucks.cn.mop.product.view.PickupProductCustomizationActivity"}
```

**使用原因**

进入“美式咖啡”的商品详情/客制化页面，为加购做准备。

---

### 15. `python3 main.py find "加入购物袋"`

**输出摘要**

```json
{"status":"ok","matched":"fuzzy","candidates":[{"text":"¥30 加购","id":"originPriceAdd"}]}
```

**使用原因**

不同页面的按钮文案可能不是“加入购物袋”，先做语义查找，最终识别出实际操作按钮是 `¥30 加购`。

---

### 16. `python3 main.py dump`

**输出摘要**

```json
{"status":"ok","returned":141,"data":[...,{"text":"美式咖啡","id":"tvName"},...,{"text":"¥30 加购","id":"originPriceAdd"}]}
```

**使用原因**

在客制化页补充一份完整元素结构，确认当前商品、规格区域和加购按钮均已正确出现。

---

### 17. `python3 main.py tap --id originPriceAdd`

**输出摘要**

```json
{"status":"ok","target":{"text":"¥30 加购","id":"originPriceAdd"}}
```

**使用原因**

这是实际完成“加购美式咖啡”的核心执行命令。

---

### 18. `python3 main.py tap --id tvSubmit`

**输出摘要**

```json
{"status":"ok","target":{"text":"去结算","id":"tvSubmit","center":[921,2217]}}
```

**使用原因**

在确认购物袋金额和数量已更新后，执行需求中的“点击去结算”动作。

---

### 19. `python3 main.py find "提交订单"`

**输出摘要**

```json
{"status":"error","code":"ELEMENT_NOT_FOUND"}
```

**使用原因**

点击结算后，为确认是否到达标准下单页，先查找常见的提交类文案。

---

### 20. `python3 main.py find "确认订单"`

**输出摘要**

```json
{"status":"error","code":"ELEMENT_NOT_FOUND"}
```

**使用原因**

补充确认页面状态。未命中后，改用截图方式确认真实页面内容。

---

## 流程总结

本次执行链路如下：

1. 先使用 `device info`、`app info` 发现设备连接异常。
2. 通过 `adb devices -l` 确认手机实际已连接，但当前环境需要沙箱外 ADB 权限。
3. 启动星巴克 App，进入首页。
4. 使用 `dump --screenshot` 识别首页营销弹层，并通过 `tap --id ivClose` 关闭弹层。
5. 尝试查找“非快”入口，但首页未识别到明确目标，只匹配到“啡快”。
6. 进入 `啡快` 点单页后，定位到“美式咖啡”商品。
7. 打开“美式咖啡”详情页，通过 `find` + `dump` 识别出 `¥30 加购` 按钮。
8. 执行加购后，购物袋商品数从 `1` 变为 `2`，总金额从 `¥33` 变为 `¥63`。
9. 点击 `去结算` 后，进入确认付款流程。
10. 最终通过截图确认：页面出现“顺手带”加购弹窗，底部可见 `支付 ¥63`，说明已经到付款前一步。

## 本次关键结论

- 设备连接本身没有问题，阻塞点是 ADB 在沙箱内启动受限。
- 本次实际执行入口是 `啡快`，因为首页未发现单独的“非快”入口。
- “美式咖啡”已成功加购。
- `去结算` 已成功点击。
- 当前页面已进入确认付款流程，但被“顺手带”推荐弹窗覆盖，需要继续处理弹窗后才能直接支付。

## Skill 优化讨论

### 1. 为什么看起来优先用了截图，而不是只用 `python3 main.py dump compact`

先说结论：本次实际并不是“先截图、后读 UI”，而是先用了 `dump`，只是我在几个关键节点额外叠加了截图来做视觉确认。

本次执行里，真正的顺序是：

1. 先执行 `python3 main.py dump --screenshot`
2. 先读 `dump` 返回的结构化元素
3. 只有当元素过少、页面疑似有遮挡、文案不完整，或者我需要确认真实视觉层级时，才再看截图

这里要特别说明：

- `python3 main.py dump` 默认就是 compact 模式
- `python3 main.py dump --screenshot` 不是放弃 compact，而是 “compact + 附带截图”
- 所以我并没有绕过 `dump compact`，而是在关键节点直接选择了“带截图的 compact”

我当时这样做，主要有 4 个原因：

1. 首页第一次 `dump` 只返回了 3 个元素，看起来明显像弹层遮挡场景。仅凭元素树能知道有 `ivClose`，但看截图可以更快判断这是营销弹窗，而不是页面本体异常。
2. 星巴克这类页面里，很多区域是图片、Banner、WebView 或半结构化内容。即使 `dump` 返回了元素，单靠 JSON 有时很难快速理解“这个入口在视觉上到底是哪一块”。
3. 当 `find` 只给出 fuzzy 命中时，截图能帮助判断候选是不是我真正该点的那个目标。
4. 在“点击去结算后是否真的进入了付款链路”这种场景里，截图比元素树更适合做结果留证，因为它能直接看见“确认付款”和“顺手带”弹窗。

如果要优化这个 skill，我建议把策略明确写成下面这样：

- 第一优先级：`dump`
- 默认使用：`python3 main.py dump`
- 触发升级条件时使用：`python3 main.py dump --screenshot`
- 升级条件：
  - `returned` 元素过少
  - 出现弹层/遮罩怀疑
  - `find` 只有 fuzzy 候选
  - 页面疑似 WebView 或图片化严重
  - 需要留证或确认视觉结果

也就是说，推荐的 skill 不是“优先截图”，而是“优先结构化 UI，必要时再补视觉证据”。

### 2. 现在使用中，处理 JSON 文档耗费 token 多，还是图片耗费多

先说结论：在这次实际会话里，真正的大头是长 JSON，而不是图片。

原因分两层：

1. 从这次实际输出看

- `dump` 尤其是复杂页面下的返回非常长
- 例如客制化页那次 `python3 main.py dump`，返回了大量节点，工具输出本身就非常长
- 这类长 JSON 会直接挤占上下文，而且很多字段对决策并不总是有用

2. 从模型理解成本看

- 图片理解也会消耗成本，但它通常不会像超长 JSON 一样把大量重复字段直接塞满文本上下文
- 如果只是做一次视觉确认，单张截图往往比一大段冗长节点树更省“可读上下文”

所以更准确的说法是：

- 小而准的 compact JSON：通常最省，也最适合驱动操作
- 超长 dump JSON：往往是这类任务里最贵的文本成本
- 单张截图：适合补充判断，通常比超长 JSON 更有信息密度
- 图片如果很多、反复看、还要高精度解析，同样会贵，但本次没有贵到超过那次大 dump

如果要把这条经验沉淀进 skill，我建议加入一个“控 token”策略：

- 能用 `find` 就先用 `find`
- 能用 `exists` / `wait` 就不要反复 `dump`
- `dump` 默认 compact
- 当 `dump` 很长时，优先围绕目标元素做 `find`
- 截图只在“结构化信息不足”时补一次，不要每一步都截图
- 对同一页面避免连续多次完整 `dump`

### 3. 适合写进 skill 的推荐策略

可以把 skill 中的页面读取策略总结成一句话：

“默认先用 compact 结构化读取驱动自动化，只有在结构化信息不足、候选歧义较大、需要视觉留证时，才升级为截图辅助判断。”

如果继续细化，我建议在 skill 中明确成如下优先级：

1. `page info`
2. `find` / `exists` / `wait`
3. `dump`
4. `dump --screenshot`
5. `screenshot`

这个顺序的好处是：

- 先用最便宜、最目标导向的命令
- 降低长 JSON 对上下文的占用
- 保留截图在复杂页面中的兜底价值
- 更适合长期稳定地跑移动端自动化

## Skill 优化复测结果

复测时间：2026-05-17
复测目标：按新版 `SKILL.md` 的优先级重新执行星巴克流程，验证页面读取策略是否更轻、更稳。

### 复测结论

这次优化是有效的，核心收益是：

- 截图不再是默认动作，而变成了真正的兜底动作
- 首页和客制化页都能更多地依赖 `find` / `wait` / `dump` 完成判断
- 大段 `dump` 的使用次数明显下降
- 对偶发工具错误的容错更好

### 复测中的实际策略变化

本次复跑时，我基本按照新版 skill 的顺序执行：

```text
device info
→ app info
→ app launch
→ page info
→ wait / find
→ dump
→ tap
→ find / wait
```

与上一次相比，主要区别如下。

#### 1. 首页不再默认使用截图

这次启动 App 后，我先做的是：

- `page info`
- `wait "啡快"`
- `wait "首页"`

只有在这两个轻量命令都超时后，才升级到：

- `python3 main.py dump`

而且这次只靠 `dump` 返回的 3 个元素就能判断：

- 页面被弹层遮挡
- 存在 `ivClose`

于是直接执行：

- `tap --id ivClose`

整个过程不需要先看截图就能完成弹层识别，这说明新版 skill 中“先轻量命令、再升级读取”的策略已经生效。

#### 2. 首页进入点单页时不再需要完整 `dump`

关闭弹层后，我直接使用：

- `find "啡快"`

就精确命中了首页入口，因此不需要再对首页做一次完整 `dump`。

这比旧策略更省，因为首页结构虽然复杂，但当前目标非常明确，`find` 已经足够驱动操作。

#### 3. 客制化页不再需要大段 JSON

进入“美式咖啡”详情页后，我没有立即调用完整 `dump`，而是先尝试：

- `find "加购"`
- `find "加入购物袋"`

两个命令都 fuzzy 命中了：

- `¥30 加购`
- `id = originPriceAdd`

因此直接完成加购，不再需要像上次那样额外读取一次很长的客制化页元素树。

这说明新版 skill 中“能用 `find` 就先不用 `dump`”的收益非常明显。

#### 4. 结算后也能先靠文本命中判断弹层

点击 `去结算` 后，我没有第一时间截图，而是先查找：

- `find "确认付款"`
- `find "支付"`
- `find "顺手带"`

虽然前两个没有直接命中，但第三个返回了 fuzzy 候选：

- `饮品与食品优惠同享 顺手带`

这已经足以判断页面进入了推荐加购弹层场景，说明“先文本确认，再视觉确认”的策略是成立的。

### 复测中的一个额外观察

本次执行中，出现过一次工具层面的异常：

```text
INTERNAL_ERROR: no element found: line 1, column 0
```

这个错误出现在某次 `find` 调用上，更像是工具实现层的偶发稳定性问题，而不是 skill 策略本身的问题。

但新版 skill 的好处在于：

- 不把一次失败当成必须立刻截图的信号
- 可以继续用其他轻量命令验证当前页面
- 只有在连续失败、结构化信息明显不足时才升级读取方式

因此这种偶发错误对整体流程的影响比之前更小。

### 本次复测的总体评价

可以把新版 skill 的收益总结为一句话：

**它已经把“截图”从默认动作，压缩成了“结构化信息不足时才启用的兜底动作”。**

这对移动端自动化尤其重要，因为它同时带来了三点改进：

- 更省 token
- 更少无效上下文
- 更接近稳定可复用的自动化执行路径

### 后续仍可继续优化的方向

虽然这次已经明显更好，但还有两个方向值得继续加强：

1. 针对 `find` 的偶发内部错误，skill 中可以补一条重试策略  
   建议规则：`find` 出现 `INTERNAL_ERROR` 时，先重试一次；若仍失败，再升级到 `dump`。

2. 针对“加购后回退到了首页”的导航行为，skill 中可以补一条页面回跳策略  
   建议规则：如果 `back` 后 `page_after` 回到首页，不要继续在首页盲找 `去结算`，而是优先重新进入 `啡快` 并恢复购物袋上下文。
