# 量化投研管理系统

基于 daily_stock_analysis + AlphaSift + AlphaEvo 的统一管理仓库。

## 流水线流程
1. **AlphaSift 选股**（每日）→ 生成 `stock_pool_raw.csv`
2. **AlphaEvo 回测校验**（每日必选）→ 计算止盈止损，生成 `stock_pool_final.csv`
3. **daily_stock_analysis 分析推送**（每日）→ AI 报告 + 邮件发送
4. **AlphaEvo 策略进化**（条件触发：周五轻量进化 / 月首全局重构）

## 触发方式
- 自动：工作日北京时间 18:00
- 手动：Actions 页面点击 "Run workflow"

## 配置 Secrets
参考 [GitHub Secrets 清单](#) 配置所有密钥。