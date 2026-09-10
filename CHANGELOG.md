# Changelog

## v2.0.0

### 新增

- **多方言支持**：`--dialect mysql|postgres|sqlite`，包含各自的标识符引用、字符串转义、类型映射与事务包装
- **CSV 输入**：支持 `.csv`（自动识别 utf-8 / utf-8-sig / gbk 编码），表名默认取文件名
- **流式处理**：边读边写，十万行级别不再需要把整表读进内存或拼接巨型 SQL 字符串
- **采样推断**：`--sample-size`（默认 1000 行）控制类型推断的成本
- **智能文本识别**：列名包含 手机/电话/编号/卡号/账号/编码/phone/code 等关键词时自动按文本处理（`--no-smart-text` 关闭）
- 新参数：`--limit`、`--add-id`、`--prefix` / `--suffix`、`--table-name`、`--sheet-table-names`、`--all-text`、`--no-create` / `--no-insert`、`--dry-run`、`-v/--verbose`、`-q/--quiet`、`--no-color`
- 行式彩色 CLI 输出：阶段/成功/警告/错误分色，结束打印每表行数与耗时汇总

### 修复

- `Sheet1` / `工作表1` 这类默认 sheet 名不再直接当表名，自动回退为文件名
- 手机号、订单号等字段不再被推断成数值而丢失前导零（`007` 保持为文本）
- 金额走 `Decimal` 计算精度，不再出现科学计数法或浮点精度丢失
- 字符串转义覆盖反斜杠、单引号、换行与控制字符，PostgreSQL 自动剔除 `\x00`

### 变更

- 运行时依赖由 `pandas` 改为 `openpyxl`（`.xls` 支持改为可选依赖 `xlrd`）
- 项目从单文件脚本重构为可安装的包 + `excel2sql` 命令（保留根目录兼容脚本）
- 新增测试套件（类型推断 / 方言 / 端到端 SQLite 执行校验）与 GitHub Actions CI

## v1.0.0

- 初始版本：Excel → MySQL SQL，自动类型推断、多 sheet、批量 INSERT
