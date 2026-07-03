#!/bin/bash
set -e

WORK_DIR=${WORK_DIR:-/home/runner/work/quant-workspace}
DSA_REPO="https://github.com/ZhuLinsen/daily_stock_analysis.git"
ALPHAEVO_REPO="https://github.com/ZhuLinsen/alphaevo.git"
ALPHASIFT_REPO="https://github.com/ZhuLinsen/alphasift.git"

mkdir -p $WORK_DIR

clone_or_pull() {
    if [ -d "$2/.git" ]; then
        echo "🔄 更新 $2 ..."
        cd $2 && git pull
    else
        echo "📦 克隆 $2 ..."
        git clone --depth 1 $1 $2
    fi
}

clone_or_pull $DSA_REPO "$WORK_DIR/daily_stock_analysis"
clone_or_pull $ALPHAEVO_REPO "$WORK_DIR/alphaevo"
clone_or_pull $ALPHASIFT_REPO "$WORK_DIR/alphasift"

cd $WORK_DIR/daily_stock_analysis && pip install -r requirements.txt
cd $WORK_DIR/alphaevo && pip install -e ".[data-yfinance]" || pip install -e .
cd $WORK_DIR/alphasift && pip install -e . || pip install alphasift