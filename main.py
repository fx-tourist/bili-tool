#!/usr/bin/env python3
"""
Bilibili Toolkit v2 - 基于 bilibili-api-python 的B站综合工具包
支持: 搜索视频、搜索番剧、提取弹幕、下载视频、查看评论区、查看UP主信息、点赞数等

用法:
  python main.py search <关键词>              搜索视频
  python main.py bangumi <关键词>             搜索番剧/国创
  python main.py danmaku --bvid <BV号>        提取视频弹幕
  python main.py danmaku --ssid <season_id>   提取番剧弹幕
  python main.py info <BV号>                  查看视频信息
  python main.py comments <BV号>              查看评论区
  python main.py download <BV号>              下载视频
  python main.py user <UID>                   查看UP主信息
  python main.py user-videos <UID>            查看UP主视频列表
  python main.py login                        扫码登录
  python main.py hot                          查看热搜
"""
import sys
import os
import asyncio
import argparse
import time
import json

from bilibili_api import video, user, comment, search, hot, rank, login_v2, bangumi, Credential


CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_credential():
    config = load_config()
    c = config.get("credential", {})
    if c.get("sessdata"):
        return Credential(
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


# ==================== 登录 ====================

async def cmd_login(args):
    """扫码登录"""
    qr = login_v2.QrCodeLogin()
    print("生成二维码中...")
    await qr.generate_qrcode()
    print("\n请使用B站APP扫描上方二维码登录")
    print("等待扫码...", end="", flush=True)

    import asyncio as aio
    for _ in range(120):  # 最多等2分钟
        await aio.sleep(2)
        state = await qr.check_state()
        if state == login_v2.QrCodeLoginEvents.DONE:
            cred = qr.get_credential()
            config = load_config()
            config["credential"] = {
                "sessdata": cred.sessdata,
                "bili_jct": cred.bili_jct,
                "buvid3": cred.buvid3,
                "dedeuserid": cred.dedeuserid,
            }
            save_config(config)
            print(f"\n[✓] 登录成功! Cookie已保存到 {CONFIG_FILE}")
            return
        elif state == login_v2.QrCodeLoginEvents.TIMEOUT:
            print("\n[!] 二维码已过期，请重新运行 login")
            return
        elif state == login_v2.QrCodeLoginEvents.CONF:
            print(" 已扫码，等待确认...", end="", flush=True)
        else:
            print(".", end="", flush=True)

    print("\n[!] 等待超时")


# ==================== 搜索 ====================

async def cmd_search(args):
    """搜索视频"""
    keyword = " ".join(args.keyword)
    print(f"搜索: {keyword}\n")

    result = await search.search_by_type(
        keyword=keyword,
        search_type=search.SearchObjectType.VIDEO,
        order_type=search.OrderVideo.TOTALRANK if not args.order else {
            "pubdate": search.OrderVideo.PUBDATE,
            "click": search.OrderVideo.CLICK,
            "dm": search.OrderVideo.DM,
            "scores": search.OrderVideo.SCORES,
        }.get(args.order, search.OrderVideo.TOTALRANK),
        page=args.page,
    )

    videos = result.get("result", [])
    if not videos:
        print("未找到结果")
        return

    print(f"{'='*80}")
    print(f"{'序号':<4} {'标题':<40} {'UP主':<12} {'播放':<10} {'时长':<8} {'BV号'}")
    print(f"{'-'*80}")

    for i, v in enumerate(videos[:args.limit], 1):
        title = v.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
        title = title[:38] + ".." if len(title) > 40 else title
        author = (v.get("author") or "")[:10]
        play = format_num(v.get("play", 0))
        duration = v.get("duration", "")
        bvid = v.get("bvid", "")
        print(f"{i:<4} {title:<40} {author:<12} {play:<10} {duration:<8} {bvid}")

    print(f"{'='*80}")
    print(f"共 {result.get('numResults', '?')} 条结果")


# ==================== 搜索番剧 ====================

async def cmd_bangumi(args):
    """搜索番剧/国创"""
    keyword = " ".join(args.keyword)
    print(f"搜索番剧: {keyword}\n")

    result = await search.search_by_type(
        keyword=keyword,
        search_type=search.SearchObjectType.BANGUMI,
        page=args.page,
    )

    items = result.get("result", [])
    if not items:
        print("未找到结果")
        return

    for i, item in enumerate(items[:args.limit], 1):
        title = item.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
        org_title = item.get("org_title", "").replace('<em class="keyword">', "").replace("</em>", "")
        score_info = item.get("media_score", {})
        score = score_info.get("score", "-")
        score_count = score_info.get("user_count", 0)
        ep_size = item.get("ep_size", "?")
        season_id = item.get("season_id", "")
        stype = item.get("season_type_name", "")
        areas = item.get("areas", "")
        styles = item.get("styles", "")
        url = item.get("url", "")
        badges = " ".join(b["text"] for b in (item.get("badges") or []))
        index_show = item.get("index_show", "")

        print(f"[{i}] {title}", end="")
        if org_title and org_title != title:
            print(f"  ({org_title})", end="")
        print()
        if badges:
            print(f"    {badges}")
        print(f"    类型: {stype} | 地区: {areas} | 分类: {styles}")
        print(f"    评分: {score} ({score_count:,}人评) | {index_show or ep_size + '集'}")
        print(f"    season_id: {season_id} | {url}")

        # 显示分集列表（如果有 eps）
        eps = item.get("eps", [])
        if eps and args.show_eps:
            ep_limit = min(args.ep_limit, len(eps))
            ep_titles = []
            for ep in eps[:ep_limit]:
                t = ep.get("long_title") or ep.get("index_title") or ep.get("title", "")
                ep_titles.append(f"E{ep.get('title', '?')} {t}")
            print(f"    分集: {' | '.join(ep_titles)}", end="")
            if len(eps) > ep_limit:
                print(f" ... (共{len(eps)}集)")
            else:
                print()
        print()

    print(f"共 {result.get('numResults', '?')} 条结果")


# ==================== 弹幕提取 ====================

async def cmd_danmaku(args):
    """提取弹幕"""
    cred = get_credential()

    danmakus = []
    title = ""

    if args.ssid:
        # 番剧模式
        if not cred:
            print("[!] 番剧弹幕需要登录，请先运行 login")
            return

        b = bangumi.Bangumi(ssid=args.ssid, credential=cred)
        meta = await b.get_meta()
        title = meta.get("media", {}).get("title", "未知番剧")

        episodes = await b.get_episodes()

        if args.episode:
            # 指定集数
            ep_idx = args.episode - 1
            if ep_idx < 0 or ep_idx >= len(episodes):
                print(f"[!] 集数超出范围 (1-{len(episodes)})")
                return
            target_eps = [episodes[ep_idx]]
        else:
            # 全部集数
            target_eps = episodes

        print(f"番剧: {title} ({len(episodes)}集)")
        if args.episode:
            print(f"提取第{args.episode}集弹幕...")
        else:
            print(f"提取全部{len(target_eps)}集弹幕...")

        for i, ep in enumerate(target_eps):
            ep_info = await ep.get_info()
            ep_title = ep_info.get("long_title") or ep_info.get("title", f"第{i+1}集")
            print(f"  第{i+1}集: {ep_title}...", end="", flush=True)
            dm_list = await ep.get_danmakus()
            print(f" {len(dm_list)}条")
            for dm in dm_list:
                dm._episode = i + 1
                dm._ep_title = ep_title
            danmakus.extend(dm_list)
            await asyncio.sleep(0.3)

    elif args.bvid:
        # 视频模式
        v = video.Video(bvid=args.bvid, credential=cred)
        info = await v.get_info()
        title = info["title"]
        cid = info.get("cid")

        print(f"视频: {title}")
        print(f"提取弹幕...", end="", flush=True)
        danmakus = await v.get_danmakus(cid=cid)
        print(f" {len(danmakus)}条")
    else:
        print("[!] 请指定 --bvid 或 --ssid")
        return

    if not danmakus:
        print("无弹幕数据")
        return

    # 排序
    if args.sort == "time":
        danmakus.sort(key=lambda d: d.dm_time)
    elif args.sort == "send":
        danmakus.sort(key=lambda d: d.send_time)

    # 导出
    if args.export:
        import csv
        with open(args.export, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if args.ssid and not args.episode:
                writer.writerow(["集数", "集名", "时间(秒)", "弹幕", "颜色", "模式", "字号", "发送时间"])
            else:
                writer.writerow(["时间(秒)", "弹幕", "颜色", "模式", "字号", "发送时间"])

            for dm in danmakus:
                send_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(dm.send_time)) if dm.send_time else ""
                if args.ssid and not args.episode:
                    writer.writerow([
                        getattr(dm, "_episode", ""),
                        getattr(dm, "_ep_title", ""),
                        f"{dm.dm_time:.2f}",
                        dm.text,
                        dm.color,
                        dm.mode,
                        dm.font_size,
                        send_time_str,
                    ])
                else:
                    writer.writerow([
                        f"{dm.dm_time:.2f}",
                        dm.text,
                        dm.color,
                        dm.mode,
                        dm.font_size,
                        send_time_str,
                    ])
        print(f"\n[✓] 已导出 {len(danmakus)} 条弹幕到 {args.export}")
        return

    # 导出XML
    if args.export_xml:
        if args.bvid:
            v = video.Video(bvid=args.bvid, credential=cred)
            info = await v.get_info()
            xml_data = await v.get_danmaku_xml(cid=info.get("cid"))
        else:
            # 番剧模式，手动拼XML
            xml_parts = ['<?xml version="1.0" encoding="UTF-8"?><i>']
            for dm in danmakus:
                esc_text = dm.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                xml_parts.append(f'<d p="{dm.dm_time:.2f},{dm.mode},{dm.font_size},{int(dm.color, 16) if dm.color != "special" else 0},{int(dm.send_time)},0,0,0,0">{esc_text}</d>')
            xml_parts.append("</i>")
            xml_data = "\n".join(xml_parts).encode("utf-8")

        with open(args.export_xml, "wb") as f:
            f.write(xml_data)
        print(f"\n[✓] 已导出XML弹幕到 {args.export_xml} ({len(xml_data)} 字节)")
        return

    # 终端显示
    print(f"\n{'='*70}")
    if args.ssid and not args.episode:
        print(f"{'集数':<4} {'时间':>8} {'弹幕'}")
    else:
        print(f"{'序号':<4} {'时间':>8} {'弹幕'}")
    print(f"{'-'*70}")

    display_list = danmakus[:args.limit]
    for i, dm in enumerate(display_list, 1):
        time_str = f"{int(dm.dm_time//60):02d}:{dm.dm_time%60:05.2f}"
        text = dm.text[:50] + ".." if len(dm.text) > 52 else dm.text
        if args.ssid and not args.episode:
            ep = getattr(dm, "_episode", "?")
            print(f"E{ep:<3} {time_str:>8} {text}")
        else:
            print(f"{i:<4} {time_str:>8} {text}")

    print(f"{'='*70}")
    print(f"共 {len(danmakus)} 条弹幕", end="")
    if len(danmakus) > args.limit:
        print(f" (显示前{args.limit}条，用 --limit 调整或 --export 导出全部)")
    else:
        print()


# ==================== 视频信息 ====================

async def cmd_info(args):
    """查看视频信息"""
    v = video.Video(bvid=args.bvid)
    info = await v.get_info()
    stat = info["stat"]

    tags = await v.get_tags()

    print(f"\n{'='*60}")
    print(f"标题: {info['title']}")
    print(f"BV号: {info['bvid']}  AV号: {info['aid']}")
    print(f"UP主: {info['owner']['name']} (UID: {info['owner']['mid']})")
    print(f"发布时间: {format_time(info['pubdate'])}")
    print(f"时长: {info['duration']//60}分{info['duration']%60}秒")

    print(f"\n📊 数据:")
    print(f"  播放: {format_num(stat['view'])}  弹幕: {format_num(stat['danmaku'])}  评论: {format_num(stat['reply'])}")
    print(f"  点赞: {format_num(stat['like'])}  投币: {format_num(stat['coin'])}  收藏: {format_num(stat['favorite'])}  分享: {format_num(stat['share'])}")

    pages = info.get("pages", [])
    if len(pages) > 1:
        print(f"\n📑 分P ({len(pages)}P):")
        for p in pages[:20]:
            dur = f"{p['duration']//60}:{p['duration']%60:02d}"
            print(f"  P{p['page']}: {p['part']} ({dur})")
        if len(pages) > 20:
            print(f"  ... 还有 {len(pages)-20} P")

    if tags:
        print(f"\n🏷️ 标签: {', '.join([t['tag_name'] for t in tags[:10]])}")

    if info.get("desc"):
        print(f"\n📝 简介: {info['desc'][:200]}")
    print(f"{'='*60}")


# ==================== 评论区 ====================

async def cmd_comments(args):
    """查看评论区"""
    cred = get_credential()
    v = video.Video(bvid=args.bvid, credential=cred)
    info = await v.get_info()
    oid = info["aid"]

    print(f"获取 {info['title'][:40]} 的评论...\n")

    order = comment.OrderType.TIME if args.mode == 2 else comment.OrderType.LIKE

    all_comments = []
    offset = ""
    fetch_all = args.pages == 0  # --pages 0 表示抓全部
    max_count = args.max if args.max > 0 else (args.pages * 20 if not fetch_all else float("inf"))

    while True:
        print(f"获取评论...", end=" ")
        try:
            c = await comment.get_comments_lazy(
                oid=oid,
                type_=comment.CommentResourceType.VIDEO,
                offset=offset,
                order=order,
                credential=cred,
            )
        except Exception as e:
            print(f"失败: {e}")
            break

        replies = c.get("replies") or []
        cursor = c.get("cursor", {})

        if not replies:
            print("无更多评论")
            break

        all_comments.extend(replies)
        print(f"已获取 {len(all_comments)} 条")

        # 获取二级评论 (用Comment类的get_sub_comments，每个最多抓3页)
        if args.sub:
            for r in replies:
                sub_count = r.get("rcount", 0)
                if sub_count > 0:
                    try:
                        cm = comment.Comment(
                            oid=oid,
                            type_=comment.CommentResourceType.VIDEO,
                            rpid=r["rpid"],
                            credential=cred,
                        )
                        sub_page = 1
                        max_sub_pages = 3  # 每个一级评论最多抓3页子评论(60条)
                        while sub_page <= max_sub_pages:
                            sub_data = await cm.get_sub_comments(page_index=sub_page, page_size=20)
                            sub_replies = sub_data.get("replies") or []
                            if not sub_replies:
                                break
                            all_comments.extend(sub_replies)
                            sub_page_info = sub_data.get("page", {})
                            if sub_page * 20 >= sub_page_info.get("count", 0):
                                break
                            sub_page += 1
                            await asyncio.sleep(0.3)
                    except Exception:
                        pass
                    await asyncio.sleep(0.3)

        # 检查是否到底
        if cursor.get("is_end"):
            break

        offset = cursor.get("pagination_reply", {}).get("next_offset", "")
        if not offset:
            break

        if not fetch_all and len(all_comments) >= max_count:
            break

        if args.max > 0 and len(all_comments) >= args.max:
            break

        await asyncio.sleep(0.5)

    print(f"\n共获取 {len(all_comments)} 条评论\n")

    # 打印评论
    print(f"{'='*70}")
    for i, r in enumerate(all_comments[:args.limit], 1):
        m = r["member"]
        like_str = f"👍{r['like']}" if r['like'] > 0 else ""
        vip_tag = " [大会员]" if m.get("vip", {}).get("vipStatus") else ""
        time_str = format_time(r["ctime"])
        level = m.get("level_info", {}).get("current_level", 0)

        # UP主点赞标记
        up_tag = ""
        if r.get("up_action", {}).get("like"):
            up_tag = " [UP主❤]"

        print(f"{i}. {m['uname']} Lv.{level}{vip_tag}{up_tag} {like_str}  {time_str}")
        print(f"   {r['content']['message'][:100]}")
        if r.get("rcount", 0) > 0:
            print(f"   └─ {r['rcount']}条回复")
        print()

    if len(all_comments) > args.limit:
        print(f"... 还有 {len(all_comments) - args.limit} 条评论")
    print(f"{'='*70}")

    # 导出CSV
    if args.export:
        import csv
        filepath = args.export if args.export.endswith(".csv") else f"{args.export}.csv"
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["用户名", "等级", "内容", "时间", "点赞", "回复数", "IP属地"])
            for r in all_comments:
                m = r["member"]
                try:
                    ip = r.get("reply_control", {}).get("location", "")[5:]
                except:
                    ip = ""
                writer.writerow([
                    m["uname"],
                    m.get("level_info", {}).get("current_level", 0),
                    r["content"]["message"],
                    format_time(r["ctime"]),
                    r["like"],
                    r.get("rcount", 0),
                    ip,
                ])
        print(f"\n[✓] 评论已导出: {filepath}")


