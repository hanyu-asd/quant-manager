#!/usr/bin/env python3
"""
策略选择器 V2
基于市场信号 + 策略注册表中的历史绩效选择最优策略
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

REGISTRY_PATH = os.environ.get('REGISTRY_PATH', 'strategy_registry.json')
WORK_DIR = os.environ.get('WORK_DIR', '.')

def get_market_signal():
    report_dir = Path(WORK_DIR) / 'daily_stock_analysis' / 'reports'
    today = datetime.now().strftime('%Y%m%d')
    report_path = report_dir / f'market_review_{today}.md'
    if not report_path.exists():
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        report_path = report_dir / f'market_review_{yesterday}.md'
        if not report_path.exists():
            return {'score': 50, 'sentiment': 'neutral'}
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
        return {'score': score, 'sentiment': sentiment}
    return {'score': 50, 'sentiment': 'neutral'}

def load_registry():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, 'r') as f:
            return json.load(f)
    else:
        # 默认注册表（首次运行）
        default = {
            "strategies": [
                {
                    "id": "momentum_trend",
                    "alpha_sift_strategy": "momentum_quality",
                    "alphaevo_strategy": "trend_following",
                    "status": "active",
                    "deployed_date": "2026-01-01",
                    "last_evaluated": None,
                    "sharpe_ratio": 0.8,
                    "win_rate": 0.58,
                    "max_drawdown": 0.12,
                    "performance_trend": [],
                    "evolution_count": 0,
                    "retire_reason": None
                },
                {
                    "id": "balanced_alpha",
                    "alpha_sift_strategy": "balanced_alpha",
                    "alphaevo_strategy": "rsi_reversion_v1",
                    "status": "active",
                    "deployed_date": "2026-01-01",
                    "last_evaluated": None,
                    "sharpe_ratio": 0.7,
                    "win_rate": 0.55,
                    "max_drawdown": 0.10,
                    "performance_trend": [],
                    "evolution_count": 0,
                    "retire_reason": None
                },
                {
                    "id": "value_defensive",
                    "alpha_sift_strategy": "value_defensive",
                    "alphaevo_strategy": "value_mean_reversion",
                    "status": "active",
                    "deployed_date": "2026-01-01",
                    "last_evaluated": None,
                    "sharpe_ratio": 0.6,
                    "win_rate": 0.52,
                    "max_drawdown": 0.08,
                    "performance_trend": [],
                    "evolution_count": 0,
                    "retire_reason": None
                },
                {
                    "id": "oversold_rebound",
                    "alpha_sift_strategy": "oversold_rebound",
                    "alphaevo_strategy": "oversold_reversal",
                    "status": "active",
                    "deployed_date": "2026-01-01",
                    "last_evaluated": None,
                    "sharpe_ratio": 0.5,
                    "win_rate": 0.50,
                    "max_drawdown": 0.15,
                    "performance_trend": [],
                    "evolution_count": 0,
                    "retire_reason": None
                }
            ]
        }
        with open(REGISTRY_PATH, 'w') as f:
            json.dump(default, f, indent=2)
        return default

def select_strategy(market_signal, registry):
    score = market_signal['score']
    sentiment = market_signal['sentiment']

    active_strategies = [s for s in registry['strategies'] if s['status'] != 'retired']
    if not active_strategies:
        return registry['strategies'][0]

    scored = []
    for s in active_strategies:
        # 基础分：市场匹配度
        base_score = 50
        if sentiment == 'bullish':
            if 'momentum' in s['id'] or 'trend' in s['id']:
                base_score = 70
            elif 'balanced' in s['id']:
                base_score = 60
            else:
                base_score = 40
        elif sentiment == 'bearish':
            if 'defensive' in s['id'] or 'value' in s['id'] or 'oversold' in s['id']:
                base_score = 70
            elif 'balanced' in s['id']:
                base_score = 60
            else:
                base_score = 40
        else:  # neutral
            if 'balanced' in s['id']:
                base_score = 70
            elif 'momentum' in s['id']:
                base_score = 60
            else:
                base_score = 50

        # 惩罚 monitor 状态（尤其是回测失败导致的）
        if s['status'] == 'monitor':
            # 检查是否有回测失败标记（可通过 retire_reason 包含 "回测失败" 判断）
            if s.get('retire_reason') and '回测失败' in s.get('retire_reason', ''):
                base_score -= 20  # 大幅降低优先级
            else:
                base_score -= 10

        # 加分项：绩效指标
        sharpe = s.get('sharpe_ratio', 0)
        win_rate = s.get('win_rate', 0)
        max_dd = s.get('max_drawdown', 0)

        if sharpe > 1.2:
            base_score += 10
        elif sharpe > 0.8:
            base_score += 5

        if win_rate > 0.6:
            base_score += 5
        elif win_rate > 0.55:
            base_score += 2

        if max_dd > 0.15:
            base_score -= 10
        elif max_dd > 0.12:
            base_score -= 5

        trend = s.get('performance_trend', [])
        if len(trend) >= 5:
            recent = trend[-5:]
            if all(x < 0 for x in recent):
                base_score -= 15

        scored.append((base_score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    return best

def main():
    market_signal = get_market_signal()
    registry = load_registry()
    selected = select_strategy(market_signal, registry)

    with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
        f.write(f"selected_strategy={selected['id']}\n")
        f.write(f"alpha_sift_strategy={selected['alpha_sift_strategy']}\n")
        f.write(f"alphaevo_strategy={selected['alphaevo_strategy']}\n")
        f.write(f"market_score={market_signal['score']}\n")
        f.write(f"market_sentiment={market_signal['sentiment']}\n")

    print(f"📊 市场信号: 评分={market_signal['score']}, 情绪={market_signal['sentiment']}")
    print(f"🎯 选定策略: {selected['id']} (评分: {selected.get('sharpe_ratio', 0)}夏普, {selected.get('win_rate', 0)}胜率)")
    print(f"   AlphaSift: {selected['alpha_sift_strategy']}")
    print(f"   AlphaEvo: {selected['alphaevo_strategy']}")
    if selected['status'] == 'monitor':
        print(f"   ⚠️ 策略处于 monitor 状态: {selected.get('retire_reason', '')}")

if __name__ == '__main__':
    main()