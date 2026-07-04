#!/usr/bin/env python3
"""
更新策略注册表 - 回写回测绩效
"""
import os
import sys
import json
from datetime import datetime

REGISTRY_PATH = os.environ.get('REGISTRY_PATH', 'strategy_registry.json')
STRATEGY_ID = os.environ.get('STRATEGY_ID', '')
WORK_DIR = os.environ.get('WORK_DIR', '.')

def load_registry():
    with open(REGISTRY_PATH, 'r') as f:
        return json.load(f)

def save_registry(registry):
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(registry, f, indent=2)

def get_backtest_metrics(strategy_id):
    """从回测报告中提取绩效指标（由 parse_alphaevo_report.py 生成）"""
    metrics_file = Path(WORK_DIR) / 'alphaevo' / 'data' / 'backtest_summary.json'
    if not metrics_file.exists():
        return None
    with open(metrics_file, 'r') as f:
        data = json.load(f)
    # 映射到标准字段
    return {
        'sharpe_ratio': data.get('Sharpe Ratio', 0),
        'win_rate': data.get('Win Rate', 0),
        'max_drawdown': data.get('Max Drawdown', 0),
        'total_return': data.get('Total Return', 0),
        'avg_return': data.get('Avg Return', 0)
    }

def evaluate_strategy_status(strategy, metrics):
    """根据绩效评估策略状态"""
    sharpe = metrics.get('sharpe_ratio', 0)
    win_rate = metrics.get('win_rate', 0)
    max_dd = metrics.get('max_drawdown', 0)

    # 阈值判断
    if sharpe > 1.5 and win_rate > 0.6 and max_dd < 0.10:
        return 'active'
    elif sharpe < 0.3 or win_rate < 0.4 or max_dd > 0.25:
        return 'retired'
    elif sharpe < 0.5 or max_dd > 0.15:
        return 'monitor'
    else:
        return 'active'

def main():
    if not STRATEGY_ID:
        print("⚠️ 未指定策略ID，跳过注册表更新")
        return

    registry = load_registry()
    # 查找策略
    strategy = next((s for s in registry['strategies'] if s['id'] == STRATEGY_ID), None)
    if not strategy:
        print(f"⚠️ 策略 {STRATEGY_ID} 不在注册表中")
        return

    # 获取最新回测绩效
    metrics = get_backtest_metrics(STRATEGY_ID)
    if not metrics:
        print(f"⚠️ 未找到回测绩效数据，跳过更新")
        return

    # 更新绩效字段
    strategy['sharpe_ratio'] = metrics['sharpe_ratio']
    strategy['win_rate'] = metrics['win_rate']
    strategy['max_drawdown'] = metrics['max_drawdown']
    strategy['last_evaluated'] = datetime.now().strftime('%Y-%m-%d')

    # 更新绩效趋势
    if 'performance_trend' not in strategy:
        strategy['performance_trend'] = []
    # 使用总收益率作为趋势指标
    trend_value = metrics.get('total_return', 0)
    strategy['performance_trend'].append(trend_value)
    if len(strategy['performance_trend']) > 30:
        strategy['performance_trend'] = strategy['performance_trend'][-30:]

    # 评估状态
    new_status = evaluate_strategy_status(strategy, metrics)
    if new_status != strategy['status']:
        print(f"🔄 策略 {STRATEGY_ID} 状态变更: {strategy['status']} → {new_status}")
        if new_status == 'retired':
            strategy['retire_reason'] = f"绩效恶化: 夏普={metrics['sharpe_ratio']}, 胜率={metrics['win_rate']}, 回撤={metrics['max_drawdown']}"
        strategy['status'] = new_status

    save_registry(registry)
    print(f"✅ 策略注册表已更新: {STRATEGY_ID}")

if __name__ == '__main__':
    from pathlib import Path
    main()