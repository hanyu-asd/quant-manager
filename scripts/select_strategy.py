#!/usr/bin/env python3
import os
import re
from pathlib import Path
from datetime import datetime, timedelta

def parse_market_signal(report_path):
    if not os.path.exists(report_path):
        return {'score': 50, 'sentiment': 'neutral'}
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'盘面信号[：:]\s*(\d+)\s*/\s*100\s*[（(]\s*([^）)]+)\s*[）)]', content)
    if match:
        score = int(match.group(1))
        label = match.group(2).strip()
        sentiment = 'bullish' if '进攻' in label or '强势' in label else 'bearish' if '防守' in label or '谨慎' in label else 'neutral'
        return {'score': score, 'sentiment': sentiment}
    return {'score': 50, 'sentiment': 'neutral'}

def get_strategy(signal):
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
    if report_path.exists():
        signal = parse_market_signal(str(report_path))
        selected = get_strategy(signal)
        score = signal['score']
    else:
        selected = 'balanced_alpha'
        score = 50
    with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
        f.write(f"selected_strategy={selected}\n")
        f.write(f"market_score={score}\n")
    print(f"📊 市场评分: {score} → 策略: {selected}")

if __name__ == "__main__":
    main()