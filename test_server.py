import importlib.util
import json
import pathlib
import unittest
from unittest import mock


SERVER_PATH = pathlib.Path(__file__).with_name('server.py')
SPEC = importlib.util.spec_from_file_location('netease_listen_together_server', SERVER_PATH)
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class ServerTest(unittest.TestCase):
    def test_public_build_has_no_default_acceptor(self):
        self.assertEqual(SERVER.NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID, '')

    def test_expected_tools_are_registered(self):
        names = {tool['name'] for tool in SERVER.TOOLS}
        expected = {
            'play_music',
            'netease_status',
            'netease_song_detail',
            'netease_lyrics',
            'get_song_comments',
            'send_song_comment',
            'send_private_message',
            'netease_listen_together_capabilities',
            'netease_listen_together_invite',
            'netease_listen_together_control',
            'netease_listen_together_leave',
        }
        self.assertTrue(expected.issubset(names))

    def test_numeric_ids_are_strict(self):
        self.assertEqual(SERVER._validate_numeric_id('123'), '123')
        with self.assertRaises(ValueError):
            SERVER._validate_numeric_id('123?x=1')

    def test_initialize_uses_public_server_name(self):
        result = SERVER.handle_jsonrpc({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
        })
        self.assertEqual(
            result['result']['serverInfo']['name'],
            'netease-listen-together',
        )

    @mock.patch.object(SERVER, 'netease_request')
    def test_song_comments_are_normalized(self, request):
        request.return_value = {
            'code': 200,
            'total': 1,
            'comments': [{
                'commentId': 9,
                'content': 'hello',
                'user': {'userId': 3, 'nickname': 'tester'},
            }],
        }
        result = json.loads(SERVER.get_song_comments('123'))
        self.assertEqual(result['songId'], '123')
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['comments'][0]['content'], 'hello')

    def test_invite_requires_explicit_acceptor_configuration(self):
        with mock.patch.object(SERVER, '_require_macos_client', return_value=None):
            result = json.loads(SERVER.netease_listen_together_invite())
        self.assertFalse(result['success'])
        self.assertIn('not configured', result['message'])


if __name__ == '__main__':
    unittest.main()