# ==================== 下载 ====================

async def cmd_download(args):
    """下载视频"""
    v = video.Video(bvid=args.bvid, credential=get_credential())
    info = await v.get_info()

    print(f"视频: {info['title']}")
    print(f"UP主: {info['owner']['name']}")
    stat = info["stat"]
    print(f"播放: {format_num(stat['view'])} | 点赞: {format_num(stat['like'])} | 投币: {format_num(stat['coin'])}")

    output_dir = args.output or "downloads"
    os.makedirs(output_dir, exist_ok=True)

    import re
    title = re.sub(r'[\\/:*?"<>|]', "_", info["title"])

    print(f"\n下载中...")
    try:
        path = await v.download_video(
            page=video.VideoDownloadPage(info["pages"][0]["cid"]),
            out_dir=output_dir,
            stream_type=video.VideoStreamType.DASH,
        )
        print(f"\n[✓] 下载完成: {path}")
    except Exception as e:
        print(f"\n[!] 下载失败: {e}")
        print("提示: 登录后可下载更高画质。运行 python main.py login")


# ==================== 用户 ====================

async def cmd_user(args):
    """查看UP主信息"""
    u = user.User(args.mid)

    # 并发获取用户信息和关系统计
    uinfo_task = u.get_user_info()
    relation_task = u.get_relation_info()

    uinfo = await uinfo_task
    relation = await relation_task

    vip_str = ""
    if uinfo.get("vip", {}).get("status"):
        vip_str = f" [大会员]"

    official = uinfo.get("official", {})
    official_str = ""
    if official.get("role"):
        title = official.get("title", "")
        official_str = f" ({title})" if title else ""

    print(f"\n{'='*50}")
    print(f"昵称: {uinfo['name']}{vip_str}{official_str}")
    print(f"UID:  {uinfo['mid']}")
    print(f"等级: Lv.{uinfo.get('level', 0)}")
    print(f"性别: {uinfo.get('sex', '')}")
    print(f"签名: {uinfo.get('sign', '')}")

    print(f"\n📊 数据:")
    follower = relation.get("follower", 0) if relation else 0
    following = relation.get("following", 0) if relation else 0
    print(f"  粉丝: {format_num(follower)}  关注: {following}")

    live = uinfo.get("live_room")
    if live and live.get("roomid"):
        status = "🔴 直播中" if live.get("liveStatus") else "未开播"
        print(f"\n🎮 直播间: {live.get('title', '')} ({status})")
        print(f"  https://live.bilibili.com/{live.get('roomid')}")

    print(f"  主页: https://space.bilibili.com/{uinfo['mid']}")
    print(f"{'='*50}")


