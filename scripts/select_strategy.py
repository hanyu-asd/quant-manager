#!/usr/bin/env python3
"""
策略选择器 V3
基于市场状态向量 + 策略因子暴露度，通过余弦相似度匹配最优策略
"""
import os
import sys
import json
from pathlib import Path

REGISTRY_PATH = os.environ.get('REGISTRY_PATH', 'strategy_registry.json')
WORK_DIR = os.environ.get('WORK_DIR', '.')
MARKET_STATE_FILE = os.path.join(WORK_DIR, 'daily_stock_analysis/data/market_state.json')


def load_market_state():
    """加载市场状态向量"""
    try:
        with open(MARKET_STATE_FILE, 'r') as f:
            data = json.load(f)
            # 兼容旧格式：如果没有 weights 字段，使用默认均衡
            if 'weights' not in data:
                data['weights'] = {'value': 0.34, 'growth': 0.33, 'quality': 0.33}
                data['confidence'] = 0.0
            return data
    except FileNotFoundError:
        print("⚠️ 市场状态文件不存在，使用默认均衡权重")
        return {
            'weights': {'value': 0.34, 'growth': 0.33, 'quality': 0.33},
            'confidence': 0.0,
            'label': '未知'
        }


def load_registry():
    """加载策略注册表"""
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, 'r') as f:
            return json.load(f)
    else:
        # 默认注册表（保持向后兼容）
        default = {
            "strategies": [
                {"id": "momentum_trend", "alpha_sift_strategy": "momentum_quality",
                 "alphaevo_strategy": "trend_following", "status": "active",
                 "factor_exposure": {"value": 0.15, "growth": 0.80, "quality": 0.05},
                 "sharpe_ratio": 0.8, "win_rate": 0.58, "max_drawdown": 0.12},
                {"id": "balanced_alpha", "alpha_sift_strategy": "balanced_alpha",
                 "alphaevo_strategy": "rsi_reversion_v1", "status": "active",
                 "factor_exposure": {"value": 0.70, "growth": 0.20, "quality": 0.10},
                 "sharpe_ratio": 0.7, "win_rate": 0.55, "max_drawdown": 0.10},
                {"id": "value_defensive", "alpha_sift_strategy": "value_defensive",
                 "alphaevo_strategy": "value_mean_reversion", "status": "active",
                 "factor_exposure": {"value": 0.90, "growth": 0.05, "quality": 0.05},
                 "sharpe_ratio": 0.6, "win_rate": 0.52, "max_drawdown": 0.08},
                {"id": "oversold_rebound", "alpha_sift_strategy": "oversold_rebound",
                 "alphaevo_strategy": "oversold_reversal", "status": "active",
                 "factor_exposure": {"value": 0.10, "growth": 0.60, "quality": 0.30},
                 "sharpe_ratio": 0.5, "win_rate": 0.50, "max_drawdown": 0.15}
            ]
        }
        with open(REGISTRY_PATH, 'w') as f:
            json.dump(default, f, indent=2)
        return default


def cosine_similarity(vec1, vec2):
    """计算两个字典向量的余弦相似度"""
    keys = set(vec1.keys()) & set(vec2.keys())
    if not keys:
        return 0.0
    dot = sum(vec1[k] * vec2[k] for k in keys)
    norm1 = sum(v ** 2 for v in vec1.values()) ** 0.5
    norm2 = sum(v ** 2 for v in vec2.values()) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def normalize_sharpe(sharpe, max_sharpe=2.0, min_sharpe=-1.0):
    """将夏普映射到0~1区间"""
    if sharpe >= max_sharpe:
        return 1.0
    if sharpe <= min_sharpe:
        return 0.0
    return (sharpe - min_sharpe) / (max_sharpe - min_sharpe)


def select_strategy(market, registry):
    """基于因子暴露度匹配选择最优策略"""
    weights = market.get('weights', {'value': 0.34, 'growth': 0.33, 'quality': 0.33})
    confidence = market.get('confidence', 0.0)

    # 降级链：active → monitor → retired
    candidates = []
    for status in ['active', 'monitor', 'retired']:
        for s in registry['strategies']:
            if s.get('status') == status:
                candidates.append(s)
        if candidates:
            break

    # 如果全无，使用兜底
    if not candidates:
        print("⚠️ 无任何可用策略，使用兜底ETF策略")
        baseline = {
            'id': 'baseline_etf',
            'alpha_sift_strategy': 'baseline_etf',
            'alphaevo_strategy': 'baseline_etf',
            'factor_exposure': {'value': 0.34, 'growth': 0.33, 'quality': 0.33},
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'status': 'active'
        }
        candidates = [baseline]

    # 计算综合得分
    scored = []
    for s in candidates:
        exposure = s.get('factor_exposure', {})
        for dim in ['value', 'growth', 'quality']:
            exposure.setdefault(dim, 0.0)

        sim = cosine_similarity(exposure, weights)
        sharpe = s.get('sharpe_ratio', 0.0)
        sharpe_norm = normalize_sharpe(sharpe)
        combined = 0.6 * sim + 0.4 * sharpe_norm

        scored.append({
            'strategy': s,
            'similarity': sim,
            'sharpe_norm': sharpe_norm,
            'combined': combined
        })

    scored.sort(key=lambda x: x['combined'], reverse=True)
    best = scored[0]

    # 输出选择结果
    print(f"📊 市场状态: {market.get('label', '未知')} (置信度: {market.get('confidence', 0):.2f})")
    print(f"   权重向量: 价值={weights['value']:.2f}, 成长={weights['growth']:.2f}, 质量={weights['quality']:.2f}")
    print(f"🎯 选定策略: {best['strategy']['id']}")
    print(f"   综合得分: {best['combined']:.3f} (相似度: {best['similarity']:.3f}, 夏普贡献: {best['sharpe_norm']:.3f})")
    print(f"   AlphaSift: {best['strategy'].get('alpha_sift_strategy', best['strategy']['id'])}")
    print(f"   AlphaEvo: {best['strategy'].get('alphaevo_strategy', 'default')}")

    return best['strategy']


def main():
    market = load_market_state()
    registry = load_registry()
    selected = select_strategy(market, registry)

    # 写入 GITHUB_OUTPUT
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"selected_strategy={selected['id']}\n")
            f.write(f"alpha_sift_strategy={selected.get('alpha_sift_strategy', selected['id'])}\n")
            f.write(f"alphaevo_strategy={selected.get('alphaevo_strategy', 'default')}\n")
            f.write(f"market_label={market.get('label', '未知')}\n")
            f.write(f"market_confidence={market.get('confidence', 0)}\n")

    # 状态警告
    if selected.get('status') == 'monitor':
        print(f"⚠️ 策略处于 monitor 状态: {selected.get('retire_reason', '')}")
    elif selected.get('status') == 'retired':
        print(f"🚨 策略处于 retired 状态（兜底选择）: {selected.get('retire_reason', '')}")


if __name__ == '__main__':
    main()