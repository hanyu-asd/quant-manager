#!/usr/bin/env python3
import json
import csv
import sys
import os
import glob

def get_latest_json(directory):
    files = glob.glob(os.path.join(directory, "*.json"))
    return max(files, key=os.path.getctime) if files else None

def convert(json_path, csv_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    picks = data.get('picks', [])
    if not picks:
        return False
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
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ 转换成功: {len(rows)} 条记录 → {csv_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python convert_alphasift_json_to_csv.py <json_file_or_dir> [output_csv]")
        sys.exit(1)
    input_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "stock_pool.csv"
    if os.path.isdir(input_path):
        json_file = get_latest_json(input_path)
        if not json_file:
            print("错误: 未找到 JSON 文件")
            sys.exit(1)
    else:
        json_file = input_path
    success = convert(json_file, output)
    sys.exit(0 if success else 1)