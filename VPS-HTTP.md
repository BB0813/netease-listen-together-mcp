# VPS HTTP 一起听方案（参考实现）

## 定位

当前仓库的 `server.py` 实现的是**桌面客户端 + CDP 方案**。本文是另一条路线的参考实现文档：在**无网易云桌面客户端**的环境（Linux / VPS）下，通过网易云 HTTP API 实现部分一起听能力。

本文整理 VPS-HTTP 方案的实现思路、关键接口流程和踩坑记录，供需要适配无桌面环境的用户参考。文中示例基于 HTTP 接口封装思路整理，`netease_request`、`get_csrf`、`get_room_state`、`report_list`、`report_play` 等为示例中的辅助封装，用于说明如何构造对应请求，调用方式见详解。

> **更新说明**：本项目（`BB0813/netease-listen-together-mcp`）已经在 `server.py` 中原生集成了该纯 HTTP 方案！在 Linux / Docker 环境下自动无缝启用，无需额外适配或安装桌面客户端，开箱即用。

## 1. 适用场景

- VPS 没有桌面环境、没有网易云桌面客户端，无法使用 CDP 进入客户端内部控制播放器。
- HTTP API 模式只依赖网易云 HTTP API，跨平台运行，不需要安装客户端，也不要求运行 Chrome/Chromium。
- 它操作的是云端一起听房间状态（如加入房间、列表同步、切歌等），实际声音播放仍由房间中的活跃客户端负责。

## 2. 环境要求

- Python 运行环境（标准库即可发起 HTTP 请求）
- 网易云登录 Cookie：浏览器登录 `https://music.163.com`，复制 `MUSIC_U` 和 `__csrf`，组合成 `NETEASE_COOKIE`
- HTTP 请求能力（携带有效 Cookie 和 CSRF）

不需要：网易云桌面客户端、CDP、Node.js。

## 3. 已验证能力

- 接受已有的一起听邀请（仅支持作为被邀请方）
- 获取房间信息与播放列表
- 向房间添加歌曲
- 发送切歌 / GOTO 命令

## 4. 核心流程与代码

下面先给出各步骤共用的最底层 HTTP 请求函数。读取房间、同步列表和切歌的具体封装分别放在对应小节，不提前重复。

### 4.0 通用 HTTP 请求函数

网易云这几个接口接收的是 `application/x-www-form-urlencoded` 表单，不是 JSON body。两个 `command/report` 接口的具体封装见 4.4 和 4.5。

- 表单外层只放 `roomId`、`commandInfo` 和 `csrf_token`；
- `commandInfo` 的值才是序列化后的 JSON 字符串；
- **不要**把 `commandType`、`targetSongId`、`clientSeq` 等字段平铺到表单外层，否则通常返回 HTTP 400。

```python
import json
import os
import time
import urllib.parse
import urllib.request

COOKIE = os.environ["NETEASE_COOKIE"]


def get_csrf():
    for part in COOKIE.split(";"):
        part = part.strip()
        if part.startswith("__csrf="):
            return part.split("=", 1)[1]
    return ""


def netease_request(path, form):
    csrf = get_csrf()
    body = urllib.parse.urlencode({**form, "csrf_token": csrf}).encode()
    request = urllib.request.Request(
        "https://music.163.com" + path
        + "?csrf_token=" + urllib.parse.quote(csrf),
        data=body,
        headers={
            "Cookie": COOKIE,
            "Referer": "https://music.163.com/",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


```

`room_id` 必须使用当前一起听房间的真实 `roomId`：可从接受邀请的返回值、已有房间状态或客户端当前一起听状态取得。不要把示例值写死，也不要新建另一个房间来替代当前房间。

### 4.1 接受邀请

从有效邀请中取得 `room_id` 和 `inviter_id`，调用接受接口：

```python
result = netease_request(
    "/api/listen/together/play/invitation/accept",
    {
        "roomId": str(room_id),
        "inviterId": str(inviter_id),
    },
)
accepted = result.get("code") == 200
```

### 4.2 读取房间状态

通过 `/sync/playlist/get` 读取当前播放命令、列表版本和播放列表：

```python
def get_room_state(room_id):
    result = netease_request(
        "/api/listen/together/sync/playlist/get",
        {"roomId": str(room_id)},
    )
    if result.get("code") != 200:
        raise RuntimeError(result)
    return result["data"]


state = get_room_state(room_id)               # /sync/playlist/get 的 data
play_command = state["playCommand"]
playlist = state["playlist"]

former = str(play_command["targetSongId"])   # 当前房间目标歌曲
seq = int(play_command.get("clientSeq", 0))
versions = [dict(v) for v in playlist.get("version", [])]
play_mode = playlist.get("playMode", "ORDER_LOOP")

display_items = playlist.get("displayList", {}).get("result", [])
display_list = [
    str(item.get("songId") if isinstance(item, dict) else item)
    for item in display_items
]
current_index = display_list.index(former) if former in display_list else 0
```

