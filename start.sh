#!/bin/bash
# Bilibili Toolkit API Server 启动脚本
# 环境变量:
#   BILI_TOOLKIT_TOKEN     - API认证令牌 (必须)
#   BILI_TOOLKIT_PORT      - 监听端口 (默认18020)
#   BILI_TOOLKIT_CONFIG    - config.json路径 (默认同目录)
#   BILI_TOOLKIT_SESSDATA  - B站登录cookie SESSDATA (必须)
#   BILI_TOOLKIT_BILI_JCT  - B站登录cookie bili_jct
#   BILI_TOOLKIT_BUVID3    - B站登录cookie buvid3
cd "$(dirname "$0")"

export BILI_TOOLKIT_TOKEN="${BILI_TOOLKIT_TOKEN:?请设置 BILI_TOOLKIT_TOKEN 环境变量}"
export BILI_TOOLKIT_SESSDATA="${BILI_TOOLKIT_SESSDATA:?请设置 BILI_TOOLKIT_SESSDATA 环境变量}"
export BILI_TOOLKIT_PORT="${BILI_TOOLKIT_PORT:-18020}"
export BILI_TOOLKIT_CONFIG="${BILI_TOOLKIT_CONFIG:-$(pwd)/config.json}"

exec python3 api_server.py
