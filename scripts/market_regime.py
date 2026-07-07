#!/usr/bin/env python3
"""
市场状态感知引擎 v2.0
- 采用相对分位数法（滚动60日）
- 输出 AlphaSift 标准标签
- 内置数据置信度门禁 + 状态持久化
"""
import os
import json
import sys
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque

# ==================== 配置加载 ====================
WORK_DIR = os.environ.get('WORK_DIR', '.')
CONFIG_PATH = Path(WORK_DIR) / 'market_regime_config.yaml'
STATE_PATH = Path(WORK_DIR) / 'market_state.json'
LAST_VALID_PATH = Path(WORK_DIR) / '.last_valid_state.json'

# 默认配置
CONFIG = {
    'rolling_window': 60,
    'percentile_threshold': 70,
    'confidence_required': 0.6,
    'data_source_weights': {'index': 0.4, 'breadth': 0.3, 'sector': 0.2, 'style': 0.1},
    'fallback_strategy': 'balanced_alpha',
    'fallback_alphaevo': 'rsi_reversion_v1',
    'indices': {
        'sh': '000001.SH',
        'sz': '399001.SZ',
        'cyb': '399006.SZ',
        'hs300': '000300.SH',
        'value': '000029.SH',
        'growth': '000030.SH'
    },
    'label_mapping': {
        'value': 'value_style',
        'growth': 'growth_style',
        'neutral': 'neutral'
    }
}

if CONFIG_PATH.exists():
    with open(CONFIG_PATH, 'r') as f:
        user_config = yaml.safe_load(f)
        if user_config:
            CONFIG.update(user_config)

# ==================== 数据获取层 ====================

def get_index_data_tickflow(symbol, count=60):
    """从 TickFlow 免费接口获取指数日线"""
    try:
        from tickflow import TickFlow
        tf = TickFlow.free()
        df = tf.klines.get(
            symbol=symbol,
            period="1d",
            count=count,
            as_dataframe=True
        )
        if df is None or df.empty:
            return None
        df = df.sort_values('trade_date')
        return df
    except Exception as e:
        print(f"⚠️ TickFlow 获取 {symbol} 失败: {e}")
        return None

def get_market_breadth():
    """获取全市场涨跌家数（Akshare 降级）"""
    try:
        import akshare as ak
        # 尝试东财接口
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            up = len(df[df['涨幅'] > 0])
            down = len(df[df['涨幅'] < 0])
            total = len(df)
            amount = df['成交额'].sum() if '成交额' in df.columns else None
            return {'up': up, 'down': down, 'total': total, 'amount': amount, 'source': 'akshare_em'}
    except Exception as e1:
        print(f"⚠️ Akshare 东财接口失败: {e1}")
        try:
            # 降级到新浪接口
            import akshare as ak
            df = ak.stock_zh_a_spot()
            if df is not None and not df.empty:
                up = len(df[df['涨跌幅'] > 0])
                down = len(df[df['涨跌幅'] < 0])
                total = len(df)
                amount = df['成交额'].sum() if '成交额' in df.columns else None
                return {'up': up, 'down': down, 'total': total, 'amount': amount, 'source': 'akshare_sina'}
        except Exception as e2:
            print(f"⚠️ Akshare 新浪接口失败: {e2}")
    return None

def get_sector_rotation():
    """获取板块轮动数据（涨幅前5 vs 后5的差值）"""
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return None
        # 按涨跌幅排序
        df_sorted = df.sort_values('涨跌幅', ascending=False)
        top5_avg = df_sorted.head(5)['涨跌幅'].mean()
        bottom5_avg = df_sorted.tail(5)['涨跌幅'].mean()
        spread = top5_avg - bottom5_avg
        return {'spread': spread, 'count': len(df)}
    except Exception as e:
        print(f"⚠️ 获取板块轮动失败: {e}")
        return None

# ==================== 状态持久化 ====================

