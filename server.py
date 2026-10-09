#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.parse, threading, time
import bisect, re, sqlite3, subprocess

NETEASE_COOKIE = os.environ.get("NETEASE_COOKIE", "")
LYRIC_CACHE = {}
LYRIC_CACHE_LOCK = threading.Lock()
NETEASE_APP_PATH = '/Applications/NeteaseMusic.app'
NETEASE_BUNDLE_ID = 'com.netease.163music'
NETEASE_PROCESS_NAME = 'NeteaseMusic'
NETEASE_DEBUG_PORT = 9222
NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID = os.environ.get(
    'NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID', ''
)
MEDIAREMOTE_SCRIPT = r'''
ObjC.import("Foundation");
$.NSBundle.bundleWithPath("/System/Library/PrivateFrameworks/MediaRemote.framework/").load;
const Request = $.NSClassFromString("MRNowPlayingRequest");
const path = Request.localNowPlayingPlayerPath;
const client = path ? path.client : null;
const item = Request.localNowPlayingItem;
const metadata = item ? item.metadata : null;
function value(key) {
  if (!metadata) return null;
  try {
    const result = metadata.valueForKey(key);
    return result ? ObjC.unwrap(result) : null;
  } catch (_) {
    return null;
  }
}
JSON.stringify({
  app: client ? ObjC.unwrap(client.displayName) : null,
  bundleId: client ? ObjC.unwrap(client.bundleIdentifier) : null,
  title: value("title"),
  artist: value("trackArtistName"),
  album: value("albumName"),
  duration: Number(value("duration")),
  elapsedTime: Number(value("elapsedTime")),
  elapsedTimeTimestamp: Number(value("elapsedTimeTimestamp")),
  playbackRate: Number(value("playbackRate"))
});
'''

def get_now_playing():
    if sys.platform != 'darwin':
        return None, 'get_current_listening_context requires macOS'
    try:
        result = subprocess.run(
            ['osascript', '-l', 'JavaScript', '-e', MEDIAREMOTE_SCRIPT],
            capture_output=True, text=True, timeout=5, check=True
        )
        info = json.loads(result.stdout.strip() or '{}')
    except Exception as e:
        return None, 'Could not read macOS Now Playing: ' + str(e)
    if info.get('bundleId') != 'com.netease.163music':
        return None, 'NetEase Music is not the current Now Playing app.'
    if not info.get('title'):
        return None, 'NetEase Music has no current Now Playing item.'
    elapsed = float(info.get('elapsedTime') or 0)
    timestamp = float(info.get('elapsedTimeTimestamp') or 0)
    rate = float(info.get('playbackRate') or 0)
    if timestamp > 0 and rate > 0:
        timestamp_unix = timestamp + 978307200
        elapsed += max(0, time.time() - timestamp_unix) * rate
    duration = float(info.get('duration') or 0)
    if duration > 0:
        elapsed = min(elapsed, duration)
    info['elapsedTime'] = max(0, elapsed)
    return info, None

def _require_macos_client():
    if sys.platform != 'darwin':
        return 'This tool requires macOS.'
    if not os.path.isdir(NETEASE_APP_PATH):
        return 'NetEase Music is not installed at ' + NETEASE_APP_PATH + '.'
    return None

