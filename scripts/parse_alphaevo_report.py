#!/usr/bin/env python3
"""
解析 AlphaEvo 回测报告，提取绩效指标
"""
import os
import sys
import json
import re
from pathlib import Path

WORK_DIR = os.environ.get('WORK_DIR', '.')
STRATEGY_ID = os.environ.get('STRATEGY_ID', '')

def find_latest_report():
    """查找最新的回测报告"""
    reports_dir = Path(WORK_DIR) / 'alphaevo' / 'reports'
    if not reports_dir.exists():
        return None
    # 查找 *_report.md 文件
    reports = list(reports_dir.glob('*_report.md'))
    if not reports:
        return None
    # 按修改时间排序
    reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0]

def parse_report(report_path):
    """解析报告，提取指标"""
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    metrics = {}
    # 匹配表格中的 Metric 和 Value
    # 例如: │ Win Rate         │  50.0% │
    pattern = r'│\s*([^│]+?)\s*│\s*([^│]+?)\s*│'
    matches = re.findall(pattern, content)
    for key, value in matches:
        key = key.strip()
        value = value.strip()
        # 转换为数字
        try:
            if value.endswith('%'):
                metrics[key] = float(value.rstrip('%')) / 100
            else:
                # 尝试直接转换
                metrics[key] = float(value)
        except ValueError:
            pass  # 保留字符串

    # 标准化字段名
    mapping = {
        'Win Rate': 'win_rate',
        'Avg Return': 'avg_return',
        'P/L Ratio': 'pl_ratio',
        'Max Drawdown': 'max_drawdown',
        'Sharpe Ratio': 'sharpe_ratio',
        'Total Signals': 'total_signals',
        'Avg Holding Days': 'avg_holding_days',
        'Total Return': 'total_return',
        'Confidence Score': 'confidence_score'
    }
    standardized = {}
    for k, v in metrics.items():
        new_key = mapping.get(k, k)
        standardized[new_key] = v

    return standardized

def main():
    report_path = find_latest_report()
    if not report_path:
        print("⚠️ 未找到回测报告")
        sys.exit(0)

    print(f"📄 解析报告: {report_path}")
    metrics = parse_report(report_path)
    if not metrics:
        print("⚠️ 未能提取绩效指标")
        sys.exit(0)

    # 保存为 JSON
    output_dir = Path(WORK_DIR) / 'alphaevo' / 'data'
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / 'backtest_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"✅ 绩效指标已保存到: {summary_path}")
    for k, v in metrics.items():
        print(f"   {k}: {v}")

if __name__ == '__main__':
    main()