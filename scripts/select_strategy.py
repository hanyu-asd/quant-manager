#!/usr/bin/env python3
"""
策略选择器 v2.0
- 双引擎评分：标签匹配度 + 因子余弦相似度 + 夏普加权
- 标签软匹配（标准化映射）
- 最低置信度阈值（<0.4 启用保底策略）
"""
import os
import json
import sys
import math
from pathlib import Path

WORK_DIR = os.environ.get('WORK_DIR', '.')
REGISTRY_PATH = os.environ.get('REGISTRY_PATH', 
                              os.path.join(WORK_DIR, 'strategy_registry.json'))
STATE_PATH = os.path.join(WORK_DIR, 'market_state.json')

# 标签标准化映射（原始 → AlphaSift 可识别）
TAG_NORMALIZE = {
    'value': 'value_style',
    'growth': 'growth_style',
    'neutral': 'neutral',
    'value_style': 'value_style',
    'growth_style': 'growth_style'
}

# 最低匹配阈值（低于此值启用保底策略）
MIN_SCORE_THRESHOLD = 0.4

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 加载 {path} 失败: {e}")
        return None

def normalize_tags(raw_tags):
    """标准化标签列表"""
    normalized = []
    for tag in raw_tags:
        normalized.append(TAG_NORMALIZE.get(tag, tag))
    return list(set(normalized))  # 去重

def cosine_similarity(vec_a, vec_b):
    """计算余弦相似度"""
    # 提取三维向量
    a = [vec_a.get('value', 0), vec_a.get('growth', 0), vec_a.get('quality', 0)]
    b = [vec_b.get('value', 0), vec_b.get('growth', 0), vec_b.get('quality', 0)]
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))

def normalize_sharpe(sharpe):
    """归一化夏普比率（映射到 0-1）"""
    # 假设夏普范围 -0.5 ~ 2.0
    normalized = (sharpe + 0.5) / 2.5
    return max(0.0, min(1.0, normalized))

def calculate_tag_match(current_tags, strategy_tags):
    """计算标签匹配度（Jaccard 相似度）"""
    if not strategy_tags:
        return 0.5  # 未定义标签时给中性分
    
    current_set = set(normalize_tags(current_tags))
    strategy_set = set(strategy_tags)
    
    if not current_set or not strategy_set:
        return 0.0
    
    intersection = len(current_set & strategy_set)
    union = len(current_set | strategy_set)
    
    return intersection / union if union > 0 else 0.0

def main():
    print("🎯 策略选择器 v2.0 启动...")
    
    # 1. 加载市场状态
    state = load_json(STATE_PATH)
    if not state:
        print("❌ 无法加载 market_state.json，退出")
        sys.exit(1)
    
    current_tags = state.get('tags', ['neutral'])
    state_vec = state.get('state_vec', {'value': 0.33, 'growth': 0.33, 'quality': 0.34})
    confidence = state.get('confidence', 0.5)
    fallback_strategy = state.get('fallback_strategy', 'balanced_alpha')
    fallback_alphaevo = state.get('fallback_alphaevo', 'rsi_reversion_v1')
    
    print(f"  ├─ 当前标签: {current_tags}")
    print(f"  ├─ 状态向量: value={state_vec.get('value', 0):.2f}, "
          f"growth={state_vec.get('growth', 0):.2f}, "
          f"quality={state_vec.get('quality', 0):.2f}")
    print(f"  ├─ 数据置信度: {confidence}")
    
    # 2. 加载策略注册表
    registry = load_json(REGISTRY_PATH)
    if not registry:
        print("❌ 无法加载策略注册表，退出")
        sys.exit(1)
    
    strategies = registry.get('strategies', [])
    if not strategies:
        print("❌ 策略注册表为空，退出")
        sys.exit(1)
    
    # 3. 计算每个策略的得分
    scored = []
    for s in strategies:
        # 3.1 标签匹配度
        strategy_tags = s.get('market_regime', [])
        tag_score = calculate_tag_match(current_tags, strategy_tags)
        
        # 3.2 因子余弦相似度
        factor_exp = s.get('factor_exposure', {'value': 0.33, 'growth': 0.33, 'quality': 0.34})
        cosine_score = cosine_similarity(state_vec, factor_exp)
        
        # 3.3 夏普归一化
        sharpe = s.get('sharpe_ratio', 0.5)
        sharpe_score = normalize_sharpe(sharpe)
        
        # 3.4 综合评分（权重可调）
        # 标签匹配 50% + 余弦相似度 30% + 夏普 20%
        final_score = 0.5 * tag_score + 0.3 * cosine_score + 0.2 * sharpe_score
        
        scored.append({
            'id': s.get('id'),
            'alpha_sift_strategy': s.get('alpha_sift_strategy'),
            'alphaevo_strategy': s.get('alphaevo_strategy'),
            'score': final_score,
            'tag_score': tag_score,
            'cosine_score': cosine_score,
            'sharpe_score': sharpe_score,
            'status': s.get('status', 'active'),
            'factor_exposure': factor_exp
        })
    
    # 4. 按得分排序
    scored.sort(key=lambda x: x['score'], reverse=True)
    
    # 5. 检查最高得分是否低于阈值
    best = scored[0]
    print(f"  ├─ 最高得分: {best['score']:.4f} ({best['id']})")
    
    if best['score'] < MIN_SCORE_THRESHOLD:
        print(f"  ├─ ⚠️ 最高得分 {best['score']:.4f} < {MIN_SCORE_THRESHOLD}，启用保底策略")
        # 从注册表中查找保底策略
        fallback = None
        for s in strategies:
            if s.get('id') == fallback_strategy:
                fallback = s
                break
        if fallback:
            best = {
                'id': fallback.get('id'),
                'alpha_sift_strategy': fallback.get('alpha_sift_strategy'),
                'alphaevo_strategy': fallback.get('alphaevo_strategy'),
                'score': 0.5,
                'tag_score': 0.5,
                'cosine_score': 0.5,
                'sharpe_score': 0.5,
                'status': fallback.get('status', 'active'),
                'factor_exposure': fallback.get('factor_exposure', {})
            }
            print(f"  │  └─ 保底策略: {best['id']}")
        else:
            print(f"  │  └─ ⚠️ 保底策略 {fallback_strategy} 未找到，使用第一个可用策略")
    
    # 6. 输出结果
    print(f"  └─ ✅ 选中策略: {best['id']}")
    print(f"     AlphaSift: {best['alpha_sift_strategy']}")
    print(f"     AlphaEvo: {best['alphaevo_strategy']}")
    print(f"     factor_exposure: {best['factor_exposure']}")
    
    # 7. 写入 GitHub Actions 输出
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"selected_strategy={best['id']}\n")
            f.write(f"alpha_sift_strategy={best['alpha_sift_strategy']}\n")
            f.write(f"alphaevo_strategy={best['alphaevo_strategy']}\n")
            f.write(f"selection_score={best['score']:.4f}\n")
    else:
        # 本地测试
        result_path = Path(WORK_DIR) / 'selected_strategy.json'
        with open(result_path, 'w') as f:
            json.dump(best, f, indent=2)
        print(f"✅ 选择结果已保存到: {result_path}")

if __name__ == '__main__':
    main()