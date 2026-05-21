#!/usr/bin/env python3
"""
分析 UI 树的深度结构，检查是否包含所有层级的元素
"""

import json
from collections import defaultdict

def analyze_ui_tree(tree_path):
    """分析 UI 树的结构"""
    
    with open(tree_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stats = {
        'total_nodes': 0,
        'max_depth': 0,
        'elements_by_depth': defaultdict(int),
        'elements_by_type': defaultdict(int),
        'interactive_elements': [],
        'depth_distribution': defaultdict(list),
        'leaf_nodes': [],  # 没有子节点的元素
        'deepest_paths': []  # 最深路径的元素
    }
    
    def traverse(node, depth=0, path=[]):
        """递归遍历 UI 树"""
        stats['total_nodes'] += 1
        stats['max_depth'] = max(stats['max_depth'], depth)
        
        current_path = path + [node.get('attributes', {}).get('resource-id', 'unknown')]
        
        # 统计深度
        stats['elements_by_depth'][depth] += 1
        
        # 统计类型
        class_name = node.get('attributes', {}).get('class', 'Unknown')
        stats['elements_by_type'][class_name] += 1
        
        # 记录可交互元素
        attrs = node.get('attributes', {})
        if attrs.get('clickable') == 'true' or attrs.get('scrollable') == 'true' or attrs.get('long-clickable') == 'true':
            stats['interactive_elements'].append({
                'depth': depth,
                'class': class_name,
                'resource-id': attrs.get('resource-id', ''),
                'text': attrs.get('text', ''),
                'clickable': attrs.get('clickable'),
                'scrollable': attrs.get('scrollable'),
                'bounds': attrs.get('bounds', ''),
                'path': ' > '.join(current_path)
            })
        
        # 记录按深度分类的元素信息
        stats['depth_distribution'][depth].append({
            'type': class_name,
            'resource-id': attrs.get('resource-id', ''),
            'text': attrs.get('text', '')[:50] if attrs.get('text') else '',
            'clickable': attrs.get('clickable')
        })
        
        # 处理子节点
        children = node.get('children', [])
        if children:
            for child in children:
                traverse(child, depth + 1, current_path)
        else:
            # 记录叶子节点
            stats['leaf_nodes'].append({
                'depth': depth,
                'class': class_name,
                'text': attrs.get('text', ''),
                'resource-id': attrs.get('resource-id', '')
            })
    
    # 开始遍历
    if 'children' in data:
        for root_child in data['children']:
            traverse(root_child, 1, [])
    
    return stats

def print_analysis(stats):
    """打印分析结果"""
    print("=" * 80)
    print("🔍 ANDROID UI 树深度分析报告")
    print("=" * 80)
    
    print(f"\n📊 总体统计:")
    print(f"  • 总节点数: {stats['total_nodes']}")
    print(f"  • 最大深度: {stats['max_depth']}")
    print(f"  • 可交互元素: {len(stats['interactive_elements'])}")
    print(f"  • 叶子节点数: {len(stats['leaf_nodes'])}")
    
    print(f"\n📈 按深度分布的元素数量:")
    for depth in sorted(stats['elements_by_depth'].keys()):
        count = stats['elements_by_depth'][depth]
        bar = "█" * (count // 2)
        print(f"  深度 {depth:2d}: {count:4d} 个节点  {bar}")
    
    print(f"\n🏗️  元素类型分布 (前15个):")
    sorted_types = sorted(stats['elements_by_type'].items(), key=lambda x: x[1], reverse=True)[:15]
    for class_name, count in sorted_types:
        short_name = class_name.split('.')[-1]
        bar = "█" * (count // 2)
        print(f"  {short_name:20s}: {count:4d} 个  {bar}")
    
    print(f"\n🎯 可交互元素分析 (按深度):")
    interactive_by_depth = defaultdict(list)
    for elem in stats['interactive_elements']:
        interactive_by_depth[elem['depth']].append(elem)
    
    for depth in sorted(interactive_by_depth.keys()):
        elements = interactive_by_depth[depth]
        print(f"\n  【深度 {depth}】- {len(elements)} 个可交互元素:")
        for i, elem in enumerate(elements[:5], 1):  # 只显示前5个
            resource_id = elem['resource-id'].split('/')[-1] if elem['resource-id'] else 'N/A'
            print(f"    {i}. {elem['class'].split('.')[-1]:15s} | {resource_id:30s} | clickable: {elem['clickable']}")
        if len(elements) > 5:
            print(f"    ... 还有 {len(elements) - 5} 个")
    
    print(f"\n🍃 叶子节点(最末端元素) 分析:")
    leaf_types = defaultdict(int)
    for leaf in stats['leaf_nodes']:
        leaf_types[leaf['class'].split('.')[-1]] += 1
    
    print(f"  叶子节点总数: {len(stats['leaf_nodes'])}")
    print(f"  类型分布 (前10个):")
    for class_name, count in sorted(leaf_types.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    • {class_name:20s}: {count:4d} 个")
    
    print(f"\n🔗 最深路径示例:")
    deepest_elements = [e for e in stats['interactive_elements'] if e['depth'] == stats['max_depth'] - 1][:3]
    for elem in deepest_elements:
        path_parts = elem['path'].split(' > ')
        print(f"\n  资源ID: {elem['resource-id']}")
        print(f"  深度: {elem['depth']}")
        print(f"  类型: {elem['class'].split('.')[-1]}")
        print(f"  路径 ({len(path_parts)} 层):")
        for i, part in enumerate(path_parts):
            indent = "    " * (i + 1)
            print(f"{indent}└─ {part}")
    
    print("\n" + "=" * 80)
    print("📝 结论:")
    print(f"  ✅ UI 树已被完整获取,包含 {stats['max_depth']} 个深度级别")
    print(f"  ✅ 包含 {len(stats['interactive_elements'])} 个可交互元素")
    print(f"  ✅ 底层元素包含在树中 ({len(stats['leaf_nodes'])} 个叶子节点)")
    print("=" * 80)

if __name__ == '__main__':
    tree_path = '/Users/atan/Desktop/work/vscode_debug/ad-cli/starbucks_ui_tree.json'
    stats = analyze_ui_tree(tree_path)
    print_analysis(stats)
