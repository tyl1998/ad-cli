#!/usr/bin/env python3
"""
实时清洗 ADB 获取的 UI 数据，展示可获取的信息空间
"""

import xml.etree.ElementTree as ET
from datetime import datetime
import json
from collections import defaultdict

def parse_bounds(bounds_str):
    """解析坐标字符串 [x1,y1][x2,y2]"""
    import re
    match = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
    if match and len(match) == 2:
        x1, y1 = int(match[0][0]), int(match[0][1])
        x2, y2 = int(match[1][0]), int(match[1][1])
        width = x2 - x1
        height = y2 - y1
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        return {
            'raw': bounds_str,
            'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
            'width': width, 'height': height,
            'center': [center_x, center_y],
            'area': width * height
        }
    return None

def get_element_label(node):
    """为元素生成易读的标签"""
    text = node.get('text', '')
    resource_id = node.get('resource-id', '')
    content_desc = node.get('content-desc', '')
    class_name = node.get('class', '').split('.')[-1]
    
    label_parts = [class_name]
    
    if text:
        label_parts.append(f'"{text[:20]}"')
    if resource_id:
        label_parts.append(f'[{resource_id.split("/")[-1]}]')
    if content_desc:
        label_parts.append(f'({content_desc[:15]})')
    
    return ' '.join(label_parts)

def analyze_ui_xml(xml_path):
    """深度分析 UI XML，展示所有可获取的信息"""
    
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # 数据结构
    data = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'source': xml_path,
        },
        'statistics': {
            'total_elements': 0,
            'visible_elements': 0,
            'clickable_elements': 0,
            'scrollable_elements': 0,
            'with_text': 0,
            'with_resource_id': 0,
            'with_content_desc': 0,
            'max_depth': 0,
        },
        'categories': {
            'interactive': [],      # 可交互元素
            'content': [],          # 内容元素（有文字）
            'images': [],           # 图片
            'inputs': [],           # 输入框
            'lists': [],            # 列表/滚动容器
            'buttons': [],          # 按钮
            'navigation': [],       # 导航元素
        },
        'spatial_map': {},         # 空间位置映射
        'element_types': defaultdict(int),
        'packages': set(),
        'all_texts': [],           # 所有文本内容
        'all_resource_ids': [],    # 所有资源ID
    }
    
    def traverse(node, depth=0):
        """遍历节点"""
        data['statistics']['total_elements'] += 1
        data['statistics']['max_depth'] = max(data['statistics']['max_depth'], depth)
        
        # 基本属性
        attrs = {
            'class': node.get('class', ''),
            'package': node.get('package', ''),
            'text': node.get('text', ''),
            'resource-id': node.get('resource-id', ''),
            'content-desc': node.get('content-desc', ''),
            'clickable': node.get('clickable') == 'true',
            'long-clickable': node.get('long-clickable') == 'true',
            'scrollable': node.get('scrollable') == 'true',
            'checkable': node.get('checkable') == 'true',
            'enabled': node.get('enabled') == 'true',
            'focused': node.get('focused') == 'true',
            'selected': node.get('selected') == 'true',
            'bounds': node.get('bounds', ''),
            'depth': depth
        }
        
        # 解析位置
        bounds_info = parse_bounds(attrs['bounds'])
        if bounds_info:
            attrs['position'] = bounds_info
            # 判断是否可见
            if bounds_info['width'] > 0 and bounds_info['height'] > 0:
                data['statistics']['visible_elements'] += 1
        
        # 统计
        class_name = attrs['class'].split('.')[-1]
        data['element_types'][class_name] += 1
        
        if attrs['package']:
            data['packages'].add(attrs['package'])
        
        if attrs['text']:
            data['statistics']['with_text'] += 1
            data['all_texts'].append(attrs['text'])
        
        if attrs['resource-id']:
            data['statistics']['with_resource_id'] += 1
            data['all_resource_ids'].append(attrs['resource-id'])
        
        if attrs['content-desc']:
            data['statistics']['with_content_desc'] += 1
        
        # 分类元素
        label = get_element_label(node)
        
        # 可交互元素
        if attrs['clickable'] or attrs['long-clickable']:
            data['statistics']['clickable_elements'] += 1
            data['categories']['interactive'].append({
                'label': label,
                'type': class_name,
                'text': attrs['text'],
                'resource_id': attrs['resource-id'],
                'bounds': attrs['bounds'],
                'depth': depth,
                'clickable': attrs['clickable'],
                'long_clickable': attrs['long-clickable'],
            })
        
        # 滚动容器
        if attrs['scrollable']:
            data['statistics']['scrollable_elements'] += 1
            data['categories']['lists'].append({
                'label': label,
                'type': class_name,
                'resource_id': attrs['resource-id'],
                'bounds': attrs['bounds'],
                'depth': depth,
            })
        
        # 有文本内容的元素
        if attrs['text'] and len(attrs['text']) > 0:
            data['categories']['content'].append({
                'label': label,
                'text': attrs['text'],
                'resource_id': attrs['resource-id'],
                'bounds': attrs['bounds'],
                'depth': depth,
            })
        
        # 按钮识别
        if 'Button' in class_name or (attrs['clickable'] and attrs['text']):
            data['categories']['buttons'].append({
                'label': label,
                'text': attrs['text'],
                'resource_id': attrs['resource-id'],
                'bounds': attrs['bounds'],
                'depth': depth,
            })
        
        # 图片
        if 'Image' in class_name:
            data['categories']['images'].append({
                'label': label,
                'resource_id': attrs['resource-id'],
                'content_desc': attrs['content-desc'],
                'bounds': attrs['bounds'],
                'depth': depth,
            })
        
        # 输入框
        if 'Edit' in class_name:
            data['categories']['inputs'].append({
                'label': label,
                'text': attrs['text'],
                'resource_id': attrs['resource-id'],
                'bounds': attrs['bounds'],
                'depth': depth,
            })
        
        # 递归子节点
        for child in node:
            traverse(child, depth + 1)
    
    # 开始遍历
    traverse(root)
    
    return data

