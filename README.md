# bili-tool
注:本项目由ai编写，我未参与编写
B站综合工具包 — 搜索视频、搜索番剧、提取弹幕、评论区、UP主信息、热搜榜。
基于 [bilibili-api-python](https://github.com/Nemo2011/bilibili-api) (400+ API) 构建，包含 CLI 工具和 REST API 服务器。

## 功能

| 功能 | CLI | API |
|------|-----|-----|
| 搜索视频 | `python main.py search "关键词"` | `POST /api/search` |
| 搜索番剧（自动过滤预告/PV） | `python main.py bangumi "番剧名"` | `POST /api/bangumi` |
| 提取弹幕（视频/番剧） | `python main.py danmaku --ssid 43164` | `POST /api/danmaku` |
| 视频详细信息 | `python main.py info BV1xxx` | `POST /api/info` |
| 评论区 | `python main.py comments BV1xxx` | `POST /api/comments` |
| UP主信息 | `python main.py user 12345` | `POST /api/user` |
| 热搜榜 | `python main.py hot` | `POST /api/hot` |

## 安装

```bash
# 安装依赖
pip install bilibili-api-python curl_cffi

# 或用 venv（推荐）
python3 -m venv venv
source venv/bin/activate
pip install bilibili-api-python curl_cffi
```

## CLI 使用

```bash
# 搜索视频
python main.py search "Python教程" --limit 5 --order click

# 搜索番剧（无需登录，自动过滤预告/PV/主题曲）
python main.py bangumi "孤独摇滚"
python main.py bangumi "曾经有勇士" --show-eps

# 提取弹幕
python main.py danmaku --bvid BV1xxx                     # 视频弹幕
python main.py danmaku --ssid 43164 -ep 1                 # 番剧第1集弹幕
python main.py danmaku --ssid 43164                       # 全集弹幕
python main.py danmaku --bvid BV1xxx --export dm.csv      # 导出CSV
python main.py danmaku --bvid BV1xxx --export-xml dm.xml  # 导出XML

# 视频信息
python main.py info BV1xxx

# 评论区（需要登录才能翻页）
python main.py comments BV1xxx --pages 0 --no-sub --export comments.csv

# UP主信息
python main.py user 523995133

# 热搜榜
python main.py hot
```

## REST API Server

纯 asyncio HTTP 服务器（无 uvicorn 依赖），延迟导入，空闲仅 ~16MB 内存(仅参考)。

### 启动

```bash
# 必须设置环境变量
export BILI_TOOLKIT_TOKEN="your_api_token"
export BILI_TOOLKIT_SESSDATA="your_sessdata"       # B站登录cookie
export BILI_TOOLKIT_BILI_JCT="your_bili_jct"       # B站登录cookie
export BILI_TOOLKIT_BUVID3="your_buvid3"           # B站登录cookie

# 启动
python api_server.py

# 或用启动脚本
chmod +x start.sh
./start.sh
```

### Systemd 服务

```bash
sudo cp bilibili-api.service /etc/systemd/system/
# 编辑服务文件，填入环境变量（注意：%要写成%%）
sudo systemctl daemon-reload
sudo systemctl enable --now bilibili-api
```

### 接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/search | 搜索视频 | ✅ |
| POST | /api/bangumi | 搜索番剧（自动过滤预告） | ✅ |
| POST | /api/danmaku | 提取弹幕（视频/番剧） | ✅ |
| POST | /api/info | 视频详细信息 | ✅ |
| POST | /api/comments | 评论区 | ✅ |
| POST | /api/user | UP主信息 | ✅ |
| POST | /api/hot | 热搜榜 | ✅ |
| GET | /api/health | 健康检查 | ❌ |

认证方式：`Authorization: Bearer <BILI_TOOLKIT_TOKEN>`

访问未定义路径返回 HTML 使用文档（无需认证）。

### 调用示例

```bash
TOKEN="your_token"

# 搜索番剧
curl -X POST http://127.0.0.1:18020/api/bangumi \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"keyword":"孤独摇滚"}'

# 提取弹幕
curl -X POST http://127.0.0.1:18020/api/danmaku \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ssid":43164,"episode":1,"limit":100}'

# 热搜榜
curl -X POST http://127.0.0.1:18020/api/hot \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | CLI 工具（搜索/番剧/弹幕/评论/下载/用户/热搜） |
| `api_server.py` | REST API 服务器（纯 asyncio，环境变量配置） |
| `start.sh` | API 启动脚本 |
| `bilibili-api.service` | Systemd 服务模板 |
| `config.json` | 登录 cookie（可选，环境变量优先） |
| `config.json.example` | 配置模板 |

## 配置

敏感信息全部通过 `BILI_TOOLKIT_*` 环境变量注入。

| 环境变量 | 必须 | 说明 |
|----------|------|------|
| `BILI_TOOLKIT_TOKEN` | ✅ | API 认证令牌 |
| `BILI_TOOLKIT_SESSDATA` | ✅* | B站登录 cookie（番剧弹幕等需要） |
| `BILI_TOOLKIT_BILI_JCT` | | B站登录 cookie |
| `BILI_TOOLKIT_BUVID3` | | B站登录 cookie |
| `BILI_TOOLKIT_PORT` | | 监听端口，默认 18020 |
| `BILI_TOOLKIT_CONFIG` | | config.json 路径（fallback） |

## 番剧搜索说明

- `search_type=media_bangumi` **无需 cookie**（2026-06 实测）
- 返回：评分、集数、season_id、分集列表、类型、地区等
- **自动过滤**预告/PV/主题曲，只返回正片分集
- 部分番剧因 B站无版权搜不到（如进击的巨人、我推的孩子）

## 代码参考

- **[bilibili-api-python](https://github.com/Nemo2011/bilibili-api)** — 核心依赖，400+ B站 API，处理 WBI 签名、反爬、异步
- **[bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)** — API 文档参考

## License

MIT
