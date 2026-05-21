#!/usr/bin/env python3
"""
生成 UI 树结构的简化可视化图
"""

def generate_structure_diagram():
    """生成 UI 树结构图"""
    
    diagram = """
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃          STARBUCKS APP - UI TREE STRUCTURE                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

层级关系（完整的嵌套结构）：

【顶层】
D1 FrameLayout (root)
 ├─ 布局层级
 │  └─ FrameLayout
 │     └─ LinearLayout [action_bar_root]
 │
 ├─ 【主内容区】D6-D10
 │  └─ ViewGroup [home_main_root]
 │     ├─ FrameLayout [nav_host_fragment]
 │     │  └─ FrameLayout [home_root_layout]
 │     │     └─ ViewGroup [refreshLayout]
 │     │        └─ ScrollView [scroll_layout] 📜 可滚动
 │     │           └─ ViewGroup [clContainer]
 │     │              ├─【头部内容】D12-D17
 │     │              │  ├─ FrameLayout [holidayHeader]
 │     │              │  ├─ FrameLayout [blur_root]
 │     │              │  ├─ RecyclerView [format_header_view]
 │     │              │  └─ RecyclerView [format_content_view]
 │     │              │     ├─【卡片】D15-D21
 │     │              │     │  ├─ CardView
 │     │              │     │  │  └─ ViewGroup [topCardLayout]
 │     │              │     │  │     └─ ViewGroup [logInLayout]
 │     │              │     │  │        ├─ ImageView [iv_bg]
 │     │              │     │  │        ├─ ImageView [iv_mood]
 │     │              │     │  │        ├─ ImageView [iv_product]
 │     │              │     │  │        ├─ TextView [tv_title] 📝 "美运黑金"
 │     │              │     │  │        └─ ImageView [bt_close] 🖱️ 可点击
 │     │              │     │  │
 │     │              │     │  └─【业务入口】D17-D21
 │     │              │     │     ├─ ViewGroup [pickup_entry_layout] 🖱️
 │     │              │     │     │  ├─ ImageView [pickup_entry]
 │     │              │     │     │  └─ TextView [pickup_entry_title] "啡快"
 │     │              │     │     │
 │     │              │     │     ├─ ViewGroup [delivery_entry_layout] 🖱️
 │     │              │     │     │  ├─ ImageView [delivery_entry_anim]
 │     │              │     │     │  └─ TextView [delivery_entry_title] "专星送"
 │     │              │     │     │
 │     │              │     │     └─ ViewGroup [room_entry] 🖱️
 │     │              │     │        ├─ ImageView [room_entry]
 │     │              │     │        └─ TextView [room_entry_title] "生活馆"
 │     │              │     │
 │     │              │     └─【菜单项】D20-D21
 │     │              │        ├─ LinearLayout 🖱️
 │     │              │        │  └─ ImageView [ivIcon] + TextView [tvTitle] "省心购"
 │     │              │        ├─ LinearLayout 🖱️
 │     │              │        │  └─ ImageView [ivIcon] + TextView [tvTitle] "多人团餐"
 │     │              │        ├─ LinearLayout 🖱️
 │     │              │        │  └─ ImageView [ivIcon] + TextView [tvTitle] "送心意"
 │     │              │        └─ LinearLayout 🖱️
 │     │              │           └─ ImageView [ivIcon] + TextView [tvTitle] "外卖拼单"
 │     │              │
 │     │              └─【用户信息区】D17-D21
 │     │                 ├─ ViewGroup [avatarView] 🖱️ [D18]
 │     │                 │  ├─ ImageView [avatar_border_image]
 │     │                 │  ├─ ImageView [border_view]
 │     │                 │  └─ ImageView [avatar_view]
 │     │                 │
 │     │                 ├─ LinearLayout [starLayout] 🖱️ [D18]
 │     │                 │  └─ TextView [star_count] "204.2"
 │     │                 │
 │     │                 └─ TextView [coupon_button] 🖱️ [D18]
 │     │                    └─ "6张好礼券"
 │     │
 │     └─【底部导航】D8-D11
 │        └─ LinearLayout [bottom_navigation]
 │           ├─ FrameLayout 🖱️ [D8]
 │           │  └─ TextView "首页"
 │           ├─ FrameLayout 🖱️ [D8]
 │           │  └─ TextView "星会员"
 │           ├─ FrameLayout 🖱️ [D8]
 │           │  └─ ImageView
 │           ├─ FrameLayout 🖱️ [D8]
 │           │  └─ TextView "订单"
 │           └─ FrameLayout 🖱️ [D8]
 │              └─ TextView "我的"
 │
 └─【其他容器】
    ├─ FrameLayout [fragNewVersionGuideContainer]
    ├─ FrameLayout [birthday_theme_container]
    └─ FrameLayout [pullTipView]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 统计信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

最深层级：D21（从顶层算起）
├─ D1-D8：框架/容器层（导航、状态栏等）
├─ D9-D14：业务内容容器（卡片、列表等）
├─ D15-D19：业务元素（文本、图片、按钮）
└─ D20-D21：最细粒度的 UI 组件（菜单图标、按钮文本）

类型分布：
├─ ViewGroup           28 个 (框架)
├─ ImageView           26 个 (图片元素 ⭐ 叶子节点)
├─ TextView            26 个 (文本元素 ⭐ 叶子节点)
├─ FrameLayout         22 个 (容器)
└─ 其他                14 个 (列表、布局等)

可交互元素：26 个
├─ 深度 9：5 个 (底部菜单)
├─ 深度 11：1 个 (滚动容器)
├─ 深度 15-18：11 个 (卡片按钮、优惠券等)
└─ 深度 20：7 个 (菜单项、抽奖)

底层元素（叶子节点）：60 个
├─ ImageView：26 个 ⭐ (最终展示的图片)
├─ TextView：26 个 ⭐ (最终展示的文本)
└─ 其他：8 个 (装饰元素)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 结论：UI 树是完整的多层嵌套结构
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 不只是顶层 UI，包括了：
   ✓ 深层容器和布局
   ✓ 各个深度的业务元素
   ✓ 最底层的真实内容（图片、文本）
   ✓ 所有交互目标（按钮、菜单等）

🔍 可以用于：
   ✓ 完整的 UI 自动化
   ✓ 准确的元素定位
   ✓ 内容的完整提取
   ✓ 用户行为分析
"""
    
    return diagram

if __name__ == '__main__':
    print(generate_structure_diagram())
    
    # 保存到文件
    with open('/Users/atan/Desktop/work/vscode_debug/ad-cli/UI_TREE_STRUCTURE.txt', 'w', encoding='utf-8') as f:
        f.write(generate_structure_diagram())
    
    print("\n✅ 结构图已保存到 UI_TREE_STRUCTURE.txt")