这里得到的关键变量是：

- `versions`：列表版本（每个用户各持一个版本号）
- `display_list`：房间展示列表中的歌曲 ID
- `play_mode`：播放模式
- `current_index`：当前歌曲下标

### 4.3 version 递增逻辑（关键踩坑点）

`version` 不能原样复用服务器返回值。必须**递增当前发送账号对应的版本号**，否则服务器可能返回 `200`，但另一端会把它当作旧列表而不重新同步：

```python
for v in versions:
    if str(v.get("userId")) == str(my_user_id):
        v["version"] = int(v.get("version", 0)) + 1
        break
else:
    versions.append({"userId": int(my_user_id), "version": 1})
```

- 递增的对象是**发送方账号自己的版本号**，不是所有用户的版本。
- 如果账号第一次参与，`version` 为 1 新增一条。
- 复用未递增的 `version` 是两端列表不同步的最常见原因。

### 4.4 ADD 列表同步

目标歌曲不在 `display_list` 时，必须先递增版本发送 `ADD`，**等待另一端同步后**再发送 `GOTO`：

```python
def report_list(room_id, command):
    result = netease_request(
        "/api/listen/together/sync/list/command/report",
        {
            "roomId": str(room_id),
            "commandInfo": json.dumps(
                command, ensure_ascii=False, separators=(",", ":")
            ),
        },
    )
    if result.get("code") != 200 or not result.get("data", {}).get("result"):
        raise RuntimeError(result)
    return result


target = str(target_song_id)

if target not in display_list:
    report_list(room_id, {                    # /sync/list/command/report
        "commandType": "ADD",
        "version": versions,                  # 递增后的版本
        "playMode": play_mode,
        "anchorSongId": former,
        "anchorPosition": current_index,
        "randomList": [target],
        "displayList": [target],
    })
    time.sleep(2)
```

### 4.5 GOTO 播放控制

列表同步完成后，发送切歌命令：

```python
def report_play(room_id, command):
    result = netease_request(
        "/api/listen/together/play/command/report",
        {
            "roomId": str(room_id),
            # 关键：GOTO 命令必须序列化后放入 commandInfo。
            "commandInfo": json.dumps(
                command, ensure_ascii=False, separators=(",", ":")
            ),
        },
    )
    if result.get("code") != 200 or not result.get("data", {}).get("result"):
        raise RuntimeError(result)
    return result


report_play(room_id, {                        # /play/command/report
    "commandType": "GOTO",
    "progress": 0,
    "playStatus": "PLAY",
    "formerSongId": former,
    "targetSongId": target,
    "clientSeq": seq + 1,
})
```

### 4.6 REPLACE 修复说明

如果错误版本曾造成"服务器列表已有目标歌曲、另一端列表却没有"，应：

1. 先用**递增版本的 `REPLACE`** 重新上报完整列表，或退出后重新加入房间；
2. 再继续切歌。

注意：`/api/listen/together/sync/notice` 是客户端恢复房间后的同步完成通知，**不是**推送新列表所需步骤。

## 5. 限制

- **HTTP API 无法完全替代桌面客户端**。声音由房间中保持活跃的手机或客户端播放；手机退后台、锁屏或长时间未操作后，仍会继续播放当前歌曲，但不再接收房间命令。
- **无法仅依赖 HTTP API 主动创建并维持完整的发起方房间**。纯 API 建房和发送邀请虽然可能返回 `200`，但目前无法维持可正常加入的有效房间；该方案仅支持作为**被邀请方**。
- HTTP API 方案不能用于未加入一起听时的普通播放，也不会让 VPS 本机发出声音。
- Cookie、CSRF 或服务器 IP 变化可能触发登录失效或风控；VPS IP 与常用登录 IP 差异很大时，账号操作风险更高。

## 6. 与桌面客户端模式区别

| | 桌面客户端模式 | HTTP API 模式 |
|---|---|---|
| 是否需要客户端 | 需要网易云桌面客户端 | 不需要 |
| 是否需要 CDP | 需要（Electron/Chromium 本地调试端口） | 不需要 |
| 运行环境 | macOS 等有桌面客户端的环境 | Linux / VPS 等无桌面环境 |
| 能力范围 | 完整客户端控制（本地播放、建房间、邀请、切歌等） | 仅云端一起听：接受邀请、同步列表、切歌；不能主动建房，不能本地播放 |
