"""Regression tests: no authenticated redirects and no ambiguous --version routing."""
import contextlib
import io
import os
import unittest
from unittest.mock import patch

import rr_entry as entry
import runrunit_api as api


REDIRECT_CODES = (301, 302, 303, 307, 308)
CROSS_ORIGIN = 'https://evil.example/collect'
PLAIN_HTTP = 'http://runrun.it.evil.example/api/v1.0/tasks'
SAME_ORIGIN = 'https://runrun.it/api/v1.0/tasks?page=2'
BASE_TASK_URL = 'https://runrun.it/api/v1.0/tasks'


def post_request():
    return api.Request(
        BASE_TASK_URL,
        data=b'{"task": {"title": "x"}}',
        headers={'App-Key': 'mock-app-key', 'User-Token': 'mock-user-token'},
        method='POST',
    )


class RedirectBlockingTests(unittest.TestCase):
    def test_every_redirect_status_is_refused_before_a_second_request(self):
        for code in REDIRECT_CODES:
            for target in (CROSS_ORIGIN, PLAIN_HTTP, SAME_ORIGIN):
                with self.subTest(code=code, target=target):
                    request = post_request()
                    handler = api.NoRedirectHandler()
                    with patch('urllib.request.Request') as rebuilt:
                        with self.assertRaises(api.RedirectBlockedError) as caught:
                            getattr(handler, f'http_error_{code}')(
                                request, io.BytesIO(b'redirect body'), code, 'Found',
                                {'location': target},
                            )
                        rebuilt.assert_not_called()
                    self.assertEqual(caught.exception.code, code)
                    self.assertEqual(request.get_method(), 'POST')
                    self.assertEqual(request.get_full_url(), BASE_TASK_URL)
                    self.assertEqual(request.headers['App-key'], 'mock-app-key')

    def test_real_opener_dispatch_blocks_all_statuses(self):
        opener = api.build_opener(api.NoRedirectHandler())
        for code in REDIRECT_CODES:
            with self.subTest(code=code):
                with self.assertRaises(api.RedirectBlockedError):
                    opener.error(
                        'http', post_request(), io.BytesIO(b''), code, 'Found',
                        {'location': CROSS_ORIGIN},
                    )

    def test_reported_origin_hides_userinfo_and_query(self):
        self.assertEqual(
            api._reported_origin('https://user:secret@evil.example:8443/steal?token=secret'),
            'https://evil.example:8443',
        )
        self.assertEqual(api._reported_origin('/relative?token=secret'), '(relative)')

    def test_urlopen_installs_the_blocking_handler(self):
        with patch.object(api, 'build_opener') as builder:
            api.urlopen(post_request(), timeout=7)
        handlers = builder.call_args.args[0]
        self.assertIsInstance(handlers, api.NoRedirectHandler)
        builder.return_value.open.assert_called_once()
        self.assertEqual(builder.return_value.open.call_args.kwargs, {'timeout': 7})

    def test_call_fails_closed_without_reopening_the_request(self):
        opened = []

        def fake_open(request, timeout=30):
            opened.append((request, timeout))
            raise api.RedirectBlockedError(302, 'https://evil.example')

        credentials = {'RUNRUNIT_APP_KEY': 'mock-app-key', 'RUNRUNIT_USER_TOKEN': 'mock-user-token'}
        with patch.dict(os.environ, credentials, clear=True), \
                patch.object(api, 'urlopen', side_effect=fake_open) as open_request:
            with self.assertRaises(SystemExit) as caught:
                api.call('POST', '/tasks', {'task': {'title': 'x'}})
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0][0].get_method(), 'POST')
        self.assertEqual(open_request.call_count, 1)
        message = str(caught.exception)
        self.assertIn('https://evil.example', message)
        self.assertIn('credentials were not re-sent', message)
        self.assertNotIn('mock-app-key', message)
        self.assertNotIn('mock-user-token', message)

    def test_successful_response_contract_is_preserved(self):
        class FakeResponse:
            status = 200
            headers = {'Content-Type': 'application/json', 'ETag': '"v1"'}

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def read(self):
                return b'{"id": 123}'

        credentials = {'RUNRUNIT_APP_KEY': 'mock-app-key', 'RUNRUNIT_USER_TOKEN': 'mock-user-token'}
        with patch.dict(os.environ, credentials, clear=True), \
                patch.object(api, 'urlopen', return_value=FakeResponse()) as open_request:
            result = api.call('PUT', '/tasks/123', {'task': {'title': 'x'}}, if_none_match='"v0"')
        self.assertEqual(result, {
            'status': 200,
            'headers': {'Content-Type': 'application/json', 'ETag': '"v1"'},
            'body': {'id': 123},
        })
        self.assertEqual(open_request.call_count, 1)
        request = open_request.call_args.args[0]
        self.assertEqual(request.get_method(), 'PUT')
        self.assertEqual(request.headers['App-key'], 'mock-app-key')
        self.assertEqual(request.headers['User-token'], 'mock-user-token')
        self.assertEqual(request.headers['If-none-match'], '"v0"')
        self.assertEqual(open_request.call_args.kwargs, {'timeout': 30})


class VersionRoutingTests(unittest.TestCase):
    def test_isolated_version_option_prints_without_running_the_cli(self):
        out = io.StringIO()
        with patch.object(entry, 'load_config'), \
                patch('importlib.metadata.version', return_value='9.9.9') as get_version, \
                patch('rr_cli.main') as cli_main, \
                contextlib.redirect_stdout(out):
            entry.main(['--version'])
        self.assertEqual(out.getvalue().strip(), '9.9.9')
        get_version.assert_called_once_with('runrunit-cli')
        cli_main.assert_not_called()

    def test_literal_version_after_separator_reaches_the_operational_parser(self):
        calls = []

        def fake_call(method, path, data=None, *args, **kwargs):
            calls.append((method, path, data))
            if method == 'GET' and path == '/tasks/123':
                return {'status': 200, 'body': {'id': 123, 'assignments': []}}
            if method == 'POST' and path == '/comments':
                return {'status': 201, 'body': {'id': 7}}
            return {'status': 200, 'body': {'id': 7, 'task_id': 123, 'text': '--version'}}

        with patch.object(entry, 'load_config'), \
                patch.object(api, 'call', side_effect=fake_call), \
                patch('importlib.metadata.version') as get_version, \
                contextlib.redirect_stdout(io.StringIO()):
            entry.main(['comentar', '123', '--confirmar', '123', '--', '--version'])
        self.assertEqual([call[0] for call in calls], ['GET', 'POST', 'GET'])
        self.assertEqual(calls[0][1], '/tasks/123')
        self.assertEqual(calls[1][1], '/comments')
        self.assertEqual(calls[1][2], {'task_id': '123', 'text': '--version'})
        self.assertEqual(calls[2][1], '/comments/7')
        get_version.assert_not_called()


if __name__ == '__main__':
    unittest.main()
