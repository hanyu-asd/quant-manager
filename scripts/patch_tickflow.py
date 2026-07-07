#!/usr/bin/env python3
"""
TickFlow 补丁 - 同时 patch 多个数据源类，优先使用 TickFlow 免费接口获取日线数据。
如果 TickFlow 失败，降级到原始数据源。
"""
import sys
import inspect
from typing import Optional

def apply_patch():
    """应用 TickFlow 补丁到 BaseFetcher 和 TushareFetcher"""
    print("🔄 开始应用 TickFlow 补丁...")

    try:
        # 1. 导入需要 patch 的类
        from data_provider.base import BaseFetcher
        from data_provider.tushare_fetcher import TushareFetcher

        # 尝试导入 AkshareFetcher（可能不存在）
        try:
            from data_provider.akshare_fetcher import AkshareFetcher
            has_akshare = True
        except ImportError:
            has_akshare = False

        # 2. 保存原始方法（避免递归调用）
        original_base_get = BaseFetcher.get_daily_data
        original_tushare_get = TushareFetcher.get_daily_data
        original_akshare_get = getattr(AkshareFetcher, 'get_daily_data', None) if has_akshare else None

        def patched_get_daily_data(self, symbol, start_date=None, end_date=None, **kwargs):
            """优先 TickFlow，失败则降级"""
            try:
                from tickflow import TickFlow
                import pandas as pd

                # 使用免费接口
                tf = TickFlow.free()
                # 获取最多 200 条历史日线（足够覆盖近期）
                df = tf.klines.get(
                    symbol=symbol,
                    period="1d",
                    count=200,
                    as_dataframe=True
                )

                if df is not None and not df.empty:
                    df = df.sort_values('trade_date')
                    # 日期过滤
                    if start_date:
                        df = df[df['trade_date'] >= start_date]
                    if end_date:
                        df = df[df['trade_date'] <= end_date]
                    if not df.empty:
                        print(f"✅ TickFlow 获取 {symbol} 成功: {len(df)} 条")
                        return df
                    else:
                        print(f"⚠️ TickFlow 返回数据但日期范围无匹配: {symbol}")
                else:
                    print(f"⚠️ TickFlow 返回空数据: {symbol}")
            except Exception as e:
                print(f"⚠️ TickFlow 获取 {symbol} 失败: {e}")

            # 降级到原始 BaseFetcher 方法
            print(f"⬇️ 降级到原始数据源: {symbol}")
            return original_base_get(self, symbol, start_date=start_date, end_date=end_date, **kwargs)

        # 3. 应用补丁到所有目标类
        BaseFetcher.get_daily_data = patched_get_daily_data
        TushareFetcher.get_daily_data = patched_get_daily_data
        if has_akshare and original_akshare_get is not None:
            AkshareFetcher.get_daily_data = patched_get_daily_data

        print("✅ TickFlow 补丁应用成功 (已 patch BaseFetcher, TushareFetcher, 以及可选的 AkshareFetcher)")
        return True

    except Exception as e:
        print(f"❌ TickFlow 补丁应用失败: {e}")
        return False


def verify_patch():
    """验证补丁是否真正生效"""
    try:
        from data_provider.base import BaseFetcher
        from data_provider.tushare_fetcher import TushareFetcher

        base_method = BaseFetcher.get_daily_data
        tushare_method = TushareFetcher.get_daily_data

        # 检查是否同一个函数对象
        if base_method is tushare_method:
            # 进一步检查函数名是否包含 "patched"
            if 'patched' in base_method.__name__:
                print("✅ 验证通过: BaseFetcher 和 TushareFetcher 均使用补丁方法")
                return True
            else:
                print("⚠️ 验证失败: 方法虽相同但名称不含 'patched'，可能补丁未正确应用")
                return False
        else:
            print("⚠️ 验证失败: BaseFetcher 和 TushareFetcher 的 get_daily_data 不是同一对象")
            return False
    except Exception as e:
        print(f"⚠️ 验证异常: {e}")
        return False


if __name__ == "__main__":
    success = apply_patch()
    if success:
        verify_patch()