async def cmd_user_videos(args):
    """查看UP主视频列表"""
    u = user.User(args.mid)
    order = user.VideoOrder.PUBDATE if args.order == "pubdate" else user.VideoOrder.CLICK

    data = await u.get_videos(pn=args.page, ps=30, order=order)
    vlist = data.get("list", {}).get("vlist", [])

    if not vlist:
        print("暂无视频")
        return

    print(f"\n{'='*70}")
    print(f"{'序号':<4} {'标题':<35} {'播放':<10} {'弹幕':<8} {'时长':<8}")
    print(f"{'-'*70}")
    for i, v in enumerate(vlist, 1):
        title = v["title"][:33] + ".." if len(v["title"]) > 35 else v["title"]
        play = format_num(v.get("play", 0))
        danmaku = format_num(v.get("video_review", 0))
        print(f"{i:<4} {title:<35} {play:<10} {danmaku:<8} {v.get('length', ''):<8}")
    print(f"{'='*70}")


# ==================== 热搜 ====================

async def cmd_hot(args):
    """查看B站热搜"""
    result = await hot.get_hot_videos()
    videos = result.get("list", [])

    if not videos:
        print("获取热搜失败")
        return

    print(f"\n{'='*60}")
    print("B站热门视频")
    print(f"{'-'*60}")
    for i, item in enumerate(videos[:30], 1):
        title = item.get("title", "")[:40]
        owner = item.get("owner", {}).get("name", "")
        play = format_num(item.get("stat", {}).get("view", 0))
        bvid = item.get("bvid", "")
        print(f"{i:>2}. [{play:>8}] {title:<40} {owner:<12} {bvid}")
    print(f"{'='*60}")


