#!/usr/bin/env python3
"""
策略选择器 V3
基于市场状态向量 + 策略因子暴露度，通过余弦相似度匹配最优策略
数据不可用时自动降级到真实存在的保底策略
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
            if 'weights' not in data:
                data['weights'] = {'value': 0.34, 'growth': 0.33, 'quality': 0.33}
                data['confidence'] = 0.0
                data['data_level'] = 3
            return data
    except FileNotFoundError:
        print("⚠️ 市场状态文件不存在，使用默认均衡权重")
        return {
            'weights': {'value': 0.34, 'growth': 0.33, 'quality': 0.33},
            'confidence': 0.0,
            'data_level': 3,
            'label': '未知'
        }


def load_registry():
    """加载策略注册表"""
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, 'r') as f:
            return json.load(f)
    else:
        print("⚠️ 注册表不存在，使用内置默认")
        default = {
            "strategies": [
                {"id": "balanced_alpha", "alpha_sift_strategy": "balanced_alpha",
                 "alphaevo_strategy": "rsi_reversion_v1", "status": "active",
                 "factor_exposure": {"value": 0.70, "growth": 0.20, "quality": 0.10},
                 "sharpe_ratio": 0.7, "win_rate": 0.55, "max_drawdown": 0.10},
                {"id": "momentum_trend", "alpha_sift_strategy": "momentum_quality",
                 "alphaevo_strategy": "trend_following", "status": "active",
                 "factor_exposure": {"value": 0.15, "growth": 0.80, "quality": 0.05},
                 "sharpe_ratio": 0.8, "win_rate": 0.58, "max_drawdown": 0.12},
                {"id": "value_defensive", "alpha_sift_strategy": "value_defensive",
                 "alphaevo_strategy": "value_mean_reversion", "status": "active",
                 "factor_exposure": {"value": 0.90, "growth": 0.05, "quality": 0.05},
                 "sharpe_ratio": 0.6, "win_rate": 0.52, "max_drawdown": 0.08},
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


def get_fallback_candidates(registry):
    """
    获取保底候选策略（真实存在的 AlphaSift 策略）
    排除 baseline_etf，优先 active，其次 monitor，最后 retired
    """
    all_strategies = registry.get('strategies', [])
    # 排除 baseline_etf（它是不存在的占位符）
    real_strategies = [s for s in all_strategies if s.get('id') != 'baseline_etf']
    if not real_strategies:
        return []
    # 按状态优先级排序
    for status in ['active', 'monitor', 'retired']:
        candidates = [s for s in real_strategies if s.get('status') == status]
        if candidates:
            # 按夏普降序排序
            return sorted(candidates, key=lambda x: x.get('sharpe_ratio', -999), reverse=True)
    # 如果没有匹配状态，返回所有真实策略（按夏普排序）
    return sorted(real_strategies, key=lambda x: x.get('sharpe_ratio', -999), reverse=True)


def select_strategy(market, registry):
    """基于因子暴露度匹配选择最优策略（带数据不可用降级）"""
    weights = market.get('weights', {'value': 0.34, 'growth': 0.33, 'quality': 0.33})
    confidence = market.get('confidence', 0.0)
    data_level = market.get('data_level', 1)

    # ---- 数据不可用时的保底逻辑 ----
    if data_level >= 3 or confidence < 0.3:
        print("⚠️ 市场数据不可用（数据等级≥3或置信度<0.3），切换到保底策略")
        fallback_list = get_fallback_candidates(registry)
        if fallback_list:
            best = fallback_list[0]
            print(f"📊 保底策略: {best['id']} (夏普: {best.get('sharpe_ratio', 0):.2f})")
            return best
        else:
            # 硬编码兜底：直接用 balanced_alpha（AlphaSift 必定存在）
            print("🚨 无可用保底策略，强制使用 balanced_alpha")
            for s in registry.get('strategies', []):
                if s.get('id') == 'balanced_alpha':
                    return s
            # 极端情况：如果 balanced_alpha 不存在，随便选一个真实策略
            for s in registry.get('strategies', []):
                if s.get('id') != 'baseline_etf':
                    print(f"⚠️ 使用备用策略: {s['id']}")
                    return s
            print("❌ 无法找到任何可用策略，退出")
            sys.exit(1)

    # ---- 正常匹配逻辑 ----
    # 降级链：active → monitor → retired（排除 baseline_etf）
    candidates = []
    for status in ['active', 'monitor', 'retired']:
        for s in registry['strategies']:
            if s.get('status') == status and s.get('id') != 'baseline_etf':
                candidates.append(s)
        if candidates:
            break

    # 如果全无，使用保底
    if not candidates:
        print("⚠️ 无候选策略，使用保底逻辑")
        fallback_list = get_fallback_candidates(registry)
        if fallback_list:
            return fallback_list[0]
        else:
            print("❌ 无任何可用策略，退出")
            sys.exit(1)

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
    best = scored[0]['strategy']

    # 输出选择结果
    print(f"📊 市场状态: {market.get('label', '未知')} (置信度: {market.get('confidence', 0):.2f})")
    print(f"   权重向量: 价值={weights['value']:.2f}, 成长={weights['growth']:.2f}, 质量={weights['quality']:.2f}")
    print(f"🎯 选定策略: {best['id']}")
    print(f"   综合得分: {scored[0]['combined']:.3f} (相似度: {scored[0]['similarity']:.3f}, 夏普贡献: {scored[0]['sharpe_norm']:.3f})")
    print(f"   AlphaSift: {best.get('alpha_sift_strategy', best['id'])}")
    print(f"   AlphaEvo: {best.get('alphaevo_strategy', 'default')}")

    return best


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
            f.write(f"market_data_level={market.get('data_level', 1)}\n")

    # 状态警告
    if selected.get('status') == 'monitor':
        print(f"⚠️ 策略处于 monitor 状态: {selected.get('retire_reason', '')}")
    elif selected.get('status') == 'retired':
        print(f"🚨 策略处于 retired 状态（兜底选择）: {selected.get('retire_reason', '')}")


if __name__ == '__main__':
    main()