def load_last_valid_state():
    """加载上一次有效状态"""
    if LAST_VALID_PATH.exists():
        try:
            with open(LAST_VALID_PATH, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def save_last_valid_state(state):
    """保存当前状态为有效状态"""
    with open(LAST_VALID_PATH, 'w') as f:
        json.dump(state, f, indent=2)

# ==================== 核心计算 ====================

def compute_rolling_percentile(series, current_value, window=60):
    """计算当前值在历史窗口中的分位数（0-100）"""
    if len(series) < window:
        window = len(series)
    if window < 5:
        return 50.0  # 数据不足时返回中位数
    history = series.tail(window).values
    percentile = np.percentile(history, CONFIG['percentile_threshold'])
    # 返回当前值超过阈值的程度（百分比）
    if percentile == 0:
        return 50.0
    ratio = current_value / percentile
    return min(100, max(0, ratio * 50 + 50))  # 映射到 0-100

def calculate_state(indices_data, breadth_data, sector_data):
    """计算市场状态标签和向量"""
    
    # 1. 提取关键数据
    sh_df = indices_data.get('sh')
    if sh_df is None or sh_df.empty:
        return None, None, 0.0, "指数数据缺失"
    
    sh_close = sh_df['close'].values
    sh_high = sh_df['high'].values
    sh_low = sh_df['low'].values
    
    current_close = sh_close[-1]
    
    # 计算MA20
    ma20 = np.mean(sh_close[-20:]) if len(sh_close) >= 20 else current_close
    
    # 计算MA20斜率（20日）
    if len(sh_close) >= 25:
        ma20_old = np.mean(sh_close[-25:-5])
        ma20_slope = (ma20 - ma20_old) / ma20_old if ma20_old > 0 else 0
    else:
        ma20_slope = 0
    
    # 计算20日波动率
    if len(sh_close) >= 20:
        returns = np.diff(sh_close[-21:]) / sh_close[-21:-1]
        volatility = np.std(returns) * np.sqrt(252)
    else:
        volatility = 0.2
    
    # 2. 计算各维度分位数（相对判断）
    
    # 2.1 趋势强度：MA20斜率在历史中的分位数
    if len(sh_close) >= CONFIG['rolling_window']:
        ma20_history = []
        for i in range(CONFIG['rolling_window'] - 20):
            if i + 20 < len(sh_close):
                ma = np.mean(sh_close[i:i+20])
                ma_old = np.mean(sh_close[i:i+15]) if i+15 < len(sh_close) else ma
                slope = (ma - ma_old) / ma_old if ma_old > 0 else 0
                ma20_history.append(slope)
        trend_percentile = compute_rolling_percentile(pd.Series(ma20_history), ma20_slope)
    else:
        trend_percentile = 50.0
    
    # 2.2 风险偏好（涨跌比）
    if breadth_data and breadth_data.get('down', 0) > 0:
        ratio = breadth_data['up'] / breadth_data['down']
        # 使用历史涨跌比分位数（简化：用过去60日平均）
        risk_percentile = min(100, max(0, (ratio - 0.8) / 1.2 * 100))
    else:
        risk_percentile = 50.0
    
    # 2.3 流动性（成交额）
    if breadth_data and breadth_data.get('amount'):
        # 简化：直接判断是否高于均值（此处用固定阈值，实际可优化）
        amount = breadth_data['amount']
        # 假设过去均值约8000亿（A股），可改为从历史数据计算
        liquidity_percentile = min(100, max(0, (amount / 1e11 - 0.5) / 1.5 * 100))
    else:
        liquidity_percentile = 50.0
    
    # 2.4 风格（价值 vs 成长）
    value_df = indices_data.get('value')
    growth_df = indices_data.get('growth')
    style_vec = {'value': 0.33, 'growth': 0.33, 'quality': 0.34}  # 默认均衡
    
    if value_df is not None and growth_df is not None and len(value_df) >= 21 and len(growth_df) >= 21:
        value_ret = (value_df['close'].iloc[-1] / value_df['close'].iloc[-21] - 1)
        growth_ret = (growth_df['close'].iloc[-1] / growth_df['close'].iloc[-21] - 1)
        style_diff = value_ret - growth_ret
        
        if style_diff > 0.02:
            style_label = 'value'
            style_vec = {'value': 0.8, 'growth': 0.1, 'quality': 0.1}
        elif style_diff < -0.02:
            style_label = 'growth'
            style_vec = {'value': 0.1, 'growth': 0.8, 'quality': 0.1}
        else:
            style_label = 'neutral'
            style_vec = {'value': 0.4, 'growth': 0.3, 'quality': 0.3}
    else:
        style_label = 'neutral'
        style_vec = {'value': 0.4, 'growth': 0.3, 'quality': 0.3}
    
    # 2.5 板块轮动（rotation）
    rotation = False
    if sector_data and sector_data.get('spread'):
        spread = sector_data['spread']
        if spread > 3.0:  # 前5后5板块涨跌幅差 > 3%
            rotation = True
    
    # 2.6 低波动（low_vol）
    vol_percentile = 50.0
    if len(sh_close) >= CONFIG['rolling_window']:
        vol_history = []
        for i in range(CONFIG['rolling_window'] - 20):
            if i + 20 < len(sh_close):
                rets = np.diff(sh_close[i:i+21]) / sh_close[i:i+20]
                vol = np.std(rets) * np.sqrt(252)
                vol_history.append(vol)
        if vol_history:
            vol_percentile = compute_rolling_percentile(pd.Series(vol_history), volatility)
    low_vol = vol_percentile < 30  # 波动率处于历史低位
    
    # 3. 生成标签（标准化）
    tags = []
    
    # 风险偏好
    if risk_percentile > 60:
        tags.append('risk_on')
    else:
        tags.append('risk_off')
    
    # 趋势
    if trend_percentile > 60:
        tags.append('trend')
    else:
        tags.append('range_bound')
    
    # 流动性
    if liquidity_percentile > 60:
        tags.append('high_liquidity')
    
    # 风格（使用标准化标签）
    mapped_style = CONFIG['label_mapping'].get(style_label, 'neutral')
    tags.append(mapped_style)
    
    # 轮动
    if rotation:
        tags.append('rotation')
    
    # 低波动
    if low_vol:
        tags.append('low_vol')
    
    # 4. 计算置信度
    confidence = 1.0
    if indices_data.get('sh') is None:
        confidence *= 0.6
    if breadth_data is None:
        confidence *= 0.7
    if sector_data is None:
        confidence *= 0.9
    if indices_data.get('value') is None or indices_data.get('growth') is None:
        confidence *= 0.8
    
    confidence = round(min(1.0, confidence), 2)
    
    return tags, style_vec, confidence, None

# ==================== 主入口 ====================

def main():
    print("📊 市场状态感知引擎 v2.0 启动...")
    
    # 1. 获取指数数据
    print("  ├─ 获取指数日线 (TickFlow)...")
    indices_data = {}
    for name, symbol in CONFIG['indices'].items():
        df = get_index_data_tickflow(symbol, CONFIG['rolling_window'])
        if df is not None:
            indices_data[name] = df
            print(f"  │  ├─ {name} ({symbol}) 成功, {len(df)} 条")
        else:
            print(f"  │  ├─ {name} ({symbol}) 失败")
    
    # 2. 获取市场广度
    print("  ├─ 获取市场广度 (Akshare)...")
    breadth_data = get_market_breadth()
    if breadth_data:
        print(f"  │  └─ 涨: {breadth_data['up']}, 跌: {breadth_data['down']}")
    else:
        print("  │  └─ 市场广度获取失败")
    
    # 3. 获取板块轮动
    print("  ├─ 获取板块轮动 (Akshare)...")
    sector_data = get_sector_rotation()
    if sector_data:
        print(f"  │  └─ 板块涨跌幅差: {sector_data.get('spread', 0):.2f}%")
    else:
        print("  │  └─ 板块轮动获取失败")
    
    # 4. 计算状态
    tags, state_vec, confidence, error = calculate_state(indices_data, breadth_data, sector_data)
    
    # 5. 置信度门禁
    if confidence < CONFIG['confidence_required']:
        print(f"  ├─ ⚠️ 数据置信度 {confidence} < {CONFIG['confidence_required']}，启用降级模式")
        last_state = load_last_valid_state()
        if last_state:
            tags = last_state.get('tags', ['neutral'])
            state_vec = last_state.get('state_vec', {'value': 0.33, 'growth': 0.33, 'quality': 0.34})
            confidence = last_state.get('confidence', 0.5)
            print(f"  │  └─ 复用 T-1 状态: {tags}")
        else:
            # 无历史状态，使用保底
            tags = ['neutral']
            state_vec = {'value': 0.34, 'growth': 0.33, 'quality': 0.33}
            confidence = 0.3
            print("  │  └─ 无历史状态，使用保底均衡权重")
    else:
        # 保存当前有效状态
        save_last_valid_state({
            'tags': tags,
            'state_vec': state_vec,
            'confidence': confidence,
            'date': datetime.now().isoformat()
        })
        print(f"  ├─ ✅ 状态计算成功，置信度: {confidence}")
    
    # 6. 输出结果
    state = {
        'tags': tags,
        'state_vec': state_vec,
        'confidence': confidence,
        'data_level': 0 if confidence > 0.7 else 1 if confidence > 0.5 else 2,
        'updated_at': datetime.now().isoformat(),
        'fallback_strategy': CONFIG['fallback_strategy'],
        'fallback_alphaevo': CONFIG['fallback_alphaevo']
    }
    
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"  └─ 输出: {tags}")
    print(f"     权重向量: value={state_vec.get('value', 0):.2f}, "
          f"growth={state_vec.get('growth', 0):.2f}, "
          f"quality={state_vec.get('quality', 0):.2f}")
    
    # 供 GitHub Actions 使用
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"confidence={confidence}\n")
            f.write(f"tags={','.join(tags)}\n")

if __name__ == '__main__':
    main()