#!/usr/bin/env python3
"""
策略自动选择器
读取当日大盘复盘报告中的盘面信号，映射到具体策略
"""
import os
import re
from pathlib import Path
from datetime import datetime, timedelta

def parse_market_signal(report_path):
    if not os.path.exists(report_path):
        return {'score': 50, 'label': '未知', 'sentiment': 'neutral'}
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = r'盘面信号[：:]\s*(\d+)\s*/\s*100\s*[（(]\s*([^）)]+)\s*[）)]'
    match = re.search(pattern, content)
    if match:
        score = int(match.group(1))
        label = match.group(2).strip()
        if '进攻' in label or '强势' in label or '乐观' in label:
            sentiment = 'bullish'
        elif '防守' in label or '谨慎' in label or '悲观' in label or '退潮' in label:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'
        return {'score': score, 'label': label, 'sentiment': sentiment}
    return {'score': 50, 'label': '未识别', 'sentiment': 'neutral'}

def get_strategy_by_market(signal):
    score = signal['score']
    if score >= 70:
        return 'momentum_trend'
    elif score >= 50:
        return 'balanced_alpha'
    elif score >= 30:
        return 'value_defensive'
    else:
        return 'oversold_rebound'

def main():
    work_dir = os.environ.get('WORK_DIR', '/home/runner/work/quant-workspace')
    date_str = datetime.now().strftime('%Y%m%d')
    report_path = Path(work_dir) / 'daily_stock_analysis' / 'reports' / f'market_review_{date_str}.md'
    if not report_path.exists():
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        report_path = Path(work_dir) / 'daily_stock_analysis' / 'reports' / f'market_review_{yesterday}.md'
    if not report_path.exists():
        selected = 'balanced_alpha'
        score = 50
        sentiment = 'neutral'
    else:
        signal = parse_market_signal(str(report_path))
        selected = get_strategy_by_market(signal)
        score = signal['score']
        sentiment = signal['sentiment']
    with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
        f.write(f"selected_strategy={selected}\n")
        f.write(f"market_score={score}\n")
        f.write(f"market_sentiment={sentiment}\n")
    print(f"📊 市场信号: 评分={score}, 情绪={sentiment}")
    print(f"🎯 选定策略: {selected}")

if __name__ == "__main__":
    main()