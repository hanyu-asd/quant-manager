#!/usr/bin/env python3
"""
从 AlphaSift 选股结果生成 AlphaEvo 策略 YAML 文件
"""
import sys
import os
import csv
import yaml
import argparse
from pathlib import Path

def load_stock_pool(csv_path):
    """读取 stock_pool.csv，返回股票代码列表"""
    codes = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'code' in row:
                codes.append(row['code'])
            elif 'symbol' in row:
                codes.append(row['symbol'])
    return codes

def generate_strategy_yaml(stock_codes, output_path):
    """生成包含指定股票池的 RSI 策略 YAML"""
    # 基础策略模板（可参考 AlphaEvo 官方示例）
    strategy = {
        "id": "custom_alpha_sift_strategy",
        "name": "AlphaSift 选股策略回测",
        "description": "对 AlphaSift 选出的股票进行 RSI 策略回测",
        "parameters": {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10
        },
        "symbols": stock_codes,  # 动态注入股票列表
        "start_date": "2025-01-01",  # 可根据需要调整
        "end_date": None  # 默认为最新交易日
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(strategy, f, allow_unicode=True, sort_keys=False)
    print(f"✅ 生成策略 YAML: {output_path} (包含 {len(stock_codes)} 只股票)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stock-csv', required=True, help='AlphaSift 输出的 CSV 文件路径')
    parser.add_argument('--output', required=True, help='输出 YAML 文件路径')
    args = parser.parse_args()

    stock_codes = load_stock_pool(args.stock_csv)
    if not stock_codes:
        print("⚠️ 未找到股票代码，退出")
        sys.exit(1)
    generate_strategy_yaml(stock_codes, args.output)

if __name__ == '__main__':
    main()