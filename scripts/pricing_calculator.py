#!/usr/bin/env python3
"""
T+1 定价计算器
基于 T 日收盘价和 TickFlow 历史日线计算买入价、止盈价、止损价
"""
import os
import sys
import json
import csv
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

WORK_DIR = os.environ.get('WORK_DIR', '.')
STOCK_LIST = os.environ.get('STOCK_LIST', '')

# 默认参数（可由策略动态调整）
DEFAULT_BUY_OFFSET = 0.98       # 买入偏移系数
DEFAULT_STOP_LOSS_PCT = 0.05    # 止损比例 5%
DEFAULT_TAKE_PROFIT_PCT = 0.10  # 止盈比例 10%
DEFAULT_LOOKBACK = 60           # 计算支撑/压力位的回看天数

def get_stock_pool():
    """从 DSA 数据目录读取候选股票池"""
    pool_path = Path(WORK_DIR) / 'daily_stock_analysis' / 'data' / 'stock_pool.csv'
    if not pool_path.exists():
        print("⚠️ 未找到候选股票池")
        return []
    df = pd.read_csv(pool_path)
    if 'code' not in df.columns:
        print("⚠️ CSV 缺少 'code' 列")
        return []
    return df['code'].tolist()

def get_latest_close(symbol):
    """获取最新收盘价（通过 TickFlow 免费版）"""
    try:
        import tickflow as tf
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        df = tf.free().klines.get(symbol, start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            return df.iloc[-1]['close']
    except Exception as e:
        print(f"⚠️ 获取 {symbol} 收盘价失败: {e}")
    return None

def calculate_support_resistance(symbol, lookback=DEFAULT_LOOKBACK):
    """计算支撑/压力位（基于 TickFlow 历史日线）"""
    try:
        import tickflow as tf
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback)).strftime('%Y-%m-%d')
        df = tf.free().klines.get(symbol, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return None, None
        # 计算近期高低点
        recent_high = df['high'].max()
        recent_low = df['low'].min()
        return recent_high, recent_low
    except Exception as e:
        print(f"⚠️ 计算 {symbol} 支撑/压力位失败: {e}")
        return None, None

def calculate_prices(symbol, close_price, buy_offset, stop_loss_pct, take_profit_pct):
    """计算买入价、止盈价、止损价"""
    entry = close_price * buy_offset
    stop_loss = entry * (1 - stop_loss_pct)
    take_profit = entry * (1 + take_profit_pct)
    return entry, stop_loss, take_profit

def main():
    stocks = get_stock_pool()
    if not stocks:
        print("⚠️ 无股票可定价")
        return

    # 加载策略参数（可扩展从注册表获取）
    # 这里使用默认值，实际可从环境变量或策略注册表读取
    buy_offset = float(os.environ.get('BUY_OFFSET', DEFAULT_BUY_OFFSET))
    stop_loss_pct = float(os.environ.get('STOP_LOSS_PCT', DEFAULT_STOP_LOSS_PCT))
    take_profit_pct = float(os.environ.get('TAKE_PROFIT_PCT', DEFAULT_TAKE_PROFIT_PCT))

    results = []
    for code in stocks:
        close = get_latest_close(code)
        if close is None:
            print(f"⚠️ 跳过 {code}，无法获取收盘价")
            continue
        support, resistance = calculate_support_resistance(code)
        entry, stop_loss, take_profit = calculate_prices(
            code, close, buy_offset, stop_loss_pct, take_profit_pct
        )
        results.append({
            'code': code,
            'close_price': round(close, 2),
            'support': round(support, 2) if support else None,
            'resistance': round(resistance, 2) if resistance else None,
            'entry_price': round(entry, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'buy_offset': buy_offset,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct
        })

    # 生成 Markdown 报告
    report_lines = []
    report_lines.append("# 📊 T+1 定价报告")
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append("## 买入价格参考")
    report_lines.append("")
    report_lines.append("| 股票代码 | 收盘价 | 支撑位 | 压力位 | 买入价 | 止损价 | 止盈价 |")
    report_lines.append("|----------|--------|--------|--------|--------|--------|--------|")
    for r in results:
        support_str = str(r['support']) if r['support'] else '-'
        resistance_str = str(r['resistance']) if r['resistance'] else '-'
        report_lines.append(
            f"| {r['code']} | {r['close_price']} | {support_str} | {resistance_str} | "
            f"{r['entry_price']} | {r['stop_loss']} | {r['take_profit']} |"
        )

    report_lines.append("")
    report_lines.append("**说明**：")
    report_lines.append(f"- 买入价 = 收盘价 × {buy_offset}")
    report_lines.append(f"- 止损价 = 买入价 × (1 - {stop_loss_pct:.0%})")
    report_lines.append(f"- 止盈价 = 买入价 × (1 + {take_profit_pct:.0%})")
    report_lines.append("- 支撑/压力位基于近60日TickFlow历史数据计算")

    # 保存报告
    report_path = Path(WORK_DIR) / 'pricing.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"✅ 定价报告已生成: {report_path}")

    # 同时输出 JSON 供后续使用
    json_path = Path(WORK_DIR) / 'pricing.json'
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()