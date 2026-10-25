import contextlib
from datetime import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import rr_cli as cli
import rr_upload as upload
import runrunit_api as api


class ExtendedTests(unittest.TestCase):
    def setUp(self):
        self.task = {'id': 123, 'title': 'Original', 'board_id': 1, 'board_stage_id': 2,
                     'team_id': 5, 'is_closed': False, 'is_urgent': False, 'desired_date': None,
                     'assignments': [], 'tags_data': [{'name': 'manter', 'color': '#123456'}, {'name': 'remover'}]}
        self.calls = []
        self.description = 'Antes'
        self.item = {'id': 9, 'checklist_id': 7, 'description': 'Antes', 'checked': False}
        self.container = {'id': 7, 'task_id': 123, 'title': 'Lista'}

    def fake(self, method, path, data=None, **kwargs):
        self.calls.append((method, path, data))
        b = self.task
        if method == 'GET':
            if path.startswith('/tags?'): b = []
            elif path.endswith('/description'): b = {'description': self.description}
            elif path == '/users?me_first=true&limit=1': b = [{'id': 'me'}]
            elif path == '/tasks/123/checklist': b = self.container
            elif path == '/checklists/7/items/9': b = self.item
            elif path.startswith('/boards/'): b = {'id': path.rsplit('/', 1)[-1], 'board_id': 1}
            elif path.startswith(('/teams/', '/users/', '/task_types/', '/projects/')): b = {'id': path.rsplit('/', 1)[-1]}
            elif path.startswith('/comments/'): b = {'id': 44, 'task_id': 123, 'text': 'Olá'}
            elif path.startswith('/manual_work_periods/'): b = self.record
        elif path == '/tasks':
            self.task.update(data['task']); b = {'id': 123}
        elif path == '/tasks/123/description': self.description = data['task_description']['description']
        elif path == '/tasks/123' and method == 'PUT': self.task.update(data['task'])
        elif path.endswith('/move'): self.task['board_stage_id'] = data['board_stage_id']
        elif path.endswith('/deliver'): self.task['is_closed'] = True
        elif path.endswith('/reopen'): self.task['is_closed'] = False
        elif path.endswith('/mark_as_urgent'): self.task['is_urgent'] = True
        elif path.endswith('/unmark_as_urgent'): self.task['is_urgent'] = False
        elif path.endswith(('/play', '/pause')): self.task['assignments'] = [{'assignee_id': 'me', 'is_working_on': path.endswith('/play')}]
        elif path.endswith('/create_assignments'): self.task['assignments'] = data['assignments']
        elif method == 'DELETE' and '/assignments/' in path: self.task['assignments'] = []
        elif path == '/comments': b = {'id': 44}
        elif path == '/manual_work_periods': self.record = data['manual_work_period']; b = {'id': 45}
        elif path == '/tasks/123/checklist':
            if not self.container: self.container = {'id': 7, 'task_id': 123}
            self.container.update(data['checklist']); b = self.container
        elif path.startswith('/checklists/7/items'):
            if data: self.item.update(data['checklist_item'])
            b = self.item
        return {'status': 200, 'body': b, 'headers': {}}

    def run_cli(self, args):
        out = io.StringIO()
        with patch.object(api, 'call', side_effect=self.fake), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            cli.main(args + ['--json'])
        return json.loads(out.getvalue())

    def test_task_mutations_and_verification(self):
        cases = [['entregar', '123'], ['reabrir', '123'], ['mover', '123', '--etapa', '3'],
                 ['prazo', '123', '2026-10-30'], ['prazo', '123', '--limpar'],
                 ['editar', '123', '--titulo', 'Novo', '--descricao', 'Depois'],
                 ['urgente', '123'], ['urgente', '123', '--remover'],
                 ['iniciar', '123'], ['pausar', '123'], ['comentar', '123', 'Olá'],
                 ['atribuir', '123', '--usuario', 'alguem'],
                 ['horas', '123', '--duracao', '1h30', '--data', '2026-10-23']]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(args + ['--confirmar', '123'])
                self.assertIn('verification', result)
        self.assertEqual(self.record['seconds'], 5400)
        self.assertEqual(self.record['board_stage_id'], '3')

    def test_tags_preserve_color_and_unrelated_tags(self):
        self.run_cli(['tags', '123', '--adicionar', 'nova', '--remover', 'remover', '--confirmar', '123'])
        self.assertEqual(self.task['tags_data'], [{'name': 'manter', 'color': '#123456'}, {'name': 'nova'}])

    def test_remove_uses_assignment_id(self):
        self.task['assignments'] = [{'id': 'assignment-abc', 'assignee_id': 'alguem'}]
        self.run_cli(['atribuir', '123', '--usuario', 'alguem', '--remover', '--confirmar', '123'])
        self.assertIn(('DELETE', '/tasks/123/assignments/assignment-abc', None), self.calls)

    def test_create_validates_reference_ids(self):
        result = self.run_cli(['criar', 'Nova', '--quadro', '1', '--tipo', '2', '--projeto', '3', '--etapa', '4', '--confirmar', 'CRIAR'])
        self.assertIn('verification', result)
        self.assertEqual([c[1] for c in self.calls[:4]], ['/boards/1', '/task_types/2', '/projects/3', '/boards/1/stages/4'])

    def test_checklist_writes(self):
        for args in [['--titulo', 'Nova lista'], ['--adicionar', 'Novo item'], ['--concluir', '9'], ['--reabrir', '9'], ['--editar-item', '9', '--texto', 'Editado']]:
            with self.subTest(args=args):
                self.assertIn('verification', self.run_cli(['checklist', '123'] + args + ['--confirmar', '123']))
        self.container = None
        self.assertIn('verification', self.run_cli(['checklist', '123', '--criar', 'Lista nova', '--confirmar', '123']))

    def test_all_mutations_support_dry_run_without_writes(self):
        commands = [['criar', 'Nova', '--quadro', '1', '--tipo', '2'], ['entregar', '123'],
                    ['reabrir', '123'], ['mover', '123', '--etapa', '3'], ['prazo', '123', '--limpar'],
                    ['editar', '123', '--descricao', 'Nova'], ['urgente', '123'],
                    ['atribuir', '123', '--usuario', 'alguem'], ['tags', '123', '--adicionar', 'tag'],
                    ['checklist', '123', '--concluir', '9'], ['horas', '123', '--duracao', '90m', '--data', '2026-10-23']]
        for args in commands:
            with self.subTest(args=args):
                self.calls.clear()
                self.assertTrue(self.run_cli(args + ['--dry-run'])['preview'])
                self.assertTrue(all(c[0] == 'GET' for c in self.calls))

    def test_wrong_confirmation_and_divergent_readback(self):
        with self.assertRaises(SystemExit): self.run_cli(['entregar', '123', '--confirmar', '999'])
        self.assertTrue(all(c[0] == 'GET' for c in self.calls))
        with self.assertRaises(SystemExit): cli.checked({'body': {}}, False)

    def test_dates_timezone_and_durations(self):
        self.assertEqual(cli.due_day({'desired_date': '2026-10-24T01:00:00Z'}).isoformat(), '2026-10-23')
        for value in ('1h30', '1h30m', '90m', '5400s'):
            self.assertEqual(cli.parse_duration(value), 5400)
        for value in ('0h', '-1h', 'abc'):
            with self.assertRaises(Exception): cli.parse_duration(value)
        with self.assertRaises(Exception): cli.iso_date('2026-02-30')

    def test_today_late_working_and_summary_preserve_partial(self):
        today = datetime.now(cli.TZ).date().isoformat()
        tasks = [dict(self.task, desired_date=today, assignments=[{'assignee_id': 'me', 'is_closed': False, 'is_working_on': True}]),
                 dict(self.task, desired_date='2000-01-01', assignments=[{'assignee_id': 'me', 'is_closed': False, 'is_working_on': False}])]
        for cmd, count in [('hoje', 1), ('atrasadas', 1), ('trabalhando', 1), ('resumo', 2)]:
            with self.subTest(cmd=cmd), patch.object(api, 'paginate', return_value={'status': 200, 'body': tasks, 'truncated': True}):
                r = self.run_cli([cmd, '--usuario', 'me'])
                self.assertTrue(r['truncated']); self.assertEqual(r['items_returned'], count)

    def test_browser_opens_known_url(self):
        with patch.object(cli.webbrowser, 'open', return_value=True) as browser:
            self.run_cli(['abrir', '123'])
            browser.assert_called_once_with('https://runrun.it/pt-BR/tasks/123')

    def test_upload_dry_run_and_multipart(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d)/'relatorio.txt'; file.write_bytes(b'conteudo')
            self.calls.clear()
            result = self.run_cli(['anexar', '123', str(file), '--dry-run'])
            self.assertEqual(result['body']['file_size'], 8)
            self.assertTrue(all(c[0] == 'GET' for c in self.calls))
        body, boundary, size = upload.multipart({'key': 'abc', 'Policy': 'signed'}, 'x.txt', io.BytesIO(b'conteudo'))
        with body:
            content = body.read()
            self.assertEqual(len(content), size)
            self.assertTrue(content.endswith(('--' + boundary + '--\r\n').encode()))
            self.assertIn(b'conteudo', content)
            self.assertNotIn(b'App-Key', content)

    def test_upload_full_sequence_and_no_retry(self):
        class Response:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Opener:
            def open(self, req, timeout):
                assert not any(k.lower() in ('app-key', 'user-token') for k in req.headers)
                return Response()
        def fake(method, path, data=None, **kwargs):
            self.calls.append((method, path, data))
            if path.startswith('/documents?'): return {'body': {'id': 88, 'fields': {'key': 'x'}, 'upload_url': 'https://storage.example/upload'}}
            if path == '/documents/88': return {'body': {'id': 88, 'attachable_id': 123, 'transfered': True, 'file_size': 8}}
            return {'body': self.task}
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            file = Path(d)/'x.txt'; file.write_bytes(b'conteudo')
            with patch.object(api, 'call', side_effect=fake), patch.object(upload, 'build_opener', return_value=Opener()), patch.object(upload, 'download_hash', return_value=hashlib.sha256(b'conteudo').hexdigest()), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main(['anexar', '123', str(file), '--confirmar', '123', '--json'])
        self.assertEqual([c[:2] for c in self.calls], [('GET', '/tasks/123'), ('POST', '/documents?task_id=123'), ('POST', '/documents/88/mark_as_uploaded'), ('GET', '/documents/88')])

    def test_checklist_delete_verifies_absence(self):
        with patch.object(api, 'paginate', return_value={'status': 200, 'body': [], 'truncated': False}):
            result = self.run_cli(['checklist', '123', '--excluir-item', '9', '--confirmar', '123'])
        self.assertIn('verification', result)
        self.assertIn(('DELETE', '/checklists/7/items/9', None), self.calls)

    def test_write_timeout_is_not_retried(self):
        def fail(method, path, data=None, **kw):
            if method != 'GET':
                self.calls.append((method, path, data))
                raise SystemExit('timeout')
            return self.fake(method, path, data, **kw)
        with patch.object(api, 'call', side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): cli.main(['entregar', '123', '--confirmar', '123'])
        self.assertEqual(len([c for c in self.calls if c[0] == 'POST']), 1)

    def test_download_redirect_drops_credentials(self):
        from urllib.error import HTTPError
        from email.message import Message
        headers = Message(); headers['Location'] = 'https://storage.example/signed'
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
        opener = unittest.mock.Mock()
        opener.open.side_effect = [HTTPError('url', 302, 'redirect', headers, None), Response(b'conteudo')]
        with patch.object(api, 'credentials', return_value=('test-key', 'test-token')), patch.object(upload, 'build_opener', return_value=opener):
            upload.download_hash(88)
        first, second = [c.args[0] for c in opener.open.call_args_list]
        self.assertEqual(first.get_header('App-key'), 'test-key')
        self.assertEqual(second.headers, {})

    def test_no_checklist_and_wrong_parent(self):
        self.container = None
        self.assertIsNone(self.run_cli(['checklist', '123'])['body'])
        self.container = {'id': 7, 'task_id': 999}
        with self.assertRaises(SystemExit): self.run_cli(['checklist', '123', '--concluir', '9', '--confirmar', '123'])
        self.assertTrue(all(c[0] == 'GET' for c in self.calls))


if __name__ == '__main__': unittest.main()
