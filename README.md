# excel2sql

[![CI](https://github.com/Moxin1044/excel2sql/actions/workflows/ci.yml/badge.svg)](https://github.com/Moxin1044/excel2sql/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

把 Excel / CSV 变成 SQL 文件：自动推断字段类型，生成 `CREATE TABLE` + 批量 `INSERT`，支持 **MySQL / PostgreSQL / SQLite** 三种方言。

流式读写，十万行级别的表格也能在低内存下跑完。

---

## ✨ 特性

| 能力 | 说明 |
|---|---|
| 自动类型推断 | `INT` / `BIGINT` / `DECIMAL(p,s)` / `DOUBLE` / `BOOLEAN` / `DATE` / `DATETIME` / `TIME` / `VARCHAR(n)` / `TEXT` |
| 采样推断 | 默认只看前 1000 行（`--sample-size` 可调），大表不再逐列全表扫描 |
| 文本列不截断 | 文本列默认使用 `TEXT`（不限长），采样之外的长值也不会被截断；需要紧凑 schema 时用 `--varchar` 全文件扫描一次长度，精确给出 `VARCHAR(n)` |
| 精度安全 | 用 `Decimal` 计算精度，金额不会变成科学计数法；**超过 15 位或带前导零的数字自动按文本处理**（订单号、身份证、手机号） |
| 智能文本识别 | 列名含「手机 / 电话 / 编号 / 卡号 / 账号 / 编码 / phone / code…」时自动按文本处理（`--no-smart-text` 关闭） |
| 多方言 | `--dialect mysql`（默认）/ `postgres` / `sqlite`，各自的标识符引号、转义规则与类型映射 |
| 流式处理 | 边读边写，10 万行不需要把整表读进内存，也不需要把 SQL 拼成一个大字符串 |
| 多输入格式 | `.xlsx` / `.xls`（需 `xlrd`）/ `.csv`（自动识别 utf-8 / gbk 编码） |
| 多 Sheet | 每个 sheet 一张表；`Sheet1` 这类默认名自动回退成文件名；重名自动加后缀 |
| 表名控制 | `--sheet-table-names 用户表:users`、`--table-name`、`--prefix` / `--suffix` |
| 行式彩色输出 | 阶段 / 成功 / 警告 / 错误分色，非 TTY 或 `--no-color` 自动降级；结束打印每表行数与耗时汇总 |
| 实用开关 | `--drop`、`--add-id`（自增主键）、`--limit`、`--no-create` / `--no-insert`、`--all-text`、`--dry-run` |

---

## 📦 安装

```bash
pip install .                 # 基础（含 openpyxl）
pip install ".[xls]"          # 额外支持 .xls（依赖 xlrd）
pip install ".[dev]"          # 开发（pytest）
```

推荐用 [pipx](https://pypa.github.io/pipx/) 安装成全局命令：

```bash
pipx install .
```

---

## 🚀 快速开始

```bash
# 最基本的用法：Excel → MySQL SQL（输出同名 .sql）
excel2sql 数据.xlsx

# 指定输出与方言
excel2sql 数据.xlsx -o out.sql --dialect postgres

# CSV 也可以
excel2sql people.csv --dialect sqlite -o people.sql

# 只转指定 sheet，并加自增主键
excel2sql 数据.xlsx --sheet 用户表,订单 --add-id

# 每表最多 1000 行，生成 DROP TABLE
excel2sql 数据.xlsx --limit 1000 --drop

# 只看推断结果，不写文件
excel2sql 数据.xlsx --dry-run --verbose
```

生成的 SQL 长这样：

```sql
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 数据.xlsx → 用户表
CREATE TABLE IF NOT EXISTS `用户表` (
  `姓名` VARCHAR(32),
  `手机号` TEXT,
  `余额` DECIMAL(8,2),
  `注册日期` DATE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `用户表` (`姓名`, `手机号`, `余额`, `注册日期`) VALUES
('张三', '13800138000', 12.50, '2023-01-05'),
('李四', '007', 100, '2023-02-06');

SET FOREIGN_KEY_CHECKS = 1;
```

---

## ⚙️ 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `inputs` | 输入文件（`.xlsx` / `.xls` / `.csv`，可多个） | 必填 |
| `-o, --output` | 输出 SQL 路径 | 输入文件名 + `.sql` |
| `--dialect` | `mysql` / `postgres` / `sqlite` | `mysql` |
| `--sheet` | 仅转换指定 sheet（逗号分隔） | 全部 |
| `--sheet-table-names` | sheet 与表名映射，如 `用户表:users,订单:orders` | — |
| `--table-name` | 单 sheet 时强制指定表名 | — |
| `--prefix` / `--suffix` | 表名前缀 / 后缀 | 空 |
| `--batch-size` | 每条 INSERT 的行数 | `500` |
| `--limit` | 每张表最多写入的行数 | `0`（不限） |
| `--sample-size` | 类型推断采样行数 | `1000` |
| `--varchar` | 文本列精确使用 `VARCHAR(n)`（全文件扫描一次长度；慢一些但 schema 更紧凑） | 关（文本列用 `TEXT`） |
| `--add-id` | 追加自增主键 `id` | 关 |
| `--all-text` | 所有字段按文本处理 | 关 |
| `--no-smart-text` | 关闭「手机号/编号类列名按文本」 | 关 |
| `--drop` | 生成 `DROP TABLE IF EXISTS` | 关 |
| `--no-create` / `--no-insert` | 只生成其中一部分 | 关 |
| `--dry-run` | 只解析与推断，不写文件 | 关 |
| `-v, --verbose` | 打印每列推断出的类型 | 关 |
| `-q, --quiet` | 静默（只显示错误） | 关 |
| `--no-color` | 关闭颜色 | 关 |
| `--version` | 打印版本 | — |

---

## 🧠 类型推断规则

| 数据情况 | 推断结果 |
|---|---|
| 全为整数，且绝对值 ≤ 2147483647 | `INT` |
| 全为整数，绝对值更大 | `BIGINT` |
| 含小数 | `DECIMAL(整数位+小数位, 小数位)`，小数位上限 6 |
| **带前导零**（如 `007`）或 **有效数字超过 15 位** | 文本（`VARCHAR` / `TEXT`） |
| 列名像手机号 / 编号 / 卡号 / 账号 / 编码 | 文本 |
| 全部可解析为日期 | `DATE`（全是零点的时间戳也会归为 `DATE`） |
| 全部可解析为日期时间 | `DATETIME` |
| `true/false`、`是/否`、布尔单元格 | `BOOLEAN`（MySQL 为 `TINYINT(1)`） |
| 类型混杂 | 文本 |
| 整列为空 | `VARCHAR(255)` |

`VARCHAR` 长度按 16 / 32 / 64 / 128 / 255 档位取整，超过 255 用 `TEXT`，超过 65535 用 `LONGTEXT`；**默认模式下文本列统一用 `TEXT`**（永不截断），加 `--varchar` 时才会做全文件长度扫描并输出精确的 `VARCHAR(n)`。

---

## 🗄 方言差异

| 项目 | MySQL | PostgreSQL | SQLite |
|---|---|---|---|
| 标识符 | `` `name` `` | `"name"` | `"name"` |
| 字符串转义 | `\'` + `\\` | `''`（标准字符串） | `''` |
| 布尔 | `TINYINT(1)`，值 `1/0` | `BOOLEAN`，值 `TRUE/FALSE` | `INTEGER`，值 `1/0` |
| 浮点 | `DOUBLE` | `DOUBLE PRECISION` | `REAL` |
| 时间 | `DATETIME` | `TIMESTAMP` | `TEXT` |
| 自增主键 | `INT AUTO_INCREMENT` | `BIGSERIAL` | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| 事务包装 | `SET FOREIGN_KEY_CHECKS=0/1` | `BEGIN; … COMMIT;` | `PRAGMA foreign_keys=OFF; BEGIN; … COMMIT;` |

> PostgreSQL 无法存储 `\x00`（NUL），转换时会自动剔除。

---

## 🔁 从 v1 升级

- 旧的 `python excel2sql.py 输入.xlsx` 仍然可用（兼容脚本保留在仓库根目录）
- 旧参数全部保留：`-o` / `--sheet` / `--charset` / `--engine` / `--batch-size` / `--drop`
- 行为改进：`Sheet1` 不再被当成表名（回退文件名）、手机号/编号不再被写成数值、金额精度不再丢失
- 依赖变轻：运行时只需要 `openpyxl`（v1 需要 pandas）

---

## 🧪 开发与测试

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

测试覆盖类型推断、三种方言的转义与类型映射，以及「生成 SQL → 用 SQLite 真实执行 → 读回校验」的端到端流程。

## 📄 License

MIT © 末心