def print_analysis(data):
    """打印详细分析"""
    
    print("\n" + "=" * 100)
    print("📱 实时 UI 控件获取分析 - 信息空间展示")
    print("=" * 100)
    
    stats = data['statistics']
    
    print(f"\n📊 基础统计:")
    print(f"  ├─ 总元素数:        {stats['total_elements']}")
    print(f"  ├─ 可见元素:        {stats['visible_elements']}")
    print(f"  ├─ 可交互元素:      {stats['clickable_elements']}")
    print(f"  ├─ 可滚动容器:      {stats['scrollable_elements']}")
    print(f"  ├─ 包含文本:        {stats['with_text']}")
    print(f"  ├─ 有资源ID:        {stats['with_resource_id']}")
    print(f"  ├─ 有无障碍描述:    {stats['with_content_desc']}")
    print(f"  └─ 最大嵌套深度:    {stats['max_depth']}")
    
    print(f"\n🏗️  元素类型分布 (前20个):")
    sorted_types = sorted(data['element_types'].items(), key=lambda x: x[1], reverse=True)[:20]
    for class_name, count in sorted_types:
        bar = "█" * (count // 2)
        print(f"  {class_name:25s} {count:4d} 个  {bar}")
    
    print(f"\n📦 应用包名:")
    for pkg in sorted(data['packages']):
        print(f"  • {pkg}")
    
    # 可交互元素
    interactive = data['categories']['interactive']
    print(f"\n🖱️  可交互元素 ({len(interactive)} 个):")
    for i, elem in enumerate(interactive[:15], 1):
        text_display = f'"{elem["text"][:20]}"' if elem['text'] else '(无文本)'
        id_display = elem['resource_id'].split('/')[-1] if elem['resource_id'] else '(无ID)'
        print(f"  {i:2d}. {elem['type']:20s} {text_display:25s} [{id_display}]")
    if len(interactive) > 15:
        print(f"      ... 还有 {len(interactive) - 15} 个")
    
    # 文本内容
    content = data['categories']['content']
    print(f"\n📝 文本内容元素 ({len(content)} 个):")
    for i, elem in enumerate(content[:20], 1):
        text = elem['text'][:40] + '...' if len(elem['text']) > 40 else elem['text']
        print(f"  {i:2d}. {text}")
    if len(content) > 20:
        print(f"      ... 还有 {len(content) - 20} 个")
    
    # 按钮
    buttons = data['categories']['buttons']
    print(f"\n🔘 按钮元素 ({len(buttons)} 个):")
    for i, btn in enumerate(buttons[:10], 1):
        text = btn['text'] if btn['text'] else '(无文本)'
        id_display = btn['resource_id'].split('/')[-1] if btn['resource_id'] else '(无ID)'
        print(f"  {i:2d}. {text:30s} [{id_display}]")
    if len(buttons) > 10:
        print(f"      ... 还有 {len(buttons) - 10} 个")
    
    # 图片
    images = data['categories']['images']
    print(f"\n🖼️  图片元素 ({len(images)} 个):")
    for i, img in enumerate(images[:10], 1):
        id_display = img['resource_id'].split('/')[-1] if img['resource_id'] else '(无ID)'
        desc = img['content_desc'][:20] if img['content_desc'] else '(无描述)'
        print(f"  {i:2d}. {id_display:30s} {desc}")
    if len(images) > 10:
        print(f"      ... 还有 {len(images) - 10} 个")
    
    # 滚动容器
    lists = data['categories']['lists']
    if lists:
        print(f"\n📜 滚动容器 ({len(lists)} 个):")
        for i, lst in enumerate(lists, 1):
            print(f"  {i}. {lst['label']}")
    
    # 输入框
    inputs = data['categories']['inputs']
    if inputs:
        print(f"\n⌨️  输入框 ({len(inputs)} 个):")
        for i, inp in enumerate(inputs, 1):
            print(f"  {i}. {inp['label']}")
    
    # 所有唯一文本
    unique_texts = list(set([t for t in data['all_texts'] if t.strip()]))
    print(f"\n💬 所有唯一文本 ({len(unique_texts)} 个):")
    for i, text in enumerate(sorted(unique_texts)[:30], 1):
        display_text = text[:50] + '...' if len(text) > 50 else text
        print(f"  {i:2d}. {display_text}")
    if len(unique_texts) > 30:
        print(f"      ... 还有 {len(unique_texts) - 30} 个")
    
    print("\n" + "=" * 100)
    print("✅ 数据获取完成")
    print("=" * 100)

def save_cleaned_data(data, output_path):
    """保存清洗后的数据"""
    # 转换 set 为 list
    data['packages'] = sorted(list(data['packages']))
    data['element_types'] = dict(data['element_types'])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 清洗后的数据已保存到: {output_path}")

if __name__ == '__main__':
    xml_path = '/Users/atan/Desktop/work/vscode_debug/ad-cli/current_ui.xml'
    output_path = '/Users/atan/Desktop/work/vscode_debug/ad-cli/current_ui_cleaned.json'
    
    print("🔄 正在分析 UI 数据...")
    data = analyze_ui_xml(xml_path)
    
    print_analysis(data)
    
    save_cleaned_data(data, output_path)
