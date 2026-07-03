#!/bin/bash
set -e

WORK_DIR=${WORK_DIR:-/home/runner/work/quant-workspace}
DSA_REPO="https://github.com/ZhuLinsen/daily_stock_analysis.git"
ALPHAEVO_REPO="https://github.com/ZhuLinsen/alphaevo.git"

mkdir -p $WORK_DIR

clone_or_pull() {
    local repo_url=$1
    local target_dir=$2
    if [ -d "$target_dir/.git" ]; then
        echo "🔄 更新 $target_dir ..."
        cd $target_dir && git pull
    else
        echo "📦 克隆 $target_dir ..."
        git clone --depth 1 $repo_url $target_dir
    fi
}

clone_or_pull $DSA_REPO "$WORK_DIR/daily_stock_analysis"
clone_or_pull $ALPHAEVO_REPO "$WORK_DIR/alphaevo"

echo "📦 安装 daily_stock_analysis 依赖..."
cd $WORK_DIR/daily_stock_analysis
pip install -r requirements.txt

echo "📦 安装 AlphaEvo 依赖..."
cd $WORK_DIR/alphaevo
pip install -e ".[data-yfinance]" || pip install -e "."