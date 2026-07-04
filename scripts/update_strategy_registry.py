#!/usr/bin/env python3
"""
更新策略注册表 - 回写回测绩效
如果回测失败，将策略状态设为 monitor 并记录原因
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

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
    """从回测报告中提取绩效指标和状态"""
    metrics_file = Path(WORK_DIR) / 'alphaevo' / 'data' / 'backtest_summary.json'
    if not metrics_file.exists():
        print(f"⚠️ 未找到绩效文件，使用保守默认值并标记失败")
        return {
            'sharpe_ratio': 0.2,
            'win_rate': 0.4,
            'max_drawdown': 0.25,
            'total_return': -0.05,
            'avg_return': -0.01,
            'backtest_status': 'failed'
        }
    with open(metrics_file, 'r') as f:
        data = json.load(f)
    # 确保状态字段存在
    if 'backtest_status' not in data:
        data['backtest_status'] = 'success'
    return data

def evaluate_strategy_status(strategy, metrics):
    """根据绩效和状态评估策略状态"""
    status = metrics.get('backtest_status', 'success')
    if status == 'failed':
        return 'monitor', "回测失败，可能数据源不可用或策略配置异常"

    sharpe = metrics.get('sharpe_ratio', 0)
    win_rate = metrics.get('win_rate', 0)
    max_dd = metrics.get('max_drawdown', 0)

    if sharpe > 1.5 and win_rate > 0.6 and max_dd < 0.10:
        return 'active', None
    elif sharpe < 0.3 or win_rate < 0.4 or max_dd > 0.25:
        return 'retired', f"绩效恶化: 夏普={sharpe}, 胜率={win_rate}, 回撤={max_dd}"
    elif sharpe < 0.5 or max_dd > 0.15:
        return 'monitor', f"绩效下滑: 夏普={sharpe}, 回撤={max_dd}"
    else:
        return 'active', None

def main():
    if not STRATEGY_ID:
        print("⚠️ 未指定策略ID，跳过注册表更新")
        return

    registry = load_registry()
    strategy = next((s for s in registry['strategies'] if s['id'] == STRATEGY_ID), None)
    if not strategy:
        print(f"⚠️ 策略 {STRATEGY_ID} 不在注册表中")
        return

    metrics = get_backtest_metrics(STRATEGY_ID)
    if not metrics:
        print(f"⚠️ 无法获取绩效，使用保守默认值")
        metrics = {'sharpe_ratio': 0.2, 'win_rate': 0.4, 'max_drawdown': 0.25, 'total_return': -0.05, 'backtest_status': 'failed'}

    # 更新绩效字段
    strategy['sharpe_ratio'] = metrics.get('sharpe_ratio', 0.2)
    strategy['win_rate'] = metrics.get('win_rate', 0.4)
    strategy['max_drawdown'] = metrics.get('max_drawdown', 0.25)
    strategy['last_evaluated'] = datetime.now().strftime('%Y-%m-%d')

    # 更新绩效趋势
    if 'performance_trend' not in strategy:
        strategy['performance_trend'] = []
    trend_value = metrics.get('total_return', -0.05)
    strategy['performance_trend'].append(trend_value)
    if len(strategy['performance_trend']) > 30:
        strategy['performance_trend'] = strategy['performance_trend'][-30:]

    # 评估状态
    new_status, reason = evaluate_strategy_status(strategy, metrics)
    if new_status != strategy['status']:
        print(f"🔄 策略 {STRATEGY_ID} 状态变更: {strategy['status']} → {new_status}")
        if reason:
            strategy['retire_reason'] = reason
            # 如果是回测失败导致的 monitor，记录失败原因
            if metrics.get('backtest_status') == 'failed':
                strategy['retire_reason'] = "回测失败 (可能数据源不可用)"
        strategy['status'] = new_status

    save_registry(registry)
    print(f"✅ 策略注册表已更新: {STRATEGY_ID}")

if __name__ == '__main__':
    main()