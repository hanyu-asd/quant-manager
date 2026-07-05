#!/usr/bin/env python3
"""
更新策略注册表：写入回测绩效，保留 factor_exposure
"""
import os
import json
from pathlib import Path

WORK_DIR = os.environ.get('WORK_DIR', '.')
REGISTRY_PATH = os.environ.get('REGISTRY_PATH', os.path.join(WORK_DIR, 'strategy_registry.json'))
STRATEGY_ID = os.environ.get('STRATEGY_ID', '')
BACKTEST_SUMMARY = os.path.join(WORK_DIR, 'alphaevo/data/backtest_summary.json')


def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return None


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    if not STRATEGY_ID:
        print("未指定 STRATEGY_ID，跳过更新")
        return

    registry = load_json(REGISTRY_PATH)
    if not registry:
        print("注册表加载失败")
        return

    strategies = registry.get('strategies', [])
    target = None
    for s in strategies:
        if s.get('id') == STRATEGY_ID:
            target = s
            break

    if not target:
        print(f"策略 {STRATEGY_ID} 未找到")
        return

    backtest = load_json(BACKTEST_SUMMARY)
    if not backtest:
        print("未找到回测摘要，跳过更新")
        return

    # 更新绩效（保留 factor_exposure 不变）
    if 'metrics' not in target:
        target['metrics'] = {}

    # 映射回测字段到注册表字段
    field_map = {
        'sharpe_ratio': 'sharpe_ratio',
        'win_rate': 'win_rate',
        'max_drawdown': 'max_drawdown',
        'total_return': 'total_return',
        'avg_return': 'avg_return',
        'confidence_score': 'confidence_score'
    }

    for backtest_key, registry_key in field_map.items():
        if backtest_key in backtest:
            target[registry_key] = backtest[backtest_key]

    # 状态更新
    sharpe = target.get('sharpe_ratio', 0.0)
    win_rate = target.get('win_rate', 0.0)
    drawdown = target.get('max_drawdown', 0.0)

    # 兜底策略永不退休
    if target.get('never_retire'):
        new_status = 'active'
        reason = '基准策略永不退休'
    elif sharpe < 0.3 or win_rate < 0.4 or drawdown > 0.25:
        new_status = 'retired'
        reason = f"夏普{sharpe:.2f}，胜率{win_rate:.2f}，回撤{drawdown:.2f}"
    elif sharpe < 0.6 or win_rate < 0.5:
        new_status = 'monitor'
        reason = f"夏普{sharpe:.2f}，胜率{win_rate:.2f}"
    else:
        new_status = 'active'
        reason = '绩效良好'

    target['status'] = new_status
    target['retire_reason'] = reason
    target['last_evaluated'] = str(Path(BACKTEST_SUMMARY).stat().st_mtime)

    save_json(REGISTRY_PATH, registry)
    print(f"✅ 策略 {STRATEGY_ID} 状态更新为 {new_status} ({reason})")
    print(f"   保留 factor_exposure: {target.get('factor_exposure', {})}")


if __name__ == '__main__':
    main()