def _run_open(arguments):
    try:
        result = subprocess.run(
            ['/usr/bin/open'] + arguments,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    detail = (result.stderr or result.stdout or '').strip()
    return result.returncode == 0, detail

CDP_EVAL_SCRIPT = r'''
const ws = new WebSocket(process.argv[1]);
const expression = process.argv[2];
const awaitPromise = process.argv[3] === "1";
let finished = false;
ws.onopen = () => ws.send(JSON.stringify({
  id: 1,
  method: "Runtime.evaluate",
  params: {expression, returnByValue: true, awaitPromise}
}));
ws.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  finished = true;
  if (message.result && message.result.exceptionDetails) {
    const detail = message.result.exceptionDetails;
    console.error(detail.exception && detail.exception.description || detail.text);
    process.exitCode = 1;
  } else {
    console.log(JSON.stringify(message.result && message.result.result
      ? message.result.result.value : null));
  }
  ws.close();
};
ws.onerror = () => {
  if (finished) return;
  console.error("Could not connect to the NetEase Chromium debugger.");
  process.exitCode = 1;
};
'''

def _netease_cdp_target():
    try:
        with urllib.request.urlopen(
            'http://127.0.0.1:' + str(NETEASE_DEBUG_PORT) + '/json/list',
            timeout=1,
        ) as response:
            targets = json.loads(response.read().decode())
    except Exception:
        return None
    return next(
        (
            target.get('webSocketDebuggerUrl')
            for target in targets
            if target.get('type') == 'page'
            and target.get('url') == 'orpheus://orpheus/app.html'
        ),
        None,
    )

def _can_use_cdp():
    if sys.platform != 'darwin':
        return False
    try:
        return _netease_cdp_target() is not None or _ensure_netease_debug_client() is None
    except Exception:
        return False

def _ensure_netease_debug_client():
    if sys.platform != 'darwin':
        return 'NetEase debug client requires macOS.'
    if _netease_cdp_target():
        return None
    if subprocess.run(
        [
            '/usr/bin/pgrep', '-f',
            NETEASE_PROCESS_NAME + '.*--remote-debugging-port='
            + str(NETEASE_DEBUG_PORT),
        ],
        capture_output=True,
    ).returncode == 0:
        return 'NetEase Chromium debugger is temporarily unavailable.'
    try:
        subprocess.run(
            ['osascript', '-e', 'tell application "NeteaseMusic" to quit'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for _ in range(100):
            if subprocess.run(
                ['/usr/bin/pgrep', '-x', NETEASE_PROCESS_NAME],
                capture_output=True,
            ).returncode != 0:
                break
            time.sleep(0.1)
        else:
            return 'NetEase Music did not finish exiting before debug relaunch.'
        result = subprocess.run(
            [
                '/usr/bin/open', '-n', '-a', NETEASE_APP_PATH, '--args',
                '--remote-debugging-port=' + str(NETEASE_DEBUG_PORT),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    if result.returncode != 0:
        return (result.stderr or result.stdout or 'Could not launch NetEase Music.').strip()
    for _ in range(24):
        if _netease_cdp_target():
            return None
        time.sleep(0.25)
    return 'NetEase Music did not expose its local Chromium debugger.'

def _netease_cdp_eval(expression, await_promise=False):
    target = _netease_cdp_target()
    if not target:
        raise RuntimeError('NetEase Chromium debugger is unavailable.')
    result = subprocess.run(
        [
            'node', '-e', CDP_EVAL_SCRIPT, target, expression,
            '1' if await_promise else '0',
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return json.loads(result.stdout.strip() or 'null')

def _bootstrap_netease_webpack():
    return _netease_cdp_eval(r'''
(() => {
  if (!window.__codexWebpackRequire) {
    webpackJsonp.push([[-991337], {
      991337: function(module, exports, require) {
        window.__codexWebpackRequire = require;
      }
    }, [[991337]]]);
  }
  return Boolean(window.__codexWebpackRequire);
})()
''')

def _create_listen_together_in_client():
    expression = r'''
(async () => {
  const req = window.__codexWebpackRequire;
  const core = req(11).a;
  const util = req(58).c;
  const modalApi = req(28).default;
  const originalInvite = modalApi.listenTogetherInvite;
  const previousRoomId =
    (core.getStore()["async:listenTogether"].roomInfo || {}).roomId || "";
  modalApi.listenTogetherInvite = () => Promise.resolve({
    inviteFriendHandle: () => {}
  });
  try {
    await Promise.resolve(core.getDispatch()({
      type: "async:listenTogether/startListenTogether",
      payload: {target: "renew_invite", refer: "songplay_more"}
    }));
    let roomInfo = {};
    for (let attempt = 0; attempt < 24; attempt += 1) {
      roomInfo = core.getStore()["async:listenTogether"].roomInfo || {};
      if (
        roomInfo.roomId
        && roomInfo.creatorId
        && roomInfo.roomId !== previousRoomId
        && ["waiting", "togetherOwner"].includes(util.utilStatus)
        && util.heartbeatCounting != null
      ) break;
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    if (
      !roomInfo.roomId
      || !roomInfo.creatorId
      || roomInfo.roomId === previousRoomId
      || !["waiting", "togetherOwner"].includes(util.utilStatus)
      || util.heartbeatCounting == null
    ) {
      throw new Error("NetEase client did not finish creating an active room.");
    }
    return {
      status: util.utilStatus,
      roomId: roomInfo.roomId,
      roomInfo,
      heartbeatActive: true,
      storeStatus: core.getStore()["async:listenTogether"].status
    };
  } finally {
    modalApi.listenTogetherInvite = originalInvite;
  }
})()
'''
    return _netease_cdp_eval(expression, await_promise=True)

def _listen_together_client_state():
    return _netease_cdp_eval(r'''
(() => {
  const req = window.__codexWebpackRequire;
  const core = req(11).a;
  const util = req(58).c;
  let store;
  try { store = core.getStore(); }
  catch (_) { return {storeReady: false}; }
  const listenTogether = store["async:listenTogether"];
  const roomInfo = (listenTogether && listenTogether.roomInfo) || {};
  return {
    status: util.utilStatus,
    heartbeatActive: util.heartbeatCounting != null,
    storeReady: Boolean(listenTogether && listenTogether.roomInfo),
    roomInfo
  };
})()
''')

def _validate_numeric_id(value):
    value = str(value or '').strip()
    if not re.fullmatch(r'\d{1,20}', value):
        raise ValueError('ID must contain 1 to 20 digits.')
    return value

def netease_status():
    installed = os.path.isdir(NETEASE_APP_PATH) if sys.platform == 'darwin' else False
    running = False
    if installed:
        try:
            running = subprocess.run(
                ['/usr/bin/pgrep', '-x', NETEASE_PROCESS_NAME],
                capture_output=True,
                timeout=3,
            ).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            running = False
    return json.dumps({
        'platform': sys.platform,
        'cookieConfigured': bool(NETEASE_COOKIE),
        'clientInstalled': installed,
        'clientRunning': running,
        'verifiedPlaybackControl': True,
        'systemMediaKeyNextInstalled': False,
    }, ensure_ascii=False)

def netease_playlist_auth_status():
    result = {'cookieConfigured': bool(NETEASE_COOKIE), 'authenticated': False}
    if NETEASE_COOKIE:
        try:
            result['authenticated'] = bool(get_uid())
        except Exception as exc:
            result['error'] = str(exc)
    return json.dumps(result, ensure_ascii=False)

def netease_song_detail(song_ids):
    if not isinstance(song_ids, list) or not song_ids or len(song_ids) > 20:
        return 'song_ids must be a non-empty array containing at most 20 IDs.'
    try:
        ids = [_validate_numeric_id(value) for value in song_ids]
    except ValueError as exc:
        return str(exc)
    response = netease_request(
        'https://music.163.com/api/song/detail?ids='
        + urllib.parse.quote(json.dumps([int(value) for value in ids]))
    )
    songs = response.get('songs', [])
    normalized = []
    for song in songs:
        normalized.append({
            'id': song.get('id'),
            'name': song.get('name', ''),
            'artists': [artist.get('name', '') for artist in song.get('artists', song.get('ar', []))],
            'album': (song.get('album') or song.get('al') or {}).get('name', ''),
            'durationMs': song.get('duration', song.get('dt')),
            'url': 'https://music.163.com/#/song?id=' + str(song.get('id', '')),
        })
    return json.dumps({'songs': normalized}, ensure_ascii=False)

def netease_lyrics(song_id):
    try:
        song_id = _validate_numeric_id(song_id)
    except ValueError as exc:
        return str(exc)
    response = netease_request(
        'https://music.163.com/api/song/lyric?id=' + song_id + '&lv=1&kv=1&tv=-1'
    )
    return json.dumps({
        'songId': song_id,
        'lyrics': (response.get('lrc') or {}).get('lyric', ''),
        'translatedLyrics': (response.get('tlyric') or {}).get('lyric', ''),
        'romanizedLyrics': (response.get('romalrc') or {}).get('lyric', ''),
    }, ensure_ascii=False)

def get_song_comments(song_id, limit=20, offset=0):
    try:
        song_id = _validate_numeric_id(song_id)
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
    except (ValueError, TypeError) as exc:
        return 'Invalid comment query: ' + str(exc)
    url = (
        'https://music.163.com/api/v1/resource/comments/R_SO_4_' + song_id
        + '?' + urllib.parse.urlencode({'limit': limit, 'offset': offset, 'beforeTime': 0})
    )
    response = netease_request(url)
    if response.get('code') not in (None, 200):
        return json.dumps(response, ensure_ascii=False)

    def normalize_comment(comment):
        user = comment.get('user') or {}
        replied = comment.get('beReplied') or []
        return {
            'commentId': comment.get('commentId'),
            'userId': user.get('userId'),
            'nickname': user.get('nickname', ''),
            'content': comment.get('content', ''),
            'time': comment.get('time'),
            'likedCount': comment.get('likedCount', 0),
            'replies': [
                {
                    'nickname': (item.get('user') or {}).get('nickname', ''),
                    'content': item.get('content', ''),
                }
                for item in replied
            ],
        }

    return json.dumps({
        'songId': song_id,
        'total': response.get('total', 0),
        'more': bool(response.get('more')),
        'hotComments': [normalize_comment(item) for item in response.get('hotComments', [])],
        'comments': [normalize_comment(item) for item in response.get('comments', [])],
    }, ensure_ascii=False)

def send_song_comment(song_id, content):
    if not NETEASE_COOKIE:
        return 'Public comment not sent: NETEASE_COOKIE is not configured.'
    try:
        song_id = _validate_numeric_id(song_id)
    except ValueError as exc:
        return str(exc)
    content = str(content or '').strip()
    if not content or len(content) > 140:
        return 'Comment content must contain 1 to 140 characters.'
    csrf = get_csrf()
    response = netease_request(
        'https://music.163.com/api/v1/resource/comments/add?csrf_token='
        + urllib.parse.quote(csrf),
        {
            'threadId': 'R_SO_4_' + song_id,
            'content': content,
            'csrf_token': csrf,
        },
    )
    if response.get('code') == 200:
        comment = response.get('comment') or {}
        return json.dumps({
            'sent': True,
            'songId': song_id,
            'commentId': comment.get('commentId'),
            'content': comment.get('content', content),
        }, ensure_ascii=False)
    return json.dumps({
        'sent': False,
        'songId': song_id,
        'code': response.get('code'),
        'message': response.get('message') or response.get('error') or 'Unknown error',
    }, ensure_ascii=False)

def send_private_message(user_id, content):
    if not NETEASE_COOKIE:
        return 'Private message not sent: NETEASE_COOKIE is not configured.'
    try:
        user_id = _validate_numeric_id(user_id)
    except ValueError as exc:
        return str(exc)
    content = str(content or '').strip()
    if not content:
        return 'Private message content cannot be empty.'
    csrf = get_csrf()
    response = netease_request(
        'https://music.163.com/api/msg/private/send?csrf_token='
        + urllib.parse.quote(csrf),
        {
            'userIds': json.dumps([int(user_id)]),
            'msg': content,
            'type': 'text',
            'csrf_token': csrf,
        },
    )
    if response.get('code') == 200:
        return json.dumps({
            'sent': True,
            'userId': user_id,
            'content': content,
        }, ensure_ascii=False)
    return json.dumps({
        'sent': False,
        'userId': user_id,
        'code': response.get('code'),
        'message': response.get('message') or response.get('error') or 'Unknown error',
    }, ensure_ascii=False)

def netease_launch():
    error = _require_macos_client()
    if error:
        return error
    ok, detail = _run_open(['-b', NETEASE_BUNDLE_ID])
    return 'NetEase Music launched.' if ok else 'Could not launch NetEase Music: ' + detail

def netease_listen_together_capabilities():
    if not _can_use_cdp():
        st = _get_listen_together_http_status()
        return json.dumps({
            'supported': True,
            'mode': 'http',
            'inRoom': bool(st.get('inRoom')),
            'roomId': st.get('roomId'),
            'canOpenInviteEntry': False,
            'canCreateShareLink': False,
            'canSendNativeInvite': False,
            'canLeaveTogether': True,
            'canPlaybackControl': bool(st.get('inRoom')),
            'canAddSong': bool(st.get('inRoom')),
            'canSwitchSong': bool(st.get('inRoom')),
            'synchronizedPlayback': 'provided_by_http_api',
            'message': 'HTTP 模式正常运行。' + ('当前处于一起听房间中。' if st.get('inRoom') else '当前未在房间中，请在手机端发起邀请。'),
        }, ensure_ascii=False)
    return json.dumps({
        'supported': sys.platform == 'darwin' and os.path.isdir(NETEASE_APP_PATH),
        'canOpenInviteEntry': True,
        'canCreateShareLink': bool(NETEASE_COOKIE),
        'canSendNativeInvite': bool(NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID),
        'canLeaveTogether': True,
        'requiresManualInteraction': False,
        'synchronizedPlayback': 'provided_by_official_client',
        'mcpTextChat': False,
        'mcpVoiceChat': False,
        'mcpEmoticons': False,
    }, ensure_ascii=False)

def netease_listen_together_invite():
    error = _require_macos_client()
    if error:
        return error
    if not NETEASE_COOKIE:
        return json.dumps({
            'success': False,
            'message': 'NETEASE_COOKIE is not configured.',
        }, ensure_ascii=False)
    if not NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID:
        return json.dumps({
            'success': False,
            'message': 'NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID is not configured.',
        }, ensure_ascii=False)
    debug_error = _ensure_netease_debug_client()
    if debug_error:
        return json.dumps({
            'success': False,
            'message': debug_error,
        }, ensure_ascii=False)
    try:
        if not _bootstrap_netease_webpack():
            raise RuntimeError('Could not access the NetEase client runtime.')
        for _ in range(40):
            client_state = _listen_together_client_state()
            if client_state.get('storeReady'):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError('Listen Together store did not initialize.')
    except Exception as exc:
        return json.dumps({
            'success': False,
            'message': 'Could not initialize NetEase client control: ' + str(exc),
        }, ensure_ascii=False)
    csrf = get_csrf()
    room = client_state.get('roomInfo') or {}
    if (
        client_state.get('status') in {'togetherOwner', 'together'}
        and client_state.get('heartbeatActive')
        and room.get('roomId')
    ):
        return json.dumps({
            'success': True,
            'alreadyListeningTogether': True,
            'roomId': str(room['roomId']),
            'roomState': client_state.get('status'),
            'nativeInviteSent': False,
            'message': 'Already listening together; no new invite was sent.',
        }, ensure_ascii=False)
    active_room = (
        client_state.get('status') in {'waiting', 'togetherOwner'}
        and client_state.get('heartbeatActive')
        and room.get('roomId')
        and room.get('creatorId')
    )
    activation = client_state
    response = {'code': 200, 'data': {'type': 'EXISTING_ROOM'}}
    if not active_room:
        stale = netease_request(
            'https://music.163.com/api/listen/together/status/get?csrf_token='
            + urllib.parse.quote(csrf),
            {'csrf_token': csrf},
        )
        stale_data = stale.get('data') or {}
        stale_room = stale_data.get('roomInfo') or {}
        if stale_data.get('inRoom') and stale_room.get('roomId'):
            netease_request(
                'https://music.163.com/api/listen/together/end/v2?csrf_token='
                + urllib.parse.quote(csrf),
                {
                    'roomId': stale_room['roomId'],
                    'shareInfo': '{}',
                    'csrf_token': csrf,
                },
            )
        try:
            activation = _create_listen_together_in_client()
            room = activation.get('roomInfo') or {}
            response = {'code': 200, 'data': {'type': 'NEW_ROOM'}}
        except Exception as exc:
            return json.dumps({
                'success': False,
                'message': 'NetEase client room creation failed: ' + str(exc),
            }, ensure_ascii=False)
    room_id = room.get('roomId')
    creator_id = room.get('creatorId')
    if response.get('code') != 200 or not room_id or not creator_id:
        return json.dumps({
            'success': False,
            'message': response.get('message') or response.get('error')
                or 'NetEase did not create a Listen Together room.',
            'code': response.get('code'),
        }, ensure_ascii=False)
    if (
        activation.get('status') not in {'waiting', 'togetherOwner'}
        or not activation.get('heartbeatActive')
    ):
        return json.dumps({
            'success': False,
            'message': 'NetEase client did not become an active room owner.',
            'activation': activation,
            'roomId': str(room_id),
        }, ensure_ascii=False)
    invite_response = netease_request(
        'https://music.163.com/api/listen/together/invite/message/send?csrf_token='
        + urllib.parse.quote(csrf),
        {
            'roomId': str(room_id),
            'acceptorId': NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID,
            'csrf_token': csrf,
        },
    )
    native_invite_sent = bool(
        invite_response.get('code') == 200
        and (invite_response.get('data') or {}).get('result')
    )
    return json.dumps({
        'success': native_invite_sent,
        'roomId': str(room_id),
        'creatorId': str(creator_id),
        'roomState': activation.get('status'),
        'clientActivated': True,
        'heartbeatActive': True,
        'nativeInviteSent': native_invite_sent,
        'acceptorId': (
            NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID
            if native_invite_sent else None
        ),
        'message': (
            'Listen Together is active and the native invite was sent.'
            if native_invite_sent
            else 'Listen Together is active, but the configured native invite failed.'
        ),
    }, ensure_ascii=False)

def netease_listen_together_leave():
    if not _can_use_cdp():
        st = _get_listen_together_http_status()
        if not st.get('inRoom') or not st.get('roomId'):
            return json.dumps({'success': True, 'alreadyLeft': True, 'message': 'Not currently listening together.'}, ensure_ascii=False)
        csrf = get_csrf()
        url = 'https://music.163.com/api/listen/together/end/v2?csrf_token=' + urllib.parse.quote(csrf)
        res = netease_request(url, {'roomId': st['roomId'], 'shareInfo': '{}', 'csrf_token': csrf})
        return json.dumps({'success': res.get('code') == 200, 'roomId': st['roomId'], 'message': 'Left Listen Together room.'}, ensure_ascii=False)
    error = _require_macos_client()
    if error:
        return error
    if not _netease_cdp_target():
        return json.dumps({
            'success': False,
            'message': 'NetEase client control is unavailable; the client was not restarted.',
        }, ensure_ascii=False)
    try:
        if not _bootstrap_netease_webpack():
            raise RuntimeError('Could not access the NetEase client runtime.')
        state = _listen_together_client_state()
        room_id = (state.get('roomInfo') or {}).get('roomId')
        if state.get('status') == 'alone' or not room_id:
            return json.dumps({
                'success': True,
                'alreadyLeft': True,
                'message': 'Not currently listening together.',
            }, ensure_ascii=False)
        _netease_cdp_eval(
            'window.__codexWebpackRequire(58).c.leaveListenTogether({silent:true}); true'
        )
        for _ in range(32):
            time.sleep(0.25)
            state = _listen_together_client_state()
            if (
                state.get('status') == 'alone'
                or not (state.get('roomInfo') or {}).get('roomId')
            ):
                return json.dumps({
                    'success': True,
                    'roomId': str(room_id),
                    'message': 'Left Listen Together.',
                }, ensure_ascii=False)
        raise RuntimeError('NetEase did not finish leaving the room.')
    except Exception as exc:
        return json.dumps({
            'success': False,
            'message': 'Could not leave Listen Together: ' + str(exc),
        }, ensure_ascii=False)

def _netease_playback_control(command, ids=None, position=None, play_status=None):
    local_commands = {'play', 'pause', 'previous', 'next'}
    room_commands = {'PLAY', 'PAUSE', 'PROGRESS', 'NEXT', 'PREVIOUS', 'GOTO'}
    if command not in local_commands | room_commands:
        return json.dumps({'success': False, 'message': 'Unsupported command.'}, ensure_ascii=False)
    if not _can_use_cdp():
        return _http_playback_control(command, ids, position, play_status)
    error = _ensure_netease_debug_client()
    if error:
        return json.dumps({'success': False, 'message': error}, ensure_ascii=False)
    try:
        if not _bootstrap_netease_webpack():
            raise RuntimeError('Could not access the NetEase client runtime.')
        if command in ('previous', 'next'):
            request = {'type': 'playingList/jump2Track', 'payload': {'flag': -1 if command == 'previous' else 1, 'type': 'call', 'triggerScene': 'minibarController'}}
        elif command in ('play', 'pause'):
            request = {'type': 'playing/resume' if command == 'play' else 'playing/pause', 'payload': {}}
        else:
            room = _listen_together_client_state()
            if room.get('status') == 'alone' or not (room.get('roomInfo') or {}).get('roomId'):
                raise RuntimeError('No active Listen Together room.')
            if command in ('NEXT', 'PREVIOUS', 'GOTO') and (not ids or len(ids) != 2):
                raise RuntimeError(command + ' requires [formerSongId, targetSongId].')
            payload = {'command': command, 'reason': 'force'}
            if ids is not None: payload['ids'] = [str(value) for value in ids]
            if position is not None: payload['position'] = position
            if play_status is not None: payload['playStatus'] = play_status
            if command in ('PLAY', 'PAUSE'): payload.setdefault('playStatus', 2 if command == 'PLAY' else 1)
            request = {'type': 'async:listenTogetherPlayStatus/reportRequest', 'payload': payload}
        result = _netease_cdp_eval('Promise.resolve(window.__codexWebpackRequire(11).a.getDispatch()(' + json.dumps(request) + ')).then(() => true)', await_promise=True)
        if result is not True: raise RuntimeError('The client did not accept the command.')
        return json.dumps({'success': True, 'command': command}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({'success': False, 'message': 'Playback control failed: ' + str(exc)}, ensure_ascii=False)

def netease_playback_control(command):
    return _netease_playback_control(command)

def netease_listen_together_control(command, ids=None, position=None, play_status=None):
    return _netease_playback_control(command, ids, position, play_status)

def normalize_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()

def local_track_db_path():
    return os.path.expanduser(
        '~/Library/Containers/com.netease.163music/Data/Documents/storage/sqlite_storage.sqlite3'
    )

def find_local_song_id(info):
    db_path = local_track_db_path()
    if not os.path.exists(db_path):
        return None
    try:
        connection = sqlite3.connect('file:' + urllib.parse.quote(db_path) + '?mode=ro', uri=True)
        try:
            rows = connection.execute(
                "SELECT id, jsonStr FROM dbTrack WHERE json_extract(jsonStr, '$.name') = ? LIMIT 100",
                (info.get('title', ''),)
            ).fetchall()
        finally:
            connection.close()
    except Exception:
        return None
    wanted_artist = normalize_text(info.get('artist'))
    wanted_album = normalize_text(info.get('album'))
    wanted_duration = float(info.get('duration') or 0) * 1000
    best = None
    for row_id, raw in rows:
        try:
            track = json.loads(raw)
        except Exception:
            continue
        artists = [normalize_text(a.get('name')) for a in track.get('artists', [])]
        score = 0
        if wanted_artist and wanted_artist in artists:
            score += 100
        if wanted_album and normalize_text(track.get('album', {}).get('name')) == wanted_album:
            score += 20
        duration = float(track.get('duration') or 0)
        if wanted_duration and duration and abs(duration - wanted_duration) <= 3000:
            score += 10
        if best is None or score > best[0]:
            best = (score, str(row_id))
    return best[1] if best and best[0] >= 100 else None

def search_song_id(info):
    query = (info.get('title', '') + ' ' + info.get('artist', '')).strip()
    url = 'https://music.163.com/api/search/get/web?s=' + urllib.parse.quote(query) + '&type=1&limit=30'
    songs = netease_request(url).get('result', {}).get('songs', [])
    title = normalize_text(info.get('title'))
    artist = normalize_text(info.get('artist'))
    for song in songs:
        song_artists = [normalize_text(a.get('name')) for a in song.get('artists', [])]
        if normalize_text(song.get('name')) == title and artist in song_artists:
            return str(song.get('id'))
    return None

def parse_lrc(raw):
    timeline = []
    for raw_line in str(raw or '').splitlines():
        matches = list(re.finditer(r'\[(\d{1,3}):(\d{2}(?:\.\d{1,3})?)\]', raw_line))
        if not matches:
            continue
        text = re.sub(r'\[[^\]]+\]', '', raw_line).strip()
        if not text:
            continue
        for match in matches:
            seconds = int(match.group(1)) * 60 + float(match.group(2))
            timeline.append((seconds, text))
    timeline.sort(key=lambda item: item[0])
    return timeline

def get_lyric_timeline(song_id):
    with LYRIC_CACHE_LOCK:
        cached = LYRIC_CACHE.get(str(song_id))
    if cached is not None:
        return cached
    url = 'https://music.163.com/api/song/lyric?id=' + str(song_id) + '&lv=1&kv=1&tv=-1'
    response = netease_request(url)
    timeline = parse_lrc(response.get('lrc', {}).get('lyric', ''))
    if timeline:
        with LYRIC_CACHE_LOCK:
            LYRIC_CACHE[str(song_id)] = timeline
    return timeline

def get_current_listening_context():
    info, error = get_now_playing()
    if error:
        try:
            if _netease_cdp_target() and _bootstrap_netease_webpack():
                current = _netease_cdp_eval(r'''
(() => {
  const playing = window.__codexWebpackRequire(11).a.getStore().playing || {};
  const item = playing.curPlaying || {};
  const track = item.track || {};
  return {
    songId: String(item.resourceId || track.id || ""),
    title: track.name || playing.resourceName || "",
    artist: (track.artists || playing.resourceArtists || []).map(a => a.name).join(", "),
    album: (track.album || {}).name || "",
    duration: Number(track.duration || playing.resourceDuration || 0) / 1000,
    playing: playing.playingState === 2
  };
})()
''')
                if current.get('songId'):
                    return json.dumps({
                        'success': True,
                        **current,
                        'positionAvailable': False,
                        'nearbyLyrics': [],
                        'message': 'Playback is confirmed by the NetEase client; macOS has not published the timeline yet.'
                    }, ensure_ascii=False)
        except Exception:
            pass
        try:
            st = _get_listen_together_http_status()
            if st.get('inRoom') and st.get('roomId'):
                state = _get_room_state(st['roomId'])
                play_cmd = state.get('playCommand') or {}
                cur_song_id = play_cmd.get('targetSongId')
                if cur_song_id:
                    detail = netease_request('https://music.163.com/api/song/detail?ids=[' + str(cur_song_id) + ']')
                    tracks = detail.get('songs') or []
                    if tracks:
                        cur_s = tracks[0]
                        title = cur_s.get('name') or ''
                        artist = ', '.join(a.get('name', '') for a in cur_s.get('artists', []))
                        album = (cur_s.get('album') or {}).get('name') or ''
                        duration = float(cur_s.get('duration') or 0) / 1000
                        elapsed = float(play_cmd.get('progress') or 0) / 1000
                        timeline = get_lyric_timeline(cur_song_id)
                        nearby = []
                        if timeline:
                            cur_idx = max(0, bisect.bisect_right([item[0] for item in timeline], elapsed) - 1)
                            nearby = [
                                {'time': round(sec, 3), 'text': text, 'current': idx == cur_idx, 'replyTarget': idx == min(cur_idx + 2, len(timeline) - 1)}
                                for idx, (sec, text) in enumerate(timeline[cur_idx:cur_idx + 6], cur_idx)
                            ]
                        return json.dumps({
                            'success': True,
                            'songId': cur_song_id,
                            'title': title,
                            'artist': artist,
                            'album': album,
                            'elapsedTime': round(elapsed, 3),
                            'duration': round(duration, 3),
                            'nearbyLyrics': nearby,
                            'playing': play_cmd.get('playStatus') == 'PLAY',
                            'roomPlayback': True
                        }, ensure_ascii=False)
        except Exception:
            pass
        return json.dumps({'success': False, 'message': error}, ensure_ascii=False)
    song_id = find_local_song_id(info) or search_song_id(info)
    if not song_id:
        return json.dumps({
            'success': False,
            'message': 'Could not resolve the current NetEase song ID.',
            'title': info.get('title'),
            'artist': info.get('artist')
        }, ensure_ascii=False)
    timeline = get_lyric_timeline(song_id)
    if not timeline:
        return json.dumps({
            'success': False,
            'message': 'No timed lyrics were returned for the current song.',
            'songId': song_id,
            'title': info.get('title'),
            'artist': info.get('artist')
        }, ensure_ascii=False)
    elapsed = float(info.get('elapsedTime') or 0)
    current_index = max(0, bisect.bisect_right([item[0] for item in timeline], elapsed) - 1)
    nearby = [
        {'time': round(seconds, 3), 'text': text, 'current': index == current_index, 'replyTarget': index == min(current_index + 2, len(timeline) - 1)}
        for index, (seconds, text) in enumerate(timeline[current_index:current_index + 6], current_index)
    ]
    return json.dumps({
        'success': True,
        'songId': song_id,
        'title': info.get('title'),
        'artist': info.get('artist'),
        'album': info.get('album'),
        'elapsedTime': round(elapsed, 3),
        'duration': round(float(info.get('duration') or 0), 3),
        'nearbyLyrics': nearby
    }, ensure_ascii=False)

def netease_request(url, data=None):
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://music.163.com/', 'Cookie': NETEASE_COOKIE, 'Content-Type': 'application/x-www-form-urlencoded' if data else 'application/json'}
    if data and isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    elif data and isinstance(data, str):
        data = data.encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"code": -1, "error": str(e)}

def get_uid():
    resp = netease_request('https://music.163.com/api/nuser/account/get')
    try:
        return resp.get('profile', {}).get('userId') or resp.get('account', {}).get('id')
    except:
        return None

def get_csrf():
    for part in NETEASE_COOKIE.split(';'):
        part = part.strip()
        if part.startswith('__csrf='):
            return part.split('=', 1)[1]
    return ''

def _get_listen_together_http_status():
    csrf = get_csrf()
    url = 'https://music.163.com/api/listen/together/status/get?csrf_token=' + urllib.parse.quote(csrf)
    res = netease_request(url, {'csrf_token': csrf})
    data = res.get('data') or {}
    room_info = data.get('roomInfo') or {}
    return {
        'inRoom': bool(data.get('inRoom')),
        'roomId': room_info.get('roomId'),
        'creatorId': room_info.get('creatorId'),
        'status': data.get('status'),
        'roomUsers': room_info.get('roomUsers') or [],
        'data': data
    }

def _accept_latest_invitation():
    csrf = get_csrf()
    acceptor_id = NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID
    if not acceptor_id:
        return False, "NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID 未配置"
    url = 'https://music.163.com/api/msg/private/history?csrf_token=' + urllib.parse.quote(csrf)
    res = netease_request(url, {'userId': str(acceptor_id), 'limit': '10', 'csrf_token': csrf})
    msgs = res.get('msgs', [])
    for m in msgs:
        try:
            msg_obj = json.loads(m.get('msg', '{}'))
            if msg_obj.get('type') == 23:
                native_url = (msg_obj.get('generalMsg') or {}).get('nativeUrl', '')
                if 'roomId=' in native_url and 'inviterId=' in native_url:
                    parsed = urllib.parse.urlparse(native_url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if 'url1' in qs:
                        sub_qs = urllib.parse.parse_qs(urllib.parse.urlparse(qs['url1'][0]).query)
                        room_id = sub_qs.get('roomId', [''])[0]
                        inviter_id = sub_qs.get('inviterId', [''])[0]
                    else:
                        room_id = qs.get('roomId', [''])[0]
                        inviter_id = qs.get('inviterId', [''])[0]
                    if room_id and inviter_id:
                        acc_url = 'https://music.163.com/api/listen/together/play/invitation/accept?csrf_token=' + urllib.parse.quote(csrf)
                        acc_res = netease_request(acc_url, {'roomId': str(room_id), 'inviterId': str(inviter_id), 'csrf_token': csrf})
                        if acc_res.get('code') == 200:
                            return True, f"已自动接受房间 {room_id} 的一起听邀请（邀请人: {inviter_id}）"
        except Exception:
            pass
    return False, "近期私信中未找到有效的一起听邀请卡片"

def _get_room_state(room_id):
    csrf = get_csrf()
    url = 'https://music.163.com/api/listen/together/sync/playlist/get?csrf_token=' + urllib.parse.quote(csrf)
    res = netease_request(url, {'roomId': str(room_id), 'csrf_token': csrf})
    if res.get('code') != 200:
        raise RuntimeError('sync/playlist/get failed: ' + str(res))
    return res.get('data') or {}

def _report_list_command(room_id, command):
    csrf = get_csrf()
    url = 'https://music.163.com/api/listen/together/sync/list/command/report?csrf_token=' + urllib.parse.quote(csrf)
    payload = {
        'roomId': str(room_id),
        'commandInfo': json.dumps(command, ensure_ascii=False, separators=(',', ':')),
        'csrf_token': csrf,
    }
    res = netease_request(url, payload)
    if res.get('code') != 200 or not (res.get('data') or {}).get('result'):
        raise RuntimeError('sync/list/command/report failed: ' + str(res))
    return res

def _report_play_command(room_id, command):
    csrf = get_csrf()
    url = 'https://music.163.com/api/listen/together/play/command/report?csrf_token=' + urllib.parse.quote(csrf)
    payload = {
        'roomId': str(room_id),
        'commandInfo': json.dumps(command, ensure_ascii=False, separators=(',', ':')),
        'csrf_token': csrf,
    }
    res = netease_request(url, payload)
    if res.get('code') != 200 or not (res.get('data') or {}).get('result'):
        raise RuntimeError('play/command/report failed: ' + str(res))
    return res

def _http_play_music(s, song_id, note=None):
    st = _get_listen_together_http_status()
    if not st.get('inRoom') or not st.get('roomId'):
        ok, msg = _accept_latest_invitation()
        if ok:
            time.sleep(1)
            st = _get_listen_together_http_status()
        if not st.get('inRoom') or not st.get('roomId'):
            return (
                "当前未加入「一起听」房间。在 Linux 纯 HTTP 模式下，请先在手机网易云 App 中发起「一起听」并邀请当前账号入房。"
            )
    room_id = st['roomId']
    state = _get_room_state(room_id)
    play_command = state.get('playCommand') or {}
    playlist = state.get('playlist') or {}

    former = str(play_command.get('targetSongId') or '')
    seq = int(play_command.get('clientSeq', 0))
    versions = [dict(v) for v in playlist.get('version', [])]
    play_mode = playlist.get('playMode', 'ORDER_LOOP')

    display_items = playlist.get('displayList', {}).get('result', [])
    display_list = [
        str(item.get('songId') if isinstance(item, dict) else item)
        for item in display_items
    ]
    current_index = display_list.index(former) if former in display_list else 0
    target = str(song_id)

    my_uid = get_uid()
    for v in versions:
        if str(v.get('userId')) == str(my_uid):
            v['version'] = int(v.get('version', 0)) + 1
            break
    else:
        if my_uid:
            versions.append({'userId': int(my_uid), 'version': 1})

    added_ok = True
    if target not in display_list:
        try:
            _report_list_command(room_id, {
                'commandType': 'ADD',
                'version': versions,
                'playMode': play_mode,
                'anchorSongId': former,
                'anchorPosition': current_index,
                'randomList': [target],
                'displayList': [target],
            })
            time.sleep(1.0)
        except Exception as e:
            added_ok = False

    try:
        _report_play_command(room_id, {
            'commandType': 'GOTO',
            'progress': 0,
            'playStatus': 'PLAY',
            'formerSongId': former,
            'targetSongId': target,
            'clientSeq': seq + 1,
        })
    except Exception as e:
        if not added_ok:
            return (
                f"切歌未能生效：目标歌曲未在房间当前播放列表中（当前房间列表已达 1000 首上限或仅房主可加歌）。\n"
                f"建议先在手机端将此歌《{s.get('name', '')}》加入房间播放列表后再点歌。"
            )
        return f"切歌失败: {e}"

    pic_url = (s.get('album') or {}).get('picUrl', '')
    name = s.get('name', '').replace(':', '：')
    artist = ', '.join([a.get('name', '') for a in s.get('artists', [])]).replace(':', '：')
    link = "https://music.163.com/song?id=" + str(song_id)
    return (
        '已在网易云「一起听」房间中切歌播放：\n'
        + "[music:" + str(song_id) + ":" + name + ":" + artist + ":" + pic_url + "]"
        + (note or '') + "\n" + link
    )

def _http_playback_control(command, ids=None, position=None, play_status=None):
    st = _get_listen_together_http_status()
    if not st.get('inRoom') or not st.get('roomId'):
        return json.dumps({
            'success': False,
            'message': '当前未在「一起听」房间中，无法执行播放控制。'
        }, ensure_ascii=False)
    room_id = st['roomId']
    state = _get_room_state(room_id)
    play_command = state.get('playCommand') or {}
    playlist = state.get('playlist') or {}
    former = str(play_command.get('targetSongId') or '')
    seq = int(play_command.get('clientSeq', 0))

    display_items = playlist.get('displayList', {}).get('result', [])
    display_list = [
        str(item.get('songId') if isinstance(item, dict) else item)
        for item in display_items
    ]
    current_index = display_list.index(former) if former in display_list else 0

    cmd = command.upper()
    if cmd in ('PLAY', 'RESUME'):
        _report_play_command(room_id, {
            'commandType': 'PLAY',
            'progress': int(position or play_command.get('progress') or 0),
            'playStatus': 'PLAY',
            'formerSongId': former,
            'targetSongId': former,
            'clientSeq': seq + 1,
        })
        return json.dumps({'success': True, 'command': command}, ensure_ascii=False)
    elif cmd in ('PAUSE', 'STOP'):
        _report_play_command(room_id, {
            'commandType': 'PAUSE',
            'progress': int(position or play_command.get('progress') or 0),
            'playStatus': 'PAUSE',
            'formerSongId': former,
            'targetSongId': former,
            'clientSeq': seq + 1,
        })
        return json.dumps({'success': True, 'command': command}, ensure_ascii=False)
    elif cmd in ('NEXT',):
        if not display_list:
            return json.dumps({'success': False, 'message': '播放列表为空'}, ensure_ascii=False)
        target = display_list[(current_index + 1) % len(display_list)]
        _report_play_command(room_id, {
            'commandType': 'GOTO',
            'progress': 0,
            'playStatus': 'PLAY',
            'formerSongId': former,
            'targetSongId': target,
            'clientSeq': seq + 1,
        })
        return json.dumps({'success': True, 'command': 'NEXT', 'targetSongId': target}, ensure_ascii=False)
    elif cmd in ('PREVIOUS', 'PREV'):
        if not display_list:
            return json.dumps({'success': False, 'message': '播放列表为空'}, ensure_ascii=False)
        target = display_list[(current_index - 1) % len(display_list)]
        _report_play_command(room_id, {
            'commandType': 'GOTO',
            'progress': 0,
            'playStatus': 'PLAY',
            'formerSongId': former,
            'targetSongId': target,
            'clientSeq': seq + 1,
        })
        return json.dumps({'success': True, 'command': 'PREVIOUS', 'targetSongId': target}, ensure_ascii=False)
    elif cmd == 'GOTO':
        target = str(ids[1]) if ids and len(ids) == 2 else (str(ids[0]) if ids else former)
        _report_play_command(room_id, {
            'commandType': 'GOTO',
            'progress': int(position or 0),
            'playStatus': 'PLAY',
            'formerSongId': former,
            'targetSongId': target,
            'clientSeq': seq + 1,
        })
        return json.dumps({'success': True, 'command': 'GOTO', 'targetSongId': target}, ensure_ascii=False)
    elif cmd == 'PROGRESS':
        _report_play_command(room_id, {
            'commandType': 'PROGRESS',
            'progress': int(position or 0),
            'playStatus': 'PLAY' if play_status != 1 else 'PAUSE',
            'formerSongId': former,
            'targetSongId': former,
            'clientSeq': seq + 1,
        })
        return json.dumps({'success': True, 'command': 'PROGRESS'}, ensure_ascii=False)
    else:
        return json.dumps({'success': False, 'message': f'不支持的指令: {command}'}, ensure_ascii=False)

def netease_listen_together_accept(room_id=None, inviter_id=None):
    if room_id and inviter_id:
        csrf = get_csrf()
        acc_url = 'https://music.163.com/api/listen/together/play/invitation/accept?csrf_token=' + urllib.parse.quote(csrf)
        acc_res = netease_request(acc_url, {'roomId': str(room_id), 'inviterId': str(inviter_id), 'csrf_token': csrf})
        if acc_res.get('code') == 200:
            return json.dumps({'success': True, 'roomId': str(room_id), 'inviterId': str(inviter_id), 'message': '成功接受一起听邀请！'}, ensure_ascii=False)
        return json.dumps({'success': False, 'message': acc_res.get('message') or '接受邀请失败', 'response': acc_res}, ensure_ascii=False)
    ok, msg = _accept_latest_invitation()
    return json.dumps({'success': ok, 'message': msg}, ensure_ascii=False)

def play_music(query='', note=None, artist=None, song_id=None):
    if song_id:
        song_id = _validate_numeric_id(song_id)
    elif not query.strip():
        return 'Provide a song title or song ID.'
    norm = lambda value: ''.join(c.lower() for c in value if c.isalnum())
    same_parts = lambda value, parts: len(norm(value)) == sum(len(norm(p)) for p in parts) and all(norm(p) in norm(value) for p in parts)
    if not song_id:
        search = query + (' ' + artist if artist else '')
        url = 'https://music.163.com/api/search/get?s=' + urllib.parse.quote(search) + '&type=1&limit=10'
        resp = netease_request(url)
        songs = resp.get('result', {}).get('songs', [])
        if not songs:
            return "No results for '" + query + "'"
        query_key = norm(query)
        variants = ('sped up', 'sped', 'live', '翻唱', 'cover')
        title_match = lambda s: norm(s.get('name', '')) == query_key or norm(re.sub('sped up|sped|live|翻唱|cover', '', s.get('name', ''), flags=re.I)) == query_key
        def format_candidates(items, heading):
            return heading + "\n" + "\n".join(
                'ID ' + str(s.get('id')) + ' | ' + s.get('name', '') + ' - ' +
                ', '.join(a.get('name', '') for a in s.get('artists', [])) + ' | ' +
                (s.get('album') or {}).get('name', '') for s in items[:5]
            )
        def artist_match(value, parts):
            keys = [norm(p) for p in parts if norm(p)]
            if len(keys) == 1:
                shorter, longer = sorted((norm(value), keys[0]), key=len)
                extra = longer.replace(shorter, '', 1) if shorter in longer else longer
                return shorter in longer and (not extra or extra.isascii())
            return same_parts(value, parts)
        if artist:
            matches = [s for s in songs if title_match(s) and artist_match(artist, [a.get('name', '') for a in s.get('artists', [])])]
        else:
            matches = [s for s in songs if same_parts(query, [s.get('name', '')] + [a.get('name', '') for a in s.get('artists', [])])]
            if not matches:
                matches = [s for s in songs if title_match(s)]
        if not matches:
            title_candidates = [s for s in songs if title_match(s)]
            if title_candidates:
                return format_candidates(
                    title_candidates,
                    'No exact original artist credit was found. Available versions (choose only if appropriate, then call play_music with song_id):',
                )
            return "No exact title and artist match for '" + query + "'"
        exact = [s for s in matches if norm(s.get('name', '')) == query_key]
        original = [s for s in matches if not any(v in s.get('name', '').lower() for v in variants)]
        candidates = exact or original or matches
        if len(candidates) != 1:
            return format_candidates(
                candidates,
                'Candidates (call play_music again with the chosen song_id):',
            )
        song_id = candidates[0].get('id')
    detail = netease_request(
        'https://music.163.com/api/song/detail?ids=[' + str(song_id) + ']'
    )
    tracks = detail.get('songs') or []
    if not tracks:
        return 'Could not load the selected song details.'
    s = tracks[0]
    if not _can_use_cdp():
        return _http_play_music(s, song_id, note)
    debug_error = _ensure_netease_debug_client()
    if debug_error:
        return 'Could not control NetEase Music: ' + debug_error
    try:
        if not _bootstrap_netease_webpack():
            raise RuntimeError('Could not access the NetEase client runtime.')
        room = _listen_together_client_state()
        in_room = room.get('status') != 'alone' and bool(
            (room.get('roomInfo') or {}).get('roomId')
        )
        old_song_id = _netease_cdp_eval(
            '''String(((window.__codexWebpackRequire(11).a.getStore().playing || {})
              .curPlaying || {}).resourceId || "")'''
        )
        if in_room:
            _netease_cdp_eval(
                '''(() => {
  const dispatch = window.__codexWebpackRequire(11).a.getDispatch();
  dispatch({
    type: "async:listenTogetherPlayStatus/setCanReport",
    payload: {isCanReport: false}
  });
  setTimeout(() => dispatch({
    type: "async:listenTogetherPlayStatus/setCanReport",
    payload: {isCanReport: true}
  }), 5000);
  return true;
})()'''
            )
        _netease_cdp_eval(
            '''(async () => {
  const req = window.__codexWebpackRequire;
  // Module 102 is the current NetEase client's internal track loader, not a public API.
  // Its module ID may change after a client upgrade and should then be located again.
  const tracks = await req(102).a([{id: "''' + str(song_id) + '''", v: 0}]);
  await Promise.resolve(req(11).a.getDispatch()({
    type: "playing/play",
    payload: {
      tracks,
      from: {
        scene: "search",
        resourceType: "track",
        fromInfo: {},
        text: ''' + json.dumps(s.get('name', '')) + ''',
        href: "/song/''' + str(song_id) + '''"
      },
      options: {
        clear: false,
        play: true,
        playId: "''' + str(song_id) + '''",
        fromDoubleClick: true
      },
      triggerScene: "search"
    }
  }));
  return true;
})()''',
            await_promise=True,
        )
        for _ in range(80):
            state = _netease_cdp_eval(
                '''(() => {
  const playing = window.__codexWebpackRequire(11).a.getStore().playing || {};
  return {
    songId: String((playing.curPlaying || {}).resourceId || ""),
    playing: playing.playingState === 2
  };
})()'''
            )
            if state.get('songId') == str(song_id) and (
                in_room or state.get('playing')
            ):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError('NetEase did not confirm playback.')
        if in_room:
            _netease_cdp_eval(
                '''window.__codexWebpackRequire(11).a.getDispatch()({
  type: "async:listenTogetherPlayStatus/setCanReport",
  payload: {isCanReport: true}
}); true'''
            )
            _netease_cdp_eval(
                '''Promise.resolve(window.__codexWebpackRequire(11).a.getDispatch()({
  type: "async:listenTogetherPlayStatus/reportRequest",
  payload: {
    command: "GOTO",
    ids: [''' + json.dumps(old_song_id) + ''', "''' + str(song_id) + '''"],
    position: 0,
    playStatus: 2,
    reason: "force"
  }
})).then(() => true)''',
                await_promise=True,
            )
    except Exception as exc:
        return 'Could not play the selected song: ' + str(exc)
    pic_url = (tracks[0].get('album') or {}).get('picUrl', '')
    name = s.get('name', '').replace(':', '\uff1a')
    artist = ', '.join([a.get('name', '') for a in s.get('artists', [])]).replace(':', '\uff1a')
    link = "https://music.163.com/song?id=" + str(song_id)
    return (
        'Playing in NetEase Music.\n'
        + "[music:" + str(song_id) + ":" + name + ":" + artist + ":" + pic_url + "]"
        + (note or '') + "\n" + link
    )

def create_playlist(name, description='', privacy=0):
    csrf = get_csrf()
    url = 'https://music.163.com/api/playlist/create?csrf_token=' + csrf
    data = {'name': name, 'privacy': str(privacy), 'type': 'NORMAL'}
    if description:
        data['description'] = description
    resp = netease_request(url, data=data)
    if resp.get('code') == 200:
        pl = resp.get('playlist', {})
        return "Created playlist '" + name + "' (ID: " + str(pl.get('id')) + ")"
    return "Failed: " + resp.get('message', resp.get('error', 'unknown'))

def add_to_playlist(playlist_id, song_ids):
    csrf = get_csrf()
    if isinstance(song_ids, str):
        ids = [s.strip() for s in song_ids.split(',')]
    else:
        ids = [str(song_ids)]
    url = 'https://music.163.com/api/playlist/manipulate/tracks?csrf_token=' + csrf
    data = {'op': 'add', 'pid': str(playlist_id), 'trackIds': json.dumps([int(i) for i in ids])}
    resp = netease_request(url, data=data)
    if resp.get('code') == 200:
        return "Added " + str(len(ids)) + " song(s) to playlist " + str(playlist_id)
    if resp.get('code') == 502:
        return "Song already in playlist"
    return "Failed: " + resp.get('message', resp.get('error', 'unknown'))

def remove_from_playlist(playlist_id, song_ids):
    csrf = get_csrf()
    if isinstance(song_ids, str):
        ids = [s.strip() for s in song_ids.split(',')]
    else:
        ids = [str(song_ids)]
    url = 'https://music.163.com/api/playlist/manipulate/tracks?csrf_token=' + csrf
    data = {'op': 'del', 'pid': str(playlist_id), 'trackIds': json.dumps([int(i) for i in ids])}
    resp = netease_request(url, data=data)
    if resp.get('code') == 200:
        return "Removed " + str(len(ids)) + " song(s) from playlist " + str(playlist_id)
    return "Failed: " + resp.get('message', resp.get('error', 'unknown'))

def list_my_playlists():
    uid = get_uid()
    if not uid:
        return "Failed to get user ID. Cookie may be expired."
    url = 'https://music.163.com/api/user/playlist?uid=' + str(uid) + '&limit=50&offset=0'
    resp = netease_request(url)
    playlists = resp.get('playlist', [])
    if not playlists:
        return "No playlists found"
    lines = []
    for pl in playlists:
        own = '(mine)' if pl.get('creator', {}).get('userId') == uid else '(collected)'
        lines.append("ID:" + str(pl['id']) + " | " + pl['name'] + " | " + str(pl.get('trackCount', 0)) + " songs " + own)
    return "\n".join(lines)

def get_playlist_songs(playlist_id):
    url = 'https://music.163.com/api/v6/playlist/detail?id=' + str(playlist_id)
    resp = netease_request(url)
    playlist = resp.get('playlist', {})
    tracks = playlist.get('tracks', [])
    if not tracks:
        track_ids = playlist.get('trackIds', [])
        if track_ids:
            ids = [t['id'] for t in track_ids[:50]]
            detail = netease_request('https://music.163.com/api/song/detail?ids=' + json.dumps(ids))
            tracks = detail.get('songs', [])
    if not tracks:
        return "Playlist " + str(playlist_id) + " is empty"
    lines = ["Playlist: " + playlist.get('name', '') + " (" + str(len(tracks)) + " songs)"]
    for i, t in enumerate(tracks[:50], 1):
        artist = ', '.join([a.get('name', '') for a in t.get('ar', t.get('artists', []))])
        lines.append(str(i) + ". " + t.get('name', '') + " - " + artist + " (ID:" + str(t.get('id', '')) + ")")
    return "\n".join(lines)

def get_play_history(limit=30, all_time=False):
    uid = get_uid()
    if not uid:
        return "Failed to get user ID."
    record_type = '0' if all_time else '1'
    url = 'https://music.163.com/api/v1/play/record?uid=' + str(uid) + '&type=' + record_type + '&limit=' + str(limit)
    resp = netease_request(url)
    records = resp.get('weekData') or resp.get('allData') or []
    if not records:
        return "No play history found"
    lines = ["Recent play history:"]
    for i, r in enumerate(records[:limit], 1):
        song = r.get('song', {})
        name = song.get('name', '')
        artist = ', '.join([a.get('name', '') for a in song.get('ar', song.get('artists', []))])
        pc = r.get('playCount', r.get('score', ''))
        lines.append(str(i) + ". " + name + " - " + artist + " (plays:" + str(pc) + ", ID:" + str(song.get('id', '')) + ")")
    return "\n".join(lines)

def like_song(song_id, like=True):
    csrf = get_csrf()
    action = 'true' if like else 'false'
    url = 'https://music.163.com/api/radio/like?alg=itembased&trackId=' + str(song_id) + '&like=' + action + '&time=25&csrf_token=' + csrf
    resp = netease_request(url)
    if resp.get('code') == 200:
        return "Liked song " + str(song_id) if like else "Unliked song " + str(song_id)
    return "Failed: " + resp.get('message', resp.get('error', 'unknown'))

def daily_recommend():
    csrf = get_csrf()
    url = 'https://music.163.com/api/v3/discovery/recommend/songs?csrf_token=' + csrf
    resp = netease_request(url, data='{}')
    songs = resp.get('data', {}).get('dailySongs', [])
    if not songs:
        return "Could not fetch daily recommendations."
    lines = ["Today's recommendations:"]
    for i, s in enumerate(songs[:30], 1):
        name = s.get('name', '')
        artist = ', '.join([a.get('name', '') for a in s.get('ar', s.get('artists', []))])
        reason = s.get('reason', '')
        line = str(i) + ". " + name + " - " + artist + " (ID:" + str(s.get('id', '')) + ")"
        if reason:
            line += " [" + reason + "]"
        lines.append(line)
    return "\n".join(lines)

TOOLS = [
    {"name": "play_music", "description": "Find and immediately play a NetEase song in the official client. Provide artist when known. If search returns candidates, choose one and call this tool again with its song_id.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Exact song title"}, "artist": {"type": "string", "description": "Artist name"}, "song_id": {"type": ["integer", "string"], "description": "Exact NetEase song ID selected from candidates; bypasses search matching"}, "note": {"type": "string", "description": "Optional note"}}}},
    {"name": "netease_playback_control", "description": "Control ordinary playback in the official NetEase client: resume, pause, next track, or previous track. Native client behavior synchronizes an active Listen Together room when applicable.", "inputSchema": {"type": "object", "properties": {"command": {"type": "string", "enum": ["play", "pause", "next", "previous"]}}, "required": ["command"]}},
    {"name": "create_playlist", "description": "Create a new playlist in NetEase account.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string", "description": "Playlist name"}, "description": {"type": "string", "description": "Description"}, "privacy": {"type": "integer", "description": "0=public, 10=private"}}, "required": ["name"]}},
    {"name": "add_to_playlist", "description": "Add song(s) to a playlist.", "inputSchema": {"type": "object", "properties": {"playlist_id": {"type": "integer", "description": "Playlist ID"}, "song_ids": {"type": "string", "description": "Song ID(s), comma-separated"}}, "required": ["playlist_id", "song_ids"]}},
    {"name": "remove_from_playlist", "description": "Remove song(s) from a playlist.", "inputSchema": {"type": "object", "properties": {"playlist_id": {"type": "integer", "description": "Playlist ID"}, "song_ids": {"type": "string", "description": "Song ID(s) to remove"}}, "required": ["playlist_id", "song_ids"]}},
    {"name": "list_my_playlists", "description": "List all playlists of the logged-in user.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_playlist_songs", "description": "Get all songs in a playlist.", "inputSchema": {"type": "object", "properties": {"playlist_id": {"type": "integer", "description": "Playlist ID"}}, "required": ["playlist_id"]}},
    {"name": "get_play_history", "description": "Get recent play history.", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Number of records, default 30"}, "all_time": {"type": "boolean", "description": "true=all time, false=this week (default)"}}}},
    {"name": "like_song", "description": "Like or unlike a song.", "inputSchema": {"type": "object", "properties": {"song_id": {"type": "integer", "description": "Song ID"}, "like": {"type": "boolean", "description": "true=like, false=unlike"}}, "required": ["song_id"]}},
    {"name": "daily_recommend", "description": "Get today's personalized recommendations.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_current_listening_context", "description": "Read the current NetEase Music macOS Now Playing item and return the current timed lyric line plus the next five lines when available, never the full lyrics. The third line is marked replyTarget to compensate for reply latency; use only that marked line as the short lyric excerpt in the user-facing reply.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "netease_status", "description": "Check NetEase MCP account configuration and macOS client status without exposing credentials.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "netease_playlist_auth_status", "description": "Check whether playlist/account operations are authenticated.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "netease_song_detail", "description": "Get normalized metadata for up to 20 NetEase song IDs.", "inputSchema": {"type": "object", "properties": {"song_ids": {"type": "array", "items": {"type": ["integer", "string"]}, "minItems": 1, "maxItems": 20}}, "required": ["song_ids"]}},
    {"name": "netease_lyrics", "description": "Get original, translated, and romanized lyrics for a NetEase song ID.", "inputSchema": {"type": "object", "properties": {"song_id": {"type": ["integer", "string"]}}, "required": ["song_id"]}},
    {"name": "get_song_comments", "description": "Read normalized public comments for a NetEase song. Login is not required.", "inputSchema": {"type": "object", "properties": {"song_id": {"type": ["integer", "string"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20}, "offset": {"type": "integer", "minimum": 0, "default": 0}}, "required": ["song_id"]}},
    {"name": "send_song_comment", "description": "Publish a public comment on a NetEase song. This is an external write action; call it only when the user has explicitly requested or authorized the comment.", "inputSchema": {"type": "object", "properties": {"song_id": {"type": ["integer", "string"]}, "content": {"type": "string", "minLength": 1, "maxLength": 140}}, "required": ["song_id", "content"]}},
    {"name": "send_private_message", "description": "Send a private text message to a NetEase user ID. This is an external write action; call it only when the user has explicitly requested or authorized the message.", "inputSchema": {"type": "object", "properties": {"user_id": {"type": ["integer", "string"], "description": "Numeric NetEase user ID"}, "content": {"type": "string", "minLength": 1}}, "required": ["user_id", "content"]}},
    {"name": "netease_launch", "description": "Launch the official NetEase Music macOS client.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "netease_listen_together_capabilities", "description": "Report what Listen Together can and cannot do through this MCP.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "netease_listen_together_control", "description": "Directly report a low-level Listen Together room playback command. NEXT/PREVIOUS/GOTO require ids=[formerSongId,targetSongId]; position is seconds and play_status is 0=stopped, 1=paused, 2=playing.", "inputSchema": {"type": "object", "properties": {"command": {"type": "string", "enum": ["PLAY", "PAUSE", "NEXT", "PREVIOUS", "PROGRESS", "GOTO"]}, "ids": {"type": "array", "items": {"type": ["integer", "string"]}, "minItems": 2, "maxItems": 2}, "position": {"type": "number", "minimum": 0}, "play_status": {"type": "integer", "enum": [0, 1, 2]}}, "required": ["command"]}},
    {"name": "netease_listen_together_invite", "description": "Create and activate a Listen Together room with no manual interaction, then send a native NetEase invitation to the configured acceptor account.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "netease_listen_together_leave", "description": "Leave the current Listen Together room without restarting the NetEase Music client.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "netease_listen_together_accept", "description": "Accept an incoming Listen Together invitation from NetEase Music, or automatically accept the latest invitation received in private messages.", "inputSchema": {"type": "object", "properties": {"room_id": {"type": "string", "description": "Optional room ID"}, "inviter_id": {"type": ["integer", "string"], "description": "Optional numeric inviter user ID"}}}}
]

def handle_jsonrpc(body):
    method = body.get('method', '')
    req_id = body.get('id')
    if method == 'initialize':
        return {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "netease-listen-together", "version": "1.0.0"}}}
    elif method == 'tools/list':
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    elif method == 'tools/call':
        name = body.get('params', {}).get('name', '')
        args = body.get('params', {}).get('arguments', {})
        if name == 'play_music':
            text = play_music(args.get('query', ''), args.get('note'), args.get('artist'), args.get('song_id'))
        elif name == 'netease_playback_control':
            text = netease_playback_control(args.get('command'))
        elif name == 'create_playlist':
            text = create_playlist(args.get('name', ''), args.get('description', ''), args.get('privacy', 0))
        elif name == 'add_to_playlist':
            text = add_to_playlist(args.get('playlist_id'), args.get('song_ids', ''))
        elif name == 'remove_from_playlist':
            text = remove_from_playlist(args.get('playlist_id'), args.get('song_ids', ''))
        elif name == 'list_my_playlists':
            text = list_my_playlists()
        elif name == 'get_playlist_songs':
            text = get_playlist_songs(args.get('playlist_id'))
        elif name == 'get_play_history':
            text = get_play_history(args.get('limit', 30), args.get('all_time', False))
        elif name == 'like_song':
            text = like_song(args.get('song_id'), args.get('like', True))
        elif name == 'daily_recommend':
            text = daily_recommend()
        elif name == 'get_current_listening_context':
            text = get_current_listening_context()
        elif name == 'netease_status':
            text = netease_status()
        elif name == 'netease_playlist_auth_status':
            text = netease_playlist_auth_status()
        elif name == 'netease_song_detail':
            text = netease_song_detail(args.get('song_ids'))
        elif name == 'netease_lyrics':
            text = netease_lyrics(args.get('song_id'))
        elif name == 'get_song_comments':
            text = get_song_comments(
                args.get('song_id'),
                args.get('limit', 20),
                args.get('offset', 0),
            )
        elif name == 'send_song_comment':
            text = send_song_comment(
                args.get('song_id'),
                args.get('content', ''),
            )
        elif name == 'send_private_message':
            text = send_private_message(
                args.get('user_id'),
                args.get('content', ''),
            )
        elif name == 'netease_launch':
            text = netease_launch()
        elif name == 'netease_listen_together_capabilities':
            text = netease_listen_together_capabilities()
        elif name == 'netease_listen_together_control':
            text = netease_listen_together_control(args.get('command'), args.get('ids'), args.get('position'), args.get('play_status'))
        elif name == 'netease_listen_together_invite':
            text = netease_listen_together_invite()
        elif name == 'netease_listen_together_leave':
            text = netease_listen_together_leave()
        elif name == 'netease_listen_together_accept':
            text = netease_listen_together_accept(args.get('room_id'), args.get('inviter_id'))
        else:
            text = "Unknown tool: " + name
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}]}}
    elif method.startswith('notifications/'):
        return None
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Unknown method: " + method}}

def run_stdio():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            body = json.loads(line)
            result = handle_jsonrpc(body)
            if result is not None and body.get('id') is not None:
                sys.stdout.write(json.dumps(result, ensure_ascii=False) + '\n')
                sys.stdout.flush()
        except Exception as e:
            error = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error: " + str(e)}
            }
            sys.stdout.write(json.dumps(error, ensure_ascii=False) + '\n')
            sys.stdout.flush()

if __name__ == '__main__':
    run_stdio()
