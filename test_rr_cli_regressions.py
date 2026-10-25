import contextlib
from datetime import datetime
import io
import json
import os
import unittest
from unittest.mock import patch

import rr_cli as cli
import runrunit_api as api


@contextlib.contextmanager
def no_configured_user():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('RUNRUNIT_USER_ID', None)
        yield


def make_task(task_id, user, title='Tarefa', desired_date=None, working=False, project_id=None):
    return {
        'id': task_id,
        'title': title,
        'is_closed': False,
        'desired_date': desired_date,
        'is_urgent': False,
        'project_id': project_id,
        'project_name': 'Projeto' if project_id else None,
        'assignments': [{'assignee_id': user, 'is_closed': False, 'is_working_on': working}],
    }


def run_json(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        cli.main(args + ['--json'])
    return json.loads(out.getvalue())


class IdentityResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [
            make_task(1, 'owner-token', title='Do dono'),
            make_task(2, 'config-user', title='Da configuração'),
            make_task(3, 'explicit-user', title='Do argumento'),
            make_task(4, 'hendrix-freire', title='Do fallback removido'),
        ]
        self.calls = []
        self.page_paths = []

    def fake_paginate(self, path, max_pages, max_items):
        self.page_paths.append(path)
        return {'status': 200, 'body': self.tasks, 'truncated': False}

    def fake_identity(self, method, path, data=None, **kwargs):
        self.calls.append((method, path))
        if path == '/users?me_first=true&limit=1':
            return {'status': 200, 'body': [{'id': 'owner-token'}]}
        raise AssertionError(f'chamada inesperada: {method} {path}')

    def run_list(self, args):
        with patch.object(api, 'paginate', side_effect=self.fake_paginate):
            return run_json(args)

    def test_default_identity_is_token_owner_not_hardcoded_slug(self):
        with no_configured_user(), patch.object(api, 'call', side_effect=self.fake_identity):
            result = self.run_list(['minhas'])
        self.assertEqual([t['id'] for t in result['body']], [1])
        self.assertIn('owner-token', result['scope'])
        self.assertEqual(self.calls, [('GET', '/users?me_first=true&limit=1')])
        self.assertIn('assignee_id=owner-token', self.page_paths[0])

    def test_explicit_user_wins_over_config_without_identity_request(self):
        with patch.dict(os.environ, {'RUNRUNIT_USER_ID': 'config-user'}, clear=False), \
                patch.object(api, 'call', side_effect=AssertionError('não deveria consultar identidade')):
            result = self.run_list(['minhas', '--usuario', 'explicit-user'])
        self.assertEqual([t['id'] for t in result['body']], [3])
        self.assertIn('explicit-user', result['scope'])
        self.assertIn('assignee_id=explicit-user', self.page_paths[0])

    def test_configured_user_is_used_without_identity_request(self):
        with patch.dict(os.environ, {'RUNRUNIT_USER_ID': ' config-user '}, clear=False), \
                patch.object(api, 'call', side_effect=AssertionError('não deveria consultar identidade')):
            result = self.run_list(['minhas'])
        self.assertEqual([t['id'] for t in result['body']], [2])
        self.assertIn('assignee_id=config-user', self.page_paths[0])

    def test_failed_identity_resolution_requires_configuration(self):
        with no_configured_user(), patch.object(api, 'paginate', side_effect=self.fake_paginate), \
                patch.object(api, 'call', side_effect=SystemExit(1)):
            with self.assertRaises(SystemExit) as raised:
                cli.main(['minhas'])
        message = str(raised.exception)
        self.assertIn('RUNRUNIT_USER_ID', message)
        self.assertIn('--usuario', message)

    def test_invalid_explicit_user_reports_configuration_error(self):
        with patch.object(api, 'paginate', side_effect=AssertionError('sem rede')), \
                patch.object(api, 'call', side_effect=AssertionError('sem rede')):
            with self.assertRaises(SystemExit) as raised:
                cli.main(['minhas', '--usuario', 'usuario inválido'])
        self.assertIn('RUNRUNIT_USER_ID', str(raised.exception))

    def test_help_and_non_identity_commands_do_not_resolve_identity(self):
        with patch.object(api, 'call', side_effect=AssertionError('sem rede')), \
                patch.object(api, 'paginate', side_effect=AssertionError('sem rede')):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
                cli.main(['--help'])
            self.assertEqual(raised.exception.code, 0)
            self.assertIn('minhas', out.getvalue())

    def test_ver_reads_only_task_and_description(self):
        task = make_task(123, 'alguem')
        paths = []

        def fake(method, path, data=None, **kwargs):
            paths.append((method, path))
            if path == '/tasks/123':
                return {'status': 200, 'body': task}
            if path == '/tasks/123/description':
                return {'status': 200, 'body': {'description': 'Descrição'}}
            raise AssertionError((method, path))

        with patch.object(api, 'call', side_effect=fake):
            result = run_json(['ver', '123'])
        self.assertEqual(paths, [('GET', '/tasks/123'), ('GET', '/tasks/123/description')])
        self.assertEqual(result['description'], 'Descrição')

    def test_six_routines_filter_and_scope_resolved_identity(self):
        today = datetime.now(cli.TZ).date().isoformat()
        self.tasks = [
            make_task(1, 'explicit-user', title='Relatório hoje', desired_date=today,
                      working=True, project_id='p1'),
            make_task(2, 'explicit-user', title='Relatório atrasado', desired_date='2000-01-01'),
            make_task(3, 'outra-pessoa', title='Relatório alheio', desired_date=today, working=True),
        ]
        expected = {'minhas': [1, 2], 'buscar': [1, 2], 'hoje': [1],
                    'atrasadas': [2], 'trabalhando': [1]}
        with patch.object(api, 'paginate', side_effect=self.fake_paginate), \
                patch.object(api, 'call', side_effect=AssertionError('não deveria consultar identidade')):
            for command, ids in expected.items():
                with self.subTest(command=command):
                    args = [command, '--usuario', 'explicit-user']
                    if command == 'buscar':
                        args.insert(1, 'Relatório')
                    result = run_json(args)
                    self.assertEqual([t['id'] for t in result['body']], ids)
                    self.assertIn('explicit-user', result['scope'])
                    self.assertEqual(result['items_returned'], len(ids))
            summary = run_json(['resumo', '--por', 'projeto', '--usuario', 'explicit-user'])
        self.assertEqual(summary['body']['total'], 2)
        self.assertEqual(summary['body']['por'], 'projeto')
        self.assertEqual(summary['body']['grupos']['p1 | Projeto'], 1)
        self.assertEqual(summary['body']['grupos']['- | Sem projeto'], 1)


class CreateDescriptionVerificationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.description_value = '<p>Descrição &amp; <cliente></p>'
        self.description_error = False
        self.task = {'id': 55, 'title': 'Nova', 'board_id': '1', 'type_id': '2'}

    def fake(self, method, path, data=None, **kwargs):
        self.calls.append((method, path, data))
        if method == 'GET' and path in ('/boards/1', '/task_types/2'):
            return {'status': 200, 'body': {'id': path.rsplit('/', 1)[-1]}}
        if method == 'POST' and path == '/tasks':
            self.task.update({k: v for k, v in data['task'].items() if k != 'description'})
            return {'status': 201, 'body': {'id': 55}}
        if method == 'GET' and path == '/tasks/55':
            return {'status': 200, 'body': dict(self.task)}
        if method == 'GET' and path == '/tasks/55/description':
            if self.description_error:
                raise SystemExit(1)
            return {'status': 200, 'body': {'description': self.description_value}}
        raise AssertionError(f'chamada inesperada: {method} {path}')

    def create(self, description):
        args = ['criar', 'Nova', '--quadro', '1', '--tipo', '2',
                '--descricao', description, '--confirmar', 'CRIAR', '--json']
        with patch.object(api, 'call', side_effect=self.fake):
            return run_json(args)

    def posts(self):
        return [c for c in self.calls if c[0] == 'POST' and c[1] == '/tasks']

    def test_matching_description_is_verified_and_posted_once(self):
        result = self.create(self.description_value)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(result['description'], self.description_value)
        self.assertEqual(result['verification'], 'confirmado por leitura após a escrita')

    def test_divergent_description_fails_reconciliation_without_second_post(self):
        self.description_value = '<p>WRONG</p>'
        with self.assertRaises(SystemExit) as raised:
            self.create('<p>EXPECTED</p>')
        self.assertIn('Reconcilie', str(raised.exception))
        self.assertEqual(len(self.posts()), 1)

    def test_missing_description_fails_reconciliation_without_second_post(self):
        self.description_error = True
        with self.assertRaises(SystemExit) as raised:
            self.create('<p>EXPECTED</p>')
        self.assertIn('Reconcilie', str(raised.exception))
        self.assertEqual(len(self.posts()), 1)

    def test_creation_without_description_does_not_read_the_resource(self):
        args = ['criar', 'Nova', '--quadro', '1', '--tipo', '2',
                '--confirmar', 'CRIAR', '--json']
        with patch.object(api, 'call', side_effect=self.fake):
            result = run_json(args)
        self.assertIn('verification', result)
        self.assertFalse(any(path.endswith('/description') for _, path, _ in self.calls))
        self.assertEqual(len(self.posts()), 1)


class PreviewLiteralTests(unittest.TestCase):
    PAYLOAD = ('<b>Cliente &amp; &lt;cliente&gt;</b> '
               '<a href="https://exemplo.test/?a=1&b=2">link</a>\x1b[31m')

    def test_literal_preserves_html_entities_and_escapes_controls(self):
        self.assertEqual(cli.literal('<b>&amp;</b>\x1b[31m\r\t'),
                         '<b>&amp;</b>\\x1b[31m\\x0d\\x09')
        self.assertNotIn('<b>', cli.plain('<b>&amp;</b>'))
        self.assertNotIn('&amp;', cli.plain('<b>&amp;</b>'))

    def test_comment_preview_keeps_authorized_payload_literal(self):
        task = {'id': 123, 'title': 'Tarefa', 'assignments': []}

        def fake(method, path, data=None, **kwargs):
            if method == 'GET' and path == '/tasks/123':
                return {'status': 200, 'body': task}
            raise AssertionError((method, path))

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(api, 'call', side_effect=fake), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            cli.main(['comentar', '123', self.PAYLOAD, '--dry-run', '--json'])
        result = json.loads(stdout.getvalue())
        self.assertEqual(result['body']['data']['text'], self.PAYLOAD)
        preview = stderr.getvalue()
        for literal in ('<b>', '&amp;', '&lt;cliente&gt;', '<a href=', 'https://exemplo.test/?a=1&b=2'):
            self.assertIn(literal, preview)
        self.assertNotIn('\x1b', preview)
        self.assertIn('\\u001b', preview)


if __name__ == '__main__':
    unittest.main()
