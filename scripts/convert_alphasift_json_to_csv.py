#!/usr/bin/env python3
"""
将 AlphaSift 输出的 JSON 选股结果转换为 CSV 格式
用法: python convert_alphasift_json_to_csv.py <json_file> <output_csv>
如果 json_file 为目录，则自动选取最新的 JSON 文件
"""

import json
import csv
import sys
import os
import glob
from pathlib import Path

def get_latest_json(directory):
    """获取指定目录下最新的 JSON 文件"""
    json_files = glob.glob(os.path.join(directory, "*.json"))
    if not json_files:
        return None
    latest = max(json_files, key=os.path.getctime)
    return latest

def convert_json_to_csv(json_path, csv_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    picks = data.get('picks', [])
    if not picks:
        print("警告: JSON 中没有选股结果")
        return False
    
    # 提取需要的字段
    rows = []
    for item in picks:
        rows.append({
            'code': item.get('code', ''),
            'name': item.get('name', ''),
            'final_score': item.get('final_score', 0),
            'price': item.get('price', 0),
            'change_pct': item.get('change_pct', 0),
            'pe_ratio': item.get('pe_ratio', 0),
            'pb_ratio': item.get('pb_ratio', 0),
            'turnover_rate': item.get('turnover_rate', 0),
            'amount': item.get('amount', 0),
            'total_mv': item.get('total_mv', 0),
        })
    
    # 写入 CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"成功转换 {len(rows)} 条选股结果到 {csv_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python convert_alphasift_json_to_csv.py <json_file_or_directory> [output_csv]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "stock_pool.csv"
    
    if os.path.isdir(input_path):
        json_file = get_latest_json(input_path)
        if not json_file:
            print(f"错误: 在 {input_path} 中未找到 JSON 文件")
            sys.exit(1)
        print(f"使用最新 JSON: {json_file}")
    else:
        json_file = input_path
    
    success = convert_json_to_csv(json_file, output_csv)
    sys.exit(0 if success else 1)