# ==================== Main ====================

def main():
    parser = argparse.ArgumentParser(
        description="Bilibili Toolkit v2 - 基于 bilibili-api-python 的B站综合工具包（视频搜索、番剧搜索、弹幕提取、评论抓取、视频下载）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py login                        扫码登录
  python main.py search Python教程            搜索视频
  python main.py bangumi 孤独摇滚             搜索番剧
  python main.py danmaku --bvid BV1xxx        提取视频弹幕
  python main.py danmaku --ssid 43164 -ep 1   提取番剧第1集弹幕
  python main.py info BV1Jgf6YvE8e            查看视频信息
  python main.py comments BV1Jgf6YvE8e        查看评论
  python main.py download BV1Jgf6YvE8e        下载视频
  python main.py user 523995133               查看UP主
  python main.py hot                          B站热搜
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # login
    subparsers.add_parser("login", help="扫码登录")

    # search
    p = subparsers.add_parser("search", help="搜索视频")
    p.add_argument("keyword", nargs="+", help="搜索关键词")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.add_argument("--limit", type=int, default=20, help="结果数量")
    p.add_argument("--order", default="", choices=["", "pubdate", "click", "dm", "scores"])

    # bangumi
    p = subparsers.add_parser("bangumi", help="搜索番剧/国创/影视（自动过滤预告/PV）")
    p.add_argument("keyword", nargs="+", help="搜索关键词")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.add_argument("--limit", type=int, default=20, help="结果数量")
    p.add_argument("--show-eps", action="store_true", default=True, help="显示分集列表(默认开启)")
    p.add_argument("--no-eps", dest="show_eps", action="store_false", help="不显示分集")
    p.add_argument("--ep-limit", type=int, default=6, help="分集显示数量")

    # danmaku
    p = subparsers.add_parser("danmaku", help="提取弹幕（支持视频和番剧，自动过滤预告）")
    p.add_argument("--bvid", help="视频BV号")
    p.add_argument("--ssid", type=int, help="番剧season_id")
    p.add_argument("--episode", "-ep", type=int, help="指定集数(从1开始)")
    p.add_argument("--sort", default="time", choices=["time", "send"], help="排序: time=视频时间, send=发送时间")
    p.add_argument("--limit", type=int, default=50, help="终端显示数量")
    p.add_argument("--export", help="导出CSV文件路径")
    p.add_argument("--export-xml", help="导出XML弹幕文件路径")

    # info
    p = subparsers.add_parser("info", help="查看视频信息")
    p.add_argument("bvid", help="BV号")

    # comments
    p = subparsers.add_parser("comments", help="查看评论区")
    p.add_argument("bvid", help="BV号")
    p.add_argument("--mode", type=int, default=2, choices=[2, 3], help="2=最新, 3=热门")
    p.add_argument("--pages", type=int, default=5, help="最大页数, 0=抓取全部(小心超时)")
    p.add_argument("--limit", type=int, default=20, help="终端显示数量")
    p.add_argument("--max", type=int, default=0, help="最大抓取数量, 0=不限(配合--pages 0)")
    p.add_argument("--sub", action="store_true", default=True, help="包含二级评论")
    p.add_argument("--no-sub", dest="sub", action="store_false")
    p.add_argument("--export", help="导出CSV文件路径")

    # download
    p = subparsers.add_parser("download", help="下载视频")
    p.add_argument("bvid", help="BV号")
    p.add_argument("--output", "-o", default="downloads", help="输出目录")

    # user
    p = subparsers.add_parser("user", help="查看UP主信息")
    p.add_argument("mid", type=int, help="用户UID")

    # user-videos
    p = subparsers.add_parser("user-videos", help="查看UP主视频列表")
    p.add_argument("mid", type=int, help="用户UID")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.add_argument("--order", default="pubdate", choices=["pubdate", "click"])

    # hot
    subparsers.add_parser("hot", help="查看B站热搜")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "login": cmd_login,
        "search": cmd_search,
        "bangumi": cmd_bangumi,
        "danmaku": cmd_danmaku,
        "info": cmd_info,
        "comments": cmd_comments,
        "download": cmd_download,
        "user": cmd_user,
        "user-videos": cmd_user_videos,
        "hot": cmd_hot,
    }

    func = cmd_map.get(args.command)
    if func:
        asyncio.run(func(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
