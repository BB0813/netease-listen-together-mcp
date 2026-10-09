global.window = global;
global.document = {
  createElement: () => ({ style: {} }),
  addEventListener: () => {},
  removeEventListener: () => {}
};
try { delete global.navigator; } catch (e) {}
Object.defineProperty(global, 'navigator', {
  value: { userAgent: 'Node' },
  writable: true,
  configurable: true
});
global.WebSocket = require('ws');

const SDK = require('@yxim/nim-web-sdk');
const NIM = SDK.NIM;
const Chatroom = SDK.Chatroom;
const APP_KEY = '3a6a3e48f6854dfa4e4464f3bdaec3b4';

let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  const params = JSON.parse(input || '{}');
  const account = String(params.account);
  const token = String(params.token);
  const chatroomId = String(params.chatroomId);
  const limit = Math.min(100, Math.max(1, Number(params.limit || 20)));
  const sinceId = params.sinceId ? String(params.sinceId).trim() : null;

  let finished = false;
  const timer = setTimeout(() => {
    if (!finished) {
      finished = true;
      console.log(JSON.stringify({ success: false, error: 'timeout' }));
      process.exit(1);
    }
  }, 10000);

  const nim = NIM.getInstance({
    appKey: APP_KEY,
    account,
    token,
    debug: false,
    onconnect() {
      nim.getChatroomAddress({
        chatroomId,
        done(err, addr) {
          if (err) {
            cleanup(err);
            return;
          }
          const chatroom = Chatroom.getInstance({
            appKey: APP_KEY,
            account,
            token,
            chatroomId,
            chatroomAddresses: addr.address,
            debug: false,
            onconnect() {
              chatroom.getHistoryMsgs({
                timetag: Date.now(),
                limit: Math.max(limit, 50),
                done(hErr, obj) {
                  if (hErr) {
                    cleanup(hErr);
                    return;
                  }
                  const rawList = obj?.msgs || [];
                  const textMsgs = [];
                  for (const m of rawList) {
                    if (m.type === 'text' && m.text && m.text.trim()) {
                      let nickname = m.fromNick;
                      let userId = m.from;
                      try {
                        const custom = JSON.parse(m.custom || '{}');
                        const sExt = custom.serverExt || {};
                        if (sExt.nickname) nickname = sExt.nickname;
                        if (sExt.userId) userId = String(sExt.userId);
                      } catch (e) {}

                      textMsgs.push({
                        id: m.idClient || String(m.time),
                        time: m.time,
                        timeStr: new Date(m.time).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }),
                        sender: (String(userId) === String(account)) ? 'me' : 'partner',
                        fromUserId: userId,
                        fromNickname: nickname || (String(userId) === String(account) ? '我' : '对方'),
                        content: m.text
                      });
                    }
                  }

                  textMsgs.sort((a, b) => a.time - b.time);

                  let filtered = textMsgs;
                  if (sinceId) {
                    const idx = filtered.findIndex(x => x.id === sinceId);
                    if (idx !== -1) {
                      filtered = filtered.slice(idx + 1);
                    }
                  }
                  if (filtered.length > limit) {
                    filtered = filtered.slice(-limit);
                  }

                  const lastId = filtered.length > 0 ? filtered[filtered.length - 1].id : (sinceId || null);
                  cleanup(null, {
                    success: true,
                    chatroomId,
                    count: filtered.length,
                    hasNew: filtered.length > 0,
                    lastMessageId: lastId,
                    messages: filtered
                  });
                }
              });
            },
            onerror(cErr) { cleanup(cErr); }
          });

          function cleanup(err, result) {
            if (finished) return;
            finished = true;
            clearTimeout(timer);
            try { chatroom.disconnect(); } catch (e) {}
            try { nim.disconnect(); } catch (e) {}
            if (err) {
              console.log(JSON.stringify({ success: false, error: String(err.message || err) }));
            } else {
              console.log(JSON.stringify(result));
            }
            process.exit(0);
          }
        }
      });
    },
    onerror(nErr) {
      if (!finished) {
        finished = true;
        clearTimeout(timer);
        console.log(JSON.stringify({ success: false, error: String(nErr.message || nErr) }));
        process.exit(1);
      }
    }
  });
});
