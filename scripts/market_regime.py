#!/usr/bin/env python3
"""
市场状态感知模块（使用 akshare 获取指数数据）
输出：权重向量 + 置信度 + 趋势强度 + 数据等级
写入 $WORK_DIR/daily_stock_analysis/data/market_state.json
"""
import os
import sys
import json
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

WORK_DIR = os.environ.get('WORK_DIR', '.')

# 尝试导入 akshare
try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    print("⚠️ akshare 未安装，请运行: pip install akshare")


class MarketRegime:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '../market_regime_config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            # 默认配置
            self.config = {
                'threshold': 0.03,
                'discount': 0.7,
                'min_amplitude': 1.0,
                'window_short': 20,
                'window_long': 60,
                'index_pairs': [
                    {'value_code': '000922', 'growth_code': '000688'},
                    {'value_code': '000300', 'growth_code': '399006'}
                ]
            }
        self.threshold = self.config['threshold']
        self.discount = self.config['discount']
        self.min_amplitude = self.config['min_amplitude']
        self.window_short = self.config['window_short']
        self.window_long = self.config['window_long']
        self.index_pairs = self.config['index_pairs']

    def get_index_data_akshare(self, code, end_date):
        """
        使用 akshare 获取指数日线数据
        支持：000922（中证红利），000688（科创50），000300（沪深300），399006（创业板指）
        """
        if not HAS_AKSHARE:
            return None

        # 转换代码格式
        if code.startswith('000') or code.startswith('688'):
            symbol = 'sh' + code
        elif code.startswith('399'):
            symbol = 'sz' + code
        else:
            symbol = code

        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty:
                return None
            df['date'] = pd.to_datetime(df['date'])
            # 只保留最近 window_long+10 天的数据
            cutoff = (pd.to_datetime(end_date) - timedelta(days=self.window_long + 10)).strftime('%Y-%m-%d')
            df = df[df['date'] >= cutoff]
            df = df.sort_values('date')
            return df[['date', 'close']]
        except Exception as e:
            print(f"⚠️ akshare 获取 {code} 失败: {e}")
            return None

    def fetch_index_pair(self, value_code, growth_code, end_date):
        """获取一对指数的历史数据"""
        df_v = self.get_index_data_akshare(value_code, end_date)
        df_g = self.get_index_data_akshare(growth_code, end_date)
        if df_v is None or df_g is None or df_v.empty or df_g.empty:
            return None
        df = pd.merge(df_v, df_g, on='date', suffixes=('_value', '_growth'))
        df = df.rename(columns={'close_value': 'value', 'close_growth': 'growth'})
        return df

    def calc_weights(self, diff):
        """根据风格差计算权重向量"""
        # 使用 sigmoid 将 diff 映射到 [0,1] 的价值权重
        value_w = 1 / (1 + np.exp(-diff * 2))
        quality_w = 0.1
        growth_w = 1 - value_w - quality_w
        growth_w = max(0, growth_w)
        value_w = max(0, min(1, value_w))
        return {'value': round(value_w, 4), 'growth': round(growth_w, 4), 'quality': round(quality_w, 4)}

    def calc_confidence(self, diff, short_ret, long_ret):
        """计算置信度"""
        base = min(abs(diff) / self.threshold, 1.0)
        same_direction = (short_ret * long_ret) > 0
        if same_direction:
            conf = base * 1.2
        else:
            conf = base * self.discount
        if same_direction and abs(short_ret) < self.min_amplitude / 100:
            conf *= 0.8
        return round(min(conf, 1.0), 4)

    def get_regime(self, asof_date=None):
        """主入口：返回市场状态字典"""
        if asof_date is None:
            asof_date = datetime.now()
        else:
            asof_date = pd.to_datetime(asof_date)

        data_level = 1
        df = None
        for pair in self.index_pairs:
            df = self.fetch_index_pair(pair['value_code'], pair['growth_code'], asof_date)
            if df is not None and len(df) >= self.window_long + 1:
                break
            data_level += 1

        # 如果所有数据源都失败，返回默认均衡权重
        if df is None or len(df) < self.window_long + 1:
            print("⚠️ 无法获取指数数据，使用默认均衡权重")
            return {
                'weights': {'value': 0.34, 'growth': 0.33, 'quality': 0.33},
                'confidence': 0.0,
                'trend_strength': 0.0,
                'data_level': 3,
                'label': '数据不可用',
                'diff': 0.0,
                'short_ret': 0.0,
                'long_ret': 0.0
            }

        # 计算短期（20日）收益率
        last_row = df.iloc[-1]
        prev_row = df.iloc[-self.window_short - 1]
        short_ret_v = (last_row['value'] - prev_row['value']) / prev_row['value']
        short_ret_g = (last_row['growth'] - prev_row['growth']) / prev_row['growth']
        short_diff = short_ret_g - short_ret_v

        # 计算长期（60日）收益率
        prev_long = df.iloc[-self.window_long - 1]
        long_ret_v = (last_row['value'] - prev_long['value']) / prev_long['value']
        long_ret_g = (last_row['growth'] - prev_long['growth']) / prev_long['growth']
        long_diff = long_ret_g - long_ret_v

        diff = short_diff
        weights = self.calc_weights(diff)
        confidence = self.calc_confidence(diff, short_diff, long_diff)
        trend_strength = min(abs(diff) / 0.1, 1.0)

        # 标签
        if confidence > 0.6:
            if weights['value'] > 0.6:
                label = '价值占优'
            elif weights['growth'] > 0.6:
                label = '成长占优'
            else:
                label = '均衡'
        else:
            label = '混沌'

        print(f"📊 获取到指数数据: 价值指数={df['value'].iloc[-1]:.2f}, 成长指数={df['growth'].iloc[-1]:.2f}")
        print(f"   风格差(20日): {diff:.4f}, 置信度: {confidence:.2f}")

        return {
            'weights': weights,
            'confidence': confidence,
            'trend_strength': round(trend_strength, 4),
            'data_level': data_level,
            'label': label,
            'diff': round(diff, 4),
            'short_ret': round(short_diff, 4),
            'long_ret': round(long_diff, 4)
        }


def main():
    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), '../market_regime_config.yaml')
    mr = MarketRegime(config_path if os.path.exists(config_path) else None)
    state = mr.get_regime()

    # 写入 market_state.json
    state_file = os.path.join(WORK_DIR, 'daily_stock_analysis/data/market_state.json')
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"📊 市场状态: {state['label']}")
    print(f"   权重向量: 价值={state['weights']['value']}, 成长={state['weights']['growth']}, 质量={state['weights']['quality']}")
    print(f"   置信度: {state['confidence']}")
    print(f"   数据等级: {state['data_level']}")
    print(f"   风格差(20日): {state['diff']:.4f}")


if __name__ == '__main__':
    main()