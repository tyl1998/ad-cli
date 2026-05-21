#!/usr/bin/env python3
"""
生成 UI 树的详细嵌套结构可视化
"""

import json
from collections import defaultdict

def visualize_ui_hierarchy(tree_path, max_depth=None):
    """可视化 UI 树的层级结构"""
    
    with open(tree_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\n" + "=" * 100)
    print("🌳 ANDROID UI 树完整嵌套结构 (包括底层元素)")
    print("=" * 100)
    
    def get_short_name(class_path):
        """获取类名的短形式"""
        if not class_path:
            return "Unknown"
        return class_path.split('.')[-1]
    
    def print_tree(node, depth=0, is_last=True, max_d=25):
        """递归打印树结构"""
        if max_depth and depth > max_depth:
            return
        
        if depth > max_d:
            return
        
        attrs = node.get('attributes', {})
        
        # 获取节点信息
        class_name = get_short_name(attrs.get('class', 'Unknown'))
        resource_id = attrs.get('resource-id', '')
        text = attrs.get('text', '')
        clickable = attrs.get('clickable', 'false')
        scrollable = attrs.get('scrollable', 'false')
        bounds = attrs.get('bounds', '')
        
        # 构建节点文本
        node_info = class_name
        
        # 添加 resource-id
        if resource_id:
            id_short = resource_id.split('/')[-1]
            node_info += f" [{id_short}]"
        
        # 添加文本内容（超过30字符截断）
        if text:
            text_short = text[:30] + "..." if len(text) > 30 else text
            node_info += f' "{text_short}"'
        
        # 添加交互属性
        attrs_list = []
        if clickable == 'true':
            attrs_list.append("🖱️ clickable")
        if scrollable == 'true':
            attrs_list.append("📜 scrollable")
        if attrs.get('long-clickable') == 'true':
            attrs_list.append("🖱️📅 long-clickable")
        
        # 打印前缀
        prefix = ""
        if depth > 0:
            if is_last:
                prefix = "    " * (depth - 1) + "└─ "
            else:
                prefix = "    " * (depth - 1) + "├─ "
        
        # 颜色代码（简单的 ANSI）
        if attrs_list:  # 可交互元素
            node_display = f"\033[92m{node_info}\033[0m"  # 绿色
            if attrs_list:
                node_display += f" \033[93m({', '.join(attrs_list)})\033[0m"  # 黄色
        else:
            node_display = node_info
        
        # 添加深度信息
        depth_info = f"\033[90m[D{depth}]\033[0m"  # 灰色
        
        print(f"{prefix}{node_display} {depth_info}")
        
        # 处理子节点
        children = node.get('children', [])
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            print_tree(child, depth + 1, is_last_child, max_d)
    
    # 打印树
    if 'children' in data:
        for root in data['children']:
            print_tree(root, 0, True)
    
    print("=" * 100 + "\n")

def print_depth_layers(tree_path):
    """按层级打印所有元素"""
    
    with open(tree_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\n" + "=" * 100)
    print("📊 按深度分层显示所有 UI 元素")
    print("=" * 100)
    
    elements_by_depth = defaultdict(list)
    
    def traverse(node, depth=0):
        """遍历并分组"""
        attrs = node.get('attributes', {})
        class_name = attrs.get('class', 'Unknown').split('.')[-1]
        resource_id = attrs.get('resource-id', '')
        text = attrs.get('text', '')
        clickable = attrs.get('clickable', 'false')
        
        elements_by_depth[depth].append({
            'class': class_name,
            'resource_id': resource_id,
            'text': text[:50] if text else '(无文本)',
            'clickable': clickable == 'true'
        })
        
        for child in node.get('children', []):
            traverse(child, depth + 1)
    
    if 'children' in data:
        for root in data['children']:
            traverse(root, 1)
    
    # 打印结果
    for depth in sorted(elements_by_depth.keys()):
        elements = elements_by_depth[depth]
        print(f"\n【 深度 {depth} 】- 共 {len(elements)} 个元素:")
        print("-" * 100)
        
        for i, elem in enumerate(elements, 1):
            marker = "🖱️ " if elem['clickable'] else "  "
            
            # 格式化输出
            class_str = f"{elem['class']:20s}"
            id_str = elem['resource_id'].split('/')[-1][:30] if elem['resource_id'] else "(无ID)"
            text_str = elem['text'][:40]
            
            print(f"{marker}{i:3d}. {class_str} | {id_str:30s} | {text_str}")

def print_leaf_analysis(tree_path):
    """分析所有叶子节点(底层元素)"""
    
    with open(tree_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\n" + "=" * 100)
    print("🍃 底层元素分析 (叶子节点 - 没有子元素的最终 UI 组件)")
    print("=" * 100)
    
    leaves = []
    
    def traverse(node, depth=0, path=[]):
        """遍历找叶子节点"""
        attrs = node.get('attributes', {})
        children = node.get('children', [])
        
        current_path = path + [attrs.get('resource-id', '?')]
        
        if not children:  # 这是叶子节点
            leaves.append({
                'depth': depth,
                'class': attrs.get('class', 'Unknown').split('.')[-1],
                'resource_id': attrs.get('resource-id', ''),
                'text': attrs.get('text', ''),
                'clickable': attrs.get('clickable', 'false'),
                'path': ' > '.join([p if p != '?' else '?' for p in current_path])
            })
        else:
            for child in children:
                traverse(child, depth + 1, current_path)
    
    if 'children' in data:
        for root in data['children']:
            traverse(root, 1)
    
    print(f"\n📈 总共 {len(leaves)} 个底层元素\n")
    
    # 按类型分类
    by_type = defaultdict(list)
    for leaf in leaves:
        by_type[leaf['class']].append(leaf)
    
    # 打印各类型的底层元素
    for class_type in sorted(by_type.keys()):
        items = by_type[class_type]
        print(f"\n【 {class_type} 】- {len(items)} 个:")
        print("-" * 100)
        
        for i, leaf in enumerate(items[:10], 1):  # 只显示前10个
            marker = "🖱️ " if leaf['clickable'] == 'true' else "  "
            text_short = leaf['text'][:50] if leaf['text'] else '(空)'
            print(f"{marker}{i:2d}. [深度{leaf['depth']}] {leaf['resource_id']:40s} | {text_short}")
        
        if len(items) > 10:
            print(f"    ... 还有 {len(items) - 10} 个 {class_type} 底层元素")

if __name__ == '__main__':
    tree_path = '/Users/atan/Desktop/work/vscode_debug/ad-cli/starbucks_ui_tree.json'
    
    # 可视化前15层
    visualize_ui_hierarchy(tree_path, max_depth=15)
    
    # 按深度打印
    print_depth_layers(tree_path)
    
    # 分析叶子节点
    print_leaf_analysis(tree_path)
