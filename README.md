# ML-CDAQ

《基于机器学习的成都市空气质量分析与预测系统设计与实现》前后端源码，系统版本 ML-CDAQ_V1.0。

前端使用 Vue 3、Vite、Element Plus 和 ECharts；后端使用 FastAPI、SQLite 和已冻结的 HistGradientBoostingRegressor，预测成都下一小时 PM2.5。

本仓库只提供源码、依赖锁定文件及启动脚本。真实数据、数据库、模型二进制和验收产物需从本地毕业设计交付目录另行取得；仅克隆源码无法启动完整后端。

## 目录

- `app/`：后端 API、数据查询、输入校验及模型服务。
- `frontend/`：前端页面、图表、API 调用与前端测试。
- `scripts/`：模型推理、数据库初始化及本地启动脚本。
- `tests/validate_chengdu_m4.py`：原后端验收测试源码，依赖本地实验产物。

## 运行条件

已验收环境为 Python 3.12.14、Node.js 24.19.0、pnpm 11.25.0。后端依赖版本见 `app/requirements.txt`，前端版本见 `frontend/pnpm-lock.yaml`。建议使用与冻结环境一致的版本加载模型。

在仓库根目录恢复以下原始冻结产物，保持文件名与相对路径：

```text
data/processed/成都空气质量基线数据.csv
outputs/models/最终模型.joblib
outputs/models/最终预处理器.joblib
outputs/models/模型元数据.json
outputs/models/模型冻结记录.json
outputs/modeling/M3验收状态.json
```

数据库可恢复 `data/system/成都空气质量系统.db`，或通过下方初始化命令从冻结基线创建。后端会验证基线和模型哈希，缺失或不符时拒绝启动。joblib 只加载本项目可信的冻结产物。

## Windows 本地启动

在仓库根目录安装后端依赖并初始化查询库：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app/requirements.txt
.\.venv\Scripts\python.exe scripts/init_system_database.py
```

安装前端依赖：

```powershell
Set-Location frontend
pnpm install --frozen-lockfile
Set-Location ..
```

在两个终端分别启动：

```powershell
.\.venv\Scripts\python.exe scripts/run_backend.py
```

```powershell
Set-Location frontend
pnpm dev
```

前端：<http://127.0.0.1:5173>；后端接口文档：<http://127.0.0.1:8000/docs>。Vite 将 `/api` 请求代理到本机后端。

也可在根目录指定本机运行时，使用已有一键启动脚本；按回车停止该脚本启动的进程：

```powershell
.\scripts\run_system.ps1 -Python (Join-Path $PWD '.venv/Scripts/python.exe') -Node (Get-Command node).Source
```

## 前端构建和测试

```powershell
Set-Location frontend
pnpm test
pnpm build
```

后端验收测试额外依赖 `outputs/modeling/M3监督学习矩阵.csv`、`outputs/analysis/M2预测样本可用性索引.csv` 及原验收文件；不属于纯源码安装后的独立测试。不要对已通过的阶段重复运行验收脚本。

## 数据和预测边界

历史数据来自 QuotSoft 成都城市级小时空气质量，源标签范围为 2020-01-01 至 2026-09-26；58537 条小时记录，其中 58337 条 PM2.5 有效记录。时间保持无时区的源标签，不声明 UTC 或 UTC+8；不是官方实时监测服务。

冻结模型版本为 `成都PM25_1H_V1_20261005`，使用 18 个原始特征、55 个编码特征预测下一小时 PM2.5。缺少必要历史特征时返回错误，不自动补值。AQI 和气象数据不进入默认模型输入。测试集曾用于探索分析，测试指标不宣称完全盲测。
