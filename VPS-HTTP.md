# VPS HTTP 一起听方案（参考实现）

## 定位

当前仓库的 `server.py` 实现的是**桌面客户端 + CDP 方案**。本文是另一条路线的参考实现文档：在**无网易云桌面客户端**的环境（Linux / VPS）下，通过网易云 HTTP API 实现部分一起听能力。

本文整理 VPS-HTTP 方案的实现思路、关键接口流程和踩坑记录，供需要适配无桌面环境的用户参考。文中示例基于 HTTP 接口封装思路整理，`netease_request`、`get_csrf`、`get_room_state`、`report_list`、`report_play` 等为示例中的辅助封装，用于说明如何构造对应请求，调用方式见详解。

> 本文是方案参考，不代表当前仓库已经集成了该方案。能力以 HTTP API 实际可用接口为准。

> 使用 VPS 环境时，需要根据自己的 MCP 框架或应用结构，将本文中的 HTTP 请求流程封装并接入对应的工具调用逻辑；当前仓库的 `server.py` 仍主要面向桌面客户端 + CDP 方案。

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

注意：本文中的接口调用示例使用封装函数展示流程，并非直接发送给网易云接口的原始 HTTP 请求 body。

实际请求由封装函数负责补充 Cookie、csrf_token、roomId 等必要参数，并按照网易云接口要求构造完整请求。
请勿直接将示例中的参数对象作为 HTTP body 发送。
### 4.1 接受邀请

从有效邀请中取得 `room_id` 和 `inviter_id`，调用接受接口：

```python
csrf = get_csrf()
result = netease_request(
    "https://music.163.com/api/listen/together/play/invitation/accept"
    "?csrf_token=" + urllib.parse.quote(csrf),
    {
        "roomId": str(room_id),
        "inviterId": str(inviter_id),
        "csrf_token": csrf,
    },
)
accepted = result.get("code") == 200
```

### 4.2 读取房间状态

通过 `/sync/playlist/get` 读取当前播放命令、列表版本和播放列表：

```python
state = get_room_state(room_id)               # /sync/playlist/get
former = state.play_command["targetSongId"]   # 当前房间目标歌曲
seq = int(state.play_command.get("clientSeq", 0))
```

从 `state` 中还需要：

- `state.version`：列表版本（每个用户各持一个版本号）
- `state.display_list`：房间展示列表
- `state.play_mode`：播放模式
- `state.current_index`：当前歌曲下标

### 4.3 version 递增逻辑（关键踩坑点）

`version` 不能原样复用服务器返回值。必须**递增当前发送账号对应的版本号**，否则服务器可能返回 `200`，但另一端会把它当作旧列表而不重新同步：

```python
versions = [dict(v) for v in state.version]
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
target = str(target_song_id)

if target not in state.display_list:
    report_list(room_id, {                    # /sync/list/command/report
        "commandType": "ADD",
        "version": versions,                  # 递增后的版本
        "playMode": state.play_mode,
        "anchorSongId": former,
        "anchorPosition": state.current_index,
        "randomList": [target],
        "displayList": [target],
    })
    time.sleep(2)
```

### 4.5 GOTO 播放控制

列表同步完成后，发送切歌命令：

```python
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
