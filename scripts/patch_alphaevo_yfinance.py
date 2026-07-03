#!/usr/bin/env python3
"""
为 AlphaEvo 的 yfinance 模块打补丁，使其使用 TickFlow 免费日K数据
用法：在运行 alphaevo 命令之前执行此脚本
"""
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# 导入原始 yfinance（如果不存在则报错）
try:
    import yfinance as yf_orig
except ImportError:
    print("⚠️ yfinance 未安装，无法应用补丁")
    sys.exit(0)

# 保存原始 download 方法
_orig_download = yf_orig.download

def tickflow_download(symbols, start=None, end=None, **kwargs):
    """
    替代 yfinance.download，使用 TickFlow 免费日K数据
    """
    print(f"[TickFlow替代yfinance] 获取数据: {symbols}, start={start}, end={end}")
    try:
        import tickflow as tf
    except ImportError:
        print("⚠️ TickFlow 未安装，降级到原始 yfinance")
        return _orig_download(symbols, start=start, end=end, **kwargs)

    # 处理 symbols 可能是字符串或列表
    if isinstance(symbols, str):
        sym_list = [symbols]
    else:
        sym_list = list(symbols)

    # 确定日期范围
    if end is None:
        end = datetime.now().strftime('%Y-%m-%d')
    if start is None:
        # 默认取近 1 年数据（适应策略回测）
        start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    all_data = {}
    for sym in sym_list:
        # TickFlow 需要类似 '000001.SH' 格式，假设传入的就是标准格式
        try:
            df = tf.free().klines.get(sym, start_date=start, end_date=end)
            if df is not None and not df.empty:
                # 转换列名：open->Open, high->High, low->Low, close->Close, volume->Volume
                df_renamed = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low',
                    'close': 'Close', 'volume': 'Volume'
                })
                # 设置日期索引
                if 'date' in df_renamed.columns:
                    df_renamed.set_index('date', inplace=True)
                # 确保数据类型为 float
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_renamed.columns:
                        df_renamed[col] = pd.to_numeric(df_renamed[col], errors='coerce')
                all_data[sym] = df_renamed
            else:
                print(f"⚠️ TickFlow 未获取到 {sym} 的数据，尝试降级")
                # 降级：用原始 yfinance 获取该标的
                fallback = _orig_download(sym, start=start, end=end, **kwargs)
                if fallback is not None and not fallback.empty:
                    all_data[sym] = fallback
        except Exception as e:
            print(f"⚠️ TickFlow 获取 {sym} 失败: {e}，降级到原始 yfinance")
            try:
                fallback = _orig_download(sym, start=start, end=end, **kwargs)
                if fallback is not None and not fallback.empty:
                    all_data[sym] = fallback
            except:
                pass

    if not all_data:
        print("⚠️ 所有数据获取失败，降级到原始 yfinance 全局调用")
        return _orig_download(symbols, start=start, end=end, **kwargs)

    # 如果只有一个标的，返回单个 DataFrame
    if len(all_data) == 1:
        return list(all_data.values())[0]
    else:
        # 多个标的，构建 MultiIndex DataFrame（模仿 yfinance 的返回格式）
        # yfinance 返回的列是多级索引 (Ticker, Price)，我们简化处理，返回按 ticker 拼接的列
        # 更简单：返回一个字典，但 AlphaEvo 可能期望 DataFrame，我们拼接
        # 这里我们按列拼接，外层索引为 Ticker
        combined = pd.concat(all_data, axis=1)
        # 重新组织列 MultiIndex
        # 实际 yfinance 返回的是 (Ticker, Price) 多级索引，我们模仿
        # 但为了简单，我们返回普通 DataFrame，AlphaEvo 可能能适应
        return combined

# 替换 yfinance 模块中的 download
yf_orig.download = tickflow_download

# 同时替换 sys.modules 中的 yfinance，确保所有导入都生效
import yfinance
yfinance.download = tickflow_download
sys.modules['yfinance'] = yfinance

print("✅ AlphaEvo yfinance 补丁应用成功，将优先使用 TickFlow 免费日K数据，失败时降级到原始 yfinance")