#!/usr/bin/env python3
"""
Monkey Patching: 让 daily_stock_analysis 的大盘复盘使用 TickFlow 免费日K数据
用法：在运行 python main.py 之前，先执行此脚本
"""
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta

# 尝试导入 tickflow
try:
    import tickflow as tf
    TICKFLOW_AVAILABLE = True
except ImportError:
    TICKFLOW_AVAILABLE = False
    print("⚠️ TickFlow 未安装，请运行 pip install tickflow")

# 尝试导入要替换的数据源模块
try:
    from data_provider.tencent_fetcher import TencentFetcher
    from data_provider.efinance_fetcher import EfinanceFetcher
except ImportError as e:
    print(f"⚠️ 无法导入数据源模块: {e}")
    print("请确保在 daily_stock_analysis 项目目录下运行此脚本")
    sys.exit(1)

# 保存原始方法
_original_tencent_get = TencentFetcher.get_realtime_quotes
_original_efinance_get = EfinanceFetcher.get_realtime_quotes

def _tickflow_to_realtime_quote(symbol, df_row):
    """
    将 TickFlow 日K行数据转换为项目期望的实时行情格式
    """
    close = df_row.get('close', 0)
    open_price = df_row.get('open', close)
    high = df_row.get('high', close)
    low = df_row.get('low', close)
    volume = df_row.get('volume', 0)
    pre_close = df_row.get('pre_close', close)
    change_pct = ((close - pre_close) / pre_close * 100) if pre_close != 0 else 0.0
    amount = volume * close if volume else 0
    return {
        'code': symbol,
        'name': symbol,
        'price': close,
        'open': open_price,
        'high': high,
        'low': low,
        'volume': volume,
        'amount': amount,
        'change_pct': change_pct,
        'pre_close': pre_close,
        'change': change_pct,
        'turnover_rate': 0.0,
        'pe_ratio': 0.0,
        'pb_ratio': 0.0,
    }

def get_realtime_from_tickflow(symbols):
    """
    从 TickFlow 免费版获取指定标的的最近交易日日K数据
    """
    if not TICKFLOW_AVAILABLE:
        return None
    today = datetime.now().strftime('%Y-%m-%d')
    dates_to_try = [today] + [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 5)]
    result = []
    for sym in symbols:
        data = None
        for date_str in dates_to_try:
            try:
                df = tf.free().klines.get(sym, start_date=date_str, end_date=date_str)
                if df is not None and not df.empty:
                    data = df.iloc[-1]
                    break
            except Exception:
                continue
        if data is not None:
            result.append(_tickflow_to_realtime_quote(sym, data))
        else:
            print(f"⚠️ TickFlow 未获取到 {sym} 的数据")
    return result

def patched_get_realtime_quotes(self, symbols):
    tickflow_result = get_realtime_from_tickflow(symbols)
    if tickflow_result and len(tickflow_result) > 0:
        return tickflow_result
    return _original_tencent_get(self, symbols)

def patched_efinance_get_realtime_quotes(self, symbols):
    tickflow_result = get_realtime_from_tickflow(symbols)
    if tickflow_result and len(tickflow_result) > 0:
        return tickflow_result
    return _original_efinance_get(self, symbols)

# 应用 patch
TencentFetcher.get_realtime_quotes = patched_get_realtime_quotes
EfinanceFetcher.get_realtime_quotes = patched_efinance_get_realtime_quotes

print("✅ Monkey Patching 完成：大盘复盘将优先使用 TickFlow 免费日K数据")