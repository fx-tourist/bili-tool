#!/usr/bin/env python3
"""
Bilibili Toolkit API Server (内存优化版)
纯 asyncio HTTP 服务器，无 uvicorn，延迟导入 bilibili_api

端口: 18020
认证: Bearer token (从 BILI_TOOLKIT_TOKEN 环境变量读取)

启动: python api_server.py
"""

import os
import sys
import gc
import json
import time
import asyncio
import logging
import weakref
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============ 配置 ============

AUTH_TOKEN = os.environ.get("BILI_TOOLKIT_TOKEN", "")
PORT = int(os.environ.get("BILI_TOOLKIT_PORT", "18020"))
CONFIG_FILE = os.environ.get("BILI_TOOLKIT_CONFIG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("bilibili-api")


# ============ 延迟导入 ============

_search = None
_video = None
_user = None
_comment = None
_hot = None
_bangumi = None
_Credential = None


def _lazy_import():
    """延迟导入 bilibili_api，只在首次请求时加载"""
    global _search, _video, _user, _comment, _hot, _bangumi, _Credential
    if _search is not None:
        return

    from bilibili_api import search, video, user, comment, hot, bangumi, Credential
    from bilibili_api.utils.network import request_settings
    _search = search
    _video = video
    _user = user
    _comment = comment
    _hot = hot
    _bangumi = bangumi
    _Credential = Credential

    # 西安VPS连B站API较慢，加大超时到120秒
    request_settings.set_timeout(120.0)

    gc.collect()


# ============ 工具函数 ============

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def get_credential():
    _lazy_import()
    # 环境变量优先
    sessdata = os.environ.get("BILI_TOOLKIT_SESSDATA", "")
    if sessdata:
        return _Credential(
            sessdata=sessdata,
            bili_jct=os.environ.get("BILI_TOOLKIT_BILI_JCT", ""),
            buvid3=os.environ.get("BILI_TOOLKIT_BUVID3", ""),
        )
    # fallback: config.json
    config = load_config()
    c = config.get("credential", {})
    if c.get("sessdata"):
        return _Credential(
            sessdata=c["sessdata"],
            bili_jct=c.get("bili_jct", ""),
            buvid3=c.get("buvid3", ""),
        )
    return None


def format_num(n):
    if n is None:
        return "N/A"
    if n >= 100000000:
        return f"{n/100000000:.1f}亿"
    elif n >= 10000:
        return f"{n/10000:.1f}万"
    return str(n)


def format_time(ts):
    if not ts:
        return "N/A"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


# ============ API 处理函数 ============


async def api_search(data):
    _lazy_import()
    keyword = data.get("keyword", "")
    if not keyword:
        return {"ok": False, "error": "缺少 keyword 参数"}

    page = data.get("page", 1)
    limit = data.get("limit", 20)
    order = data.get("order", "")

    order_map = {
        "pubdate": _search.OrderVideo.PUBDATE,
        "click": _search.OrderVideo.CLICK,
        "dm": _search.OrderVideo.DM,
        "scores": _search.OrderVideo.SCORES,
    }
    order_type = order_map.get(order, _search.OrderVideo.TOTALRANK)

    result = await _search.search_by_type(
        keyword=keyword,
        search_type=_search.SearchObjectType.VIDEO,
        order_type=order_type,
        page=page,
    )

    videos = result.get("result", [])
    items = []
    for v in videos[:limit]:
        items.append({
            "title": v.get("title", "").replace('<em class="keyword">', "").replace("</em>", ""),
            "author": v.get("author", ""),
            "play": v.get("play", 0),
            "play_fmt": format_num(v.get("play", 0)),
            "duration": v.get("duration", ""),
            "bvid": v.get("bvid", ""),
        })

    return {"ok": True, "total": result.get("numResults", 0), "items": items}


async def api_bangumi(data):
    _lazy_import()
    keyword = data.get("keyword", "")
    if not keyword:
        return {"ok": False, "error": "缺少 keyword 参数"}

    page = data.get("page", 1)
    limit = data.get("limit", 10)

    result = await _search.search_by_type(
        keyword=keyword,
        search_type=_search.SearchObjectType.BANGUMI,
        page=page,
    )

    items = []
    for item in (result.get("result", []) or [])[:limit]:
        score_info = item.get("media_score", {})
        eps = item.get("eps", [])
        items.append({
            "title": item.get("title", "").replace('<em class="keyword">', "").replace("</em>", ""),
            "org_title": item.get("org_title", "").replace('<em class="keyword">', "").replace("</em>", ""),
            "season_id": item.get("season_id", ""),
            "type": item.get("season_type_name", ""),
            "areas": item.get("areas", ""),
            "styles": item.get("styles", ""),
            "score": score_info.get("score", 0),
            "score_count": score_info.get("user_count", 0),
            "ep_size": item.get("ep_size", 0),
            "index_show": item.get("index_show", ""),
            "url": item.get("url", ""),
            "badges": [b["text"] for b in (item.get("badges") or [])],
            "eps": [
                {"title": ep.get("title", ""), "long_title": ep.get("long_title", ""), "id": ep.get("id", "")}
                for ep in eps
            ],
        })

    return {"ok": True, "total": result.get("numResults", 0), "items": items}


async def api_danmaku(data):
    _lazy_import()
    bvid = data.get("bvid")
    ssid = data.get("ssid")
    episode = data.get("episode")
    limit = data.get("limit", 50)
    sort = data.get("sort", "time")

    if not bvid and not ssid:
        return {"ok": False, "error": "请指定 bvid 或 ssid"}

    cred = get_credential()
    danmakus = []
    title = ""

    if ssid:
        if not cred:
            return {"ok": False, "error": "番剧弹幕需要登录，请配置 config.json"}
        b = _bangumi.Bangumi(ssid=ssid, credential=cred)
        meta = await b.get_meta()
        title = meta.get("media", {}).get("title", "未知番剧")
        episodes = await b.get_episodes()

        if episode:
            ep_idx = episode - 1
            if ep_idx < 0 or ep_idx >= len(episodes):
                return {"ok": False, "error": f"集数超出范围 (1-{len(episodes)})"}
            target_eps = [episodes[ep_idx]]
        else:
            target_eps = episodes

        for i, ep in enumerate(target_eps):
            ep_info = await ep.get_info()
            ep_title = ep_info.get("long_title") or ep_info.get("title", f"第{i+1}集")
            dm_list = await ep.get_danmakus()
            for dm in dm_list:
                danmakus.append({
                    "text": dm.text,
                    "time": round(dm.dm_time, 2),
                    "send_time": int(dm.send_time) if dm.send_time else 0,
                    "color": dm.color,
                    "mode": dm.mode,
                    "episode": i + 1,
                    "ep_title": ep_title,
                })
            await asyncio.sleep(0.3)

    elif bvid:
        v = _video.Video(bvid=bvid, credential=cred)
        info = await v.get_info()
        title = info["title"]
        cid = info.get("cid")
        dm_list = await v.get_danmakus(cid=cid)
        for dm in dm_list:
            danmakus.append({
                "text": dm.text,
                "time": round(dm.dm_time, 2),
                "send_time": int(dm.send_time) if dm.send_time else 0,
                "color": dm.color,
                "mode": dm.mode,
            })

    if sort == "time":
        danmakus.sort(key=lambda d: d["time"])
    elif sort == "send":
        danmakus.sort(key=lambda d: d["send_time"])

    return {"ok": True, "title": title, "total": len(danmakus), "items": danmakus[:limit]}


async def api_info(data):
    _lazy_import()
    bvid = data.get("bvid", "")
    if not bvid:
        return {"ok": False, "error": "缺少 bvid 参数"}

    v = _video.Video(bvid=bvid)
    info = await v.get_info()
    stat = info["stat"]

    return {
        "ok": True,
        "title": info["title"],
        "bvid": info["bvid"],
        "aid": info["aid"],
        "cid": info.get("cid"),
        "owner": {"mid": info["owner"]["mid"], "name": info["owner"]["name"]},
        "pubdate": format_time(info["pubdate"]),
        "duration": info["duration"],
        "desc": info.get("desc", ""),
        "stat": {
            "view": stat["view"], "danmaku": stat["danmaku"], "reply": stat["reply"],
            "like": stat["like"], "coin": stat["coin"], "favorite": stat["favorite"],
            "share": stat["share"],
        },
    }


async def api_comments(data):
    _lazy_import()
    bvid = data.get("bvid", "")
    if not bvid:
        return {"ok": False, "error": "缺少 bvid 参数"}

    mode = data.get("mode", 2)
    limit = data.get("limit", 20)
    max_count = data.get("max_count", 0)
    sub = data.get("sub", True)

    cred = get_credential()
    v = _video.Video(bvid=bvid, credential=cred)
    info = await v.get_info()
    aid = info["aid"]
    title = info["title"]

    comments_list = []
    offset = ""
    total_fetched = 0

    while True:
        c = await _comment.get_comments_lazy(
            oid=aid,
            type_=_comment.CommentResourceType.VIDEO,
            offset=offset,
            order=_comment.OrderType.TIME if mode == 2 else _comment.OrderType.LIKE,
            credential=cred,
        )

        replies = c.get("replies") or []
        if not replies:
            break

        for r in replies:
            msg = r.get("content", {}).get("message", "")
            uname = r.get("member", {}).get("uname", "")
            like = r.get("like", 0)
            rcount = r.get("rcount", 0)
            rpid = r.get("rpid", 0)

            comment_item = {
                "user": uname, "text": msg, "like": like,
                "sub_count": rcount, "sub_comments": [],
            }

            if sub and rcount > 0:
                cm = _comment.Comment(
                    oid=aid, type_=_comment.CommentResourceType.VIDEO,
                    rpid=rpid, credential=cred,
                )
                sub_result = await cm.get_sub_comments(page_index=1, page_size=20)
                for sr in (sub_result.get("replies") or [])[:5]:
                    comment_item["sub_comments"].append({
                        "user": sr.get("member", {}).get("uname", ""),
                        "text": sr.get("content", {}).get("message", ""),
                        "like": sr.get("like", 0),
                    })

            comments_list.append(comment_item)
            total_fetched += 1
            if max_count and total_fetched >= max_count:
                break

        if max_count and total_fetched >= max_count:
            break

        cursor = c.get("cursor", {})
        if cursor.get("is_end"):
            break
        offset = cursor.get("pagination_reply", {}).get("next_offset", "")
        if not offset:
            break
        await asyncio.sleep(0.3)

    return {"ok": True, "title": title, "total": len(comments_list), "items": comments_list[:limit]}


async def api_user(data):
    _lazy_import()
    mid = data.get("mid", 0)
    if not mid:
        return {"ok": False, "error": "缺少 mid 参数"}

    u = _user.User(mid)
    uinfo = await u.get_user_info()
    relation = await u.get_relation_info()

    vip = uinfo.get("vip", {})
    official = uinfo.get("official", {})
    follower = relation.get("follower", 0) if relation else 0
    following = relation.get("following", 0) if relation else 0

    return {
        "ok": True, "name": uinfo["name"], "mid": uinfo["mid"],
        "level": uinfo.get("level", 0), "sex": uinfo.get("sex", ""),
        "sign": uinfo.get("sign", ""), "follower": follower, "following": following,
        "vip": bool(vip.get("status")), "official": official.get("title", ""),
        "live_room": uinfo.get("live_room"),
        "url": f"https://space.bilibili.com/{uinfo['mid']}",
    }


async def api_hot(data):
    _lazy_import()
    try:
        result = await _hot.get_hot_videos()
        videos = result.get("list", [])[:30]
    except Exception as e:
        return {"ok": False, "error": str(e)}

    items = []
    for v in videos:
        items.append({
            "title": v.get("title", ""),
            "author": v.get("owner", {}).get("name", ""),
            "play": v.get("stat", {}).get("view", 0),
            "play_fmt": format_num(v.get("stat", {}).get("view", 0)),
            "bvid": v.get("bvid", ""),
        })

    return {"ok": True, "items": items}


# ============ 路由表 ============

ROUTES = {
    "/api/search": api_search,
    "/api/bangumi": api_bangumi,
    "/api/danmaku": api_danmaku,
    "/api/info": api_info,
    "/api/comments": api_comments,
    "/api/user": api_user,
    "/api/hot": api_hot,
}


# ============ HTTP 响应 ============


def _json_response(status, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode()
    headers = (
        f"HTTP/1.1 {status} OK\r\n"
        f"Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode()
    return headers + body


def _html_response(status, html):
    body = html.encode()
    headers = (
        f"HTTP/1.1 {status} OK\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode()
    return headers + body


# ============ API 文档 ============

API_DOCS = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Bilibili Toolkit API</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;background:#0d1117;color:#c9d1d9;line-height:1.6}
h1{color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:12px}
h2{color:#79c0ff;margin-top:32px}
h3{color:#d2a8ff}
code{background:#161b22;padding:2px 6px;border-radius:4px;font-size:14px;color:#79c0ff}
pre{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;border:1px solid #30363d}
pre code{background:none;padding:0;color:#c9d1d9}
.endpoint{background:#161b22;padding:16px;border-radius:8px;margin:12px 0;border-left:4px solid #58a6ff}
.method{color:#3fb950;font-weight:bold}
.path{color:#58a6ff;font-weight:bold}
.param{color:#ffa657}
hr{border:none;border-top:1px solid #30363d;margin:32px 0}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:bold;background:#238636;color:#fff}
table{width:100%;border-collapse:collapse;margin:12px 0}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid #30363d}
th{color:#58a6ff}
</style></head><body>
<h1>Bilibili Toolkit API</h1>
<p>B站综合工具API — 搜索视频、番剧、提取弹幕、评论区、UP主信息、热搜</p>
<p><span class="badge">POST</span> 所有接口均为 POST，Content-Type: application/json</p>
<p>认证: <code>Authorization: Bearer &lt;token&gt;</code></p>
<hr>
<h2>接口列表</h2>
<div class="endpoint"><h3><span class="method">POST</span> <span class="path">/api/search</span> — 搜索视频</h3>
<table><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr>
<tr><td class="param">keyword</td><td>string</td><td>✅</td><td>搜索关键词</td></tr>
<tr><td class="param">page</td><td>int</td><td></td><td>页码，默认1</td></tr>
<tr><td class="param">limit</td><td>int</td><td></td><td>结果数量，默认20</td></tr>
<tr><td class="param">order</td><td>string</td><td></td><td>pubdate/click/dm/scores</td></tr></table></div>
<div class="endpoint"><h3><span class="method">POST</span> <span class="path">/api/bangumi</span> — 搜索番剧</h3>
<table><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr>
<tr><td class="param">keyword</td><td>string</td><td>✅</td><td>搜索关键词</td></tr>
<tr><td class="param">page</td><td>int</td><td></td><td>页码，默认1</td></tr>
<tr><td class="param">limit</td><td>int</td><td></td><td>结果数量，默认10</td></tr></table></div>
<div class="endpoint"><h3><span class="method">POST</span> <span class="path">/api/danmaku</span> — 提取弹幕</h3>
<table><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr>
<tr><td class="param">bvid</td><td>string</td><td>二选一</td><td>视频BV号</td></tr>
<tr><td class="param">ssid</td><td>int</td><td>二选一</td><td>番剧season_id</td></tr>
<tr><td class="param">episode</td><td>int</td><td></td><td>集数，从1开始</td></tr>
<tr><td class="param">limit</td><td>int</td><td></td><td>返回条数，默认50</td></tr>
<tr><td class="param">sort</td><td>string</td><td></td><td>time/send</td></tr></table></div>
<div class="endpoint"><h3><span class="method">POST</span> <span class="path">/api/info</span> — 视频信息</h3>
<table><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr>
<tr><td class="param">bvid</td><td>string</td><td>✅</td><td>视频BV号</td></tr></table></div>
<div class="endpoint"><h3><span class="method">POST</span> <span class="path">/api/comments</span> — 评论区</h3>
<table><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr>
<tr><td class="param">bvid</td><td>string</td><td>✅</td><td>视频BV号</td></tr>
<tr><td class="param">mode</td><td>int</td><td></td><td>2=最新(默认)，3=热门</td></tr>
<tr><td class="param">limit</td><td>int</td><td></td><td>返回条数，默认20</td></tr>
<tr><td class="param">sub</td><td>bool</td><td></td><td>展开子评论，默认true</td></tr></table></div>
<div class="endpoint"><h3><span class="method">POST</span> <span class="path">/api/user</span> — UP主信息</h3>
<table><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr>
<tr><td class="param">mid</td><td>int</td><td>✅</td><td>用户UID</td></tr></table></div>
<div class="endpoint"><h3><span class="method">POST</span> <span class="path">/api/hot</span> — 热搜榜</h3><p>无参数</p></div>
<hr>
<h2>调用示例</h2>
<pre><code>curl -X POST https://bili.fucks.qzz.io/api/search -H "Authorization: Bearer &lt;token&gt;" -H "Content-Type: application/json" -d '{"keyword":"Python","limit":5}'</code></pre>
<pre><code>curl -X POST https://bili.fucks.qzz.io/api/bangumi -H "Authorization: Bearer &lt;token&gt;" -H "Content-Type: application/json" -d '{"keyword":"孤独摇滚"}'</code></pre>
<pre><code>curl -X POST https://bili.fucks.qzz.io/api/danmaku -H "Authorization: Bearer &lt;token&gt;" -H "Content-Type: application/json" -d '{"ssid":43164,"episode":1}'</code></pre>
<hr><p style="color:#8b949e">Bilibili Toolkit API · bilibili-api-python</p>
</body></html>"""


# ============ HTTP Handler ============


async def handle_client(reader, writer):
    """处理单个 HTTP 连接"""
    try:
        # 读取请求行
        request_line = await asyncio.wait_for(reader.readline(), timeout=10)
        if not request_line:
            writer.close()
            return

        parts = request_line.decode().strip().split()
        if len(parts) < 2:
            writer.close()
            return

        method = parts[0]
        path = parts[1].split("?")[0]

        # 读取 headers
        content_length = 0
        auth_token = ""
        accept = ""
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            if line == b"\r\n" or line == b"\n" or not line:
                break
            line_str = line.decode().strip().lower()
            if line_str.startswith("content-length:"):
                content_length = int(line_str.split(":")[1].strip())
            elif line_str.startswith("authorization: bearer "):
                auth_token = line_str[21:].strip()
            elif line_str.startswith("accept:"):
                accept = line_str[7:].strip()

        # 读取 body
        body = b""
        if content_length > 0:
            body = await asyncio.wait_for(reader.read(content_length), timeout=10)

        # 健康检查不需要认证
        if path == "/api/health":
            resp = _json_response(200, {"ok": True, "service": "bilibili-api", "status": "running"})
            writer.write(resp)
            await writer.drain()
            writer.close()
            return

        # 未定义路径 → 返回文档（不需要认证）
        if path not in ROUTES:
            resp = _html_response(200, API_DOCS)
            writer.write(resp)
            await writer.drain()
            writer.close()
            return

        # 认证检查
        if auth_token != AUTH_TOKEN:
            resp = _json_response(401, {"ok": False, "error": "Unauthorized"})
            writer.write(resp)
            await writer.drain()
            writer.close()
            return

        # API 路由
        if path in ROUTES and method == "POST":
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                resp = _json_response(400, {"ok": False, "error": "Invalid JSON"})
                writer.write(resp)
                await writer.drain()
                writer.close()
                return

            try:
                result = await ROUTES[path](data)
                resp = _json_response(200, result)
            except Exception as e:
                logger.error(f"API error: {e}", exc_info=True)
                resp = _json_response(500, {"ok": False, "error": str(e)})

            writer.write(resp)
            await writer.drain()
            writer.close()
            return

        # 非 POST 访问 API 端点
        if path in ROUTES:
            resp = _json_response(405, {"ok": False, "error": f"{path} 仅支持 POST"})
            writer.write(resp)
            await writer.drain()
            writer.close()
            return

    except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
        pass
    except Exception as e:
        logger.error(f"Handler error: {e}")
        try:
            writer.close()
        except:
            pass


# ============ Main ============

async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", PORT)
    print(f"🚀 Bilibili API Server 启动")
    print(f"   端口: {PORT}")
    print(f"   认证: Bearer {AUTH_TOKEN}")
    print(f"   文档: http://0.0.0.0:{PORT}/")
    print(f"   模式: 纯 asyncio (延迟导入)")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
