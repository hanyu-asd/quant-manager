#!/usr/bin/env python3
"""
策略自动选择器
读取当日大盘复盘报告中的盘面信号，映射到具体策略
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta

def parse_market_signal(report_path):
    """从市场复盘报告中解析盘面信号"""
    if not os.path.exists(report_path):
        print(f"警告: 复盘报告不存在 {report_path}")
        return {'score': 50, 'label': '未知', 'sentiment': 'neutral'}
    
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取盘面信号: "盘面信号：67/100（偏暖，可进攻）"
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
    
    # 备选模式
    pattern2 = r'(\d+)\s*分'
    match2 = re.search(pattern2, content)
    if match2:
        score = int(match2.group(1))
        sentiment = 'bullish' if score >= 60 else 'bearish' if score < 40 else 'neutral'
        return {'score': score, 'label': f'{score}分', 'sentiment': sentiment}
    
    # 默认
    return {'score': 50, 'label': '未识别', 'sentiment': 'neutral'}

def get_strategy_by_market(signal):
    """根据市场信号选择策略"""
    score = signal['score']
    sentiment = signal['sentiment']
    
    if score >= 70:
        return 'momentum_trend'
    elif score >= 50:
        return 'balanced_alpha'
    elif score >= 30:
        return 'value_defensive'
    else:
        return 'oversold_rebound'

def load_strategy_performance(perf_file):
    """加载策略历史绩效"""
    if not os.path.exists(perf_file):
        return {}
    with open(perf_file, 'r') as f:
        return json.load(f)

def main():
    work_dir = os.environ.get('WORK_DIR', '/home/runner/work/quant-workspace')
    # 当日报告
    date_str = datetime.now().strftime('%Y%m%d')
    report_path = Path(work_dir) / 'daily_stock_analysis' / 'reports' / f'market_review_{date_str}.md'
    
    # 若当日报告不存在，回退到昨日（极少发生）
    if not report_path.exists():
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        report_path = Path(work_dir) / 'daily_stock_analysis' / 'reports' / f'market_review_{yesterday}.md'
        if not report_path.exists():
            print("错误：找不到任何复盘报告")
            selected = 'balanced_alpha'
            score = 50
            sentiment = 'neutral'
        else:
            signal = parse_market_signal(str(report_path))
            selected = get_strategy_by_market(signal)
            score = signal['score']
            sentiment = signal['sentiment']
    else:
        signal = parse_market_signal(str(report_path))
        selected = get_strategy_by_market(signal)
        score = signal['score']
        sentiment = signal['sentiment']
    
    # 输出到 GitHub Actions
    with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
        f.write(f"selected_strategy={selected}\n")
        f.write(f"market_score={score}\n")
        f.write(f"market_sentiment={sentiment}\n")
    
    print(f"📊 市场信号: 评分={score}, 情绪={sentiment}")
    print(f"🎯 选定策略: {selected}")
    print("=" * 50)

if __name__ == "__main__":
    main()