#!/usr/bin/env python3
"""
增量更新 DSA 数据库：为候选股票补充历史日线数据（最多 days 天）
如果数据库已存在数据，则只追加缺失部分。
支持多数据源自动降级（由 DSA 的 DataProvider 处理）。
"""
import sys
import os
import argparse
import pandas as pd
from pathlib import Path

# 添加 DSA 项目路径到 sys.path，以便导入其模块
sys.path.insert(0, os.path.join(os.environ.get('WORK_DIR', '.'), 'daily_stock_analysis'))

from data_provider import DataProvider
from src.storage import DatabaseManager  # 假设存在数据库管理类，若无则使用 sqlite3 直接操作

def update_stock_data(stock_codes, days=365, db_path=None):
    """
    为股票代码列表更新历史日线数据
    """
    provider = DataProvider()  # 会使用 DATA_SOURCE_PRIORITY 配置
    db = DatabaseManager(db_path) if db_path else DatabaseManager()

    end_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)  # 截止到昨日
    start_date = end_date - pd.Timedelta(days=days)

    for code in stock_codes:
        # 检查数据库中该股票的最新日期
        latest = db.get_latest_date(code)
        if latest and latest >= end_date:
            print(f"{code} 数据已最新，跳过")
            continue
        # 下载缺失部分（从 latest+1 到 end_date）
        if latest:
            start = latest + pd.Timedelta(days=1)
        else:
            start = start_date
        print(f"正在获取 {code} 从 {start} 到 {end_date} 的数据...")
        try:
            df = provider.get_daily_data(code, start_date=start, end_date=end_date)
            if df is not None and not df.empty:
                db.insert_daily_data(code, df)
                print(f"{code} 数据更新成功（{len(df)} 条）")
            else:
                print(f"{code} 获取数据为空")
        except Exception as e:
            print(f"获取 {code} 数据失败: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stocks-file', required=True, help='CSV 文件路径，包含股票代码列（列名: code）')
    parser.add_argument('--days', type=int, default=365, help='历史天数')
    args = parser.parse_args()

    # 读取股票列表
    df = pd.read_csv(args.stocks_file)
    if 'code' not in df.columns:
        print("CSV 文件必须包含 'code' 列")
        sys.exit(1)
    codes = df['code'].dropna().unique().tolist()
    print(f"需要更新的股票数量: {len(codes)}")

    # 设置数据库路径（与 DSA 项目保持一致）
    work_dir = os.environ.get('WORK_DIR', '.')
    db_path = os.path.join(work_dir, 'daily_stock_analysis', 'data', 'stock_analysis.db')
    update_stock_data(codes, args.days, db_path)

if __name__ == '__main__':
    main()