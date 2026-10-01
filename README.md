# 光伏旁路组重接线试算台

一个用于比较光伏旁路组串并联接线方式的 Web 应用：录入 3～9 个旁路组和一份基线接线，程序穷举所有 1～3 串分组，精确计算旁路拐点、二次功率段内部极值和全局最大功率点，并在同一图中对比基线与最优接线的 P-V 曲线。

## 技术栈

- 后端：Python、FastAPI、SQLite
- 前端：原生 HTML / CSS / JavaScript，Canvas 绘制 P-V 曲线
- 部署：Docker Compose
- 精确计算：两位小数输入转换为 `fractions.Fraction`，搜索排序不依赖浮点比较

## 一键启动

```bash
docker compose up --build
```

启动后访问：

- Web 页面：<http://localhost:8000>
- OpenAPI 文档：<http://localhost:8000/docs>

停止：

```bash
docker compose down
```

SQLite 数据库保存在 Docker Volume `pv-trial-data` 中，容器重启后试算记录仍可打开。若要同时删除数据：

```bash
docker compose down -v
```

## 本地开发

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
PV_DB_PATH=./data/pv_trials.db uvicorn app.main:app --reload --port 8000
```

访问 <http://localhost:8000>。

运行测试：

```bash
python -m unittest discover -s tests -v
```

## 输入规则

- 旁路组数量：3～9 个。
- 组编号：唯一、非空，最多 32 个字符，可使用中英文、数字、下划线、点或连字符。
- 开路电压：`0 < Voc ≤ 100 V`，正数，最多两位小数。
- 短路电流：`0 < Isc ≤ 30 A`，正数，最多两位小数。
- 基线接线：1～3 个非空串；页面每行输入一串，组编号用空格、逗号、中文逗号、顿号或分号分隔；每组必须恰好出现一次。

非法参数返回 HTTP 400，并在页面显示中文错误。

## 电学模型

单个旁路组：

```text
Vg(I) = max(Voc × (1 − I / Isc), 0)
```

同一串内各组串联：

```text
Vstring(I) = Σ Vg(I)
```

串的 V-I 曲线在各组 Isc 处出现旁路拐点，是分段线性下降曲线。多串并联时共用端电压 `V`：

```text
Itotal(V) = Σ Istring(V)
P(V) = V × Itotal(V)
```

- 在端电压为 0 时，串电流取该串最小可行短路电流，即串联组中最大的 Isc；电流再高时所有组都被钳位到零电压。
- 端电压达到某串开路电压时，该串电流为零。
- 每个线性电流区间内功率为二次函数，程序同时检查区间内部顶点和所有旁路/开路拐点。

## 搜索与排序

枚举集合划分：每个旁路组分配到 1～3 个非空串之一。组在串内和串间均按编号字典序规范化，避免重复方案。9 个组时候选数为：

```text
S(9,1) + S(9,2) + S(9,3) = 1 + 255 + 3025 = 3281
```

最优接线按以下顺序选择：

1. 全局峰值功率最大；
2. 同功率先取串数少；
3. 再按组内及串间编号字典序；
4. 仍存在等高峰值时取较小峰值电压。

## API

### `POST /api/calculate`

请求示例：

```json
{
  "title": "示例",
  "groups": [
    {"id": "G1", "voc": "40.00", "isc": "10.00"},
    {"id": "G2", "voc": "40.00", "isc": "8.00"},
    {"id": "G3", "voc": "38.00", "isc": "9.00"}
  ],
  "baseline": [["G1", "G3"], ["G2"]]
}
```

返回基线、最优接线、曲线分段、峰值电压/电流/功率、候选数量和功率提升。

### 试算记录

- `GET /api/records`：记录列表
- `POST /api/records`：保存输入与结果
- `GET /api/records/{id}`：打开完整记录
- `DELETE /api/records/{id}`：删除记录

## 项目结构

```text
app/
├── main.py          # FastAPI 路由与异常处理
├── engine.py        # 电学模型、拐点、二次极值和穷举搜索
├── schemas.py       # 参数校验与序列化
├── database.py      # SQLite 持久化
└── static/          # 原生前端
tests/               # 单元和 API 测试
Dockerfile
docker-compose.yml
```
