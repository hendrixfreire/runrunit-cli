import contextlib
from datetime import date
import importlib.util
import io
import os
import re
import unittest
from unittest.mock import patch
import rr_cli as cli
import rr_format as fmt

HAS_RICH = importlib.util.find_spec('rich') is not None
REF = date(2026, 11, 16)
TASKS = [
    {'id': 1, 'title': 'Hoje', 'project_name': 'P1', 'board_stage_name': 'A fazer',
     'desired_date': '2026-11-16T18:00:00-03:00', 'assignments': []},
    {'id': 2, 'title': '[bold red]x[/] [link=http://e.test]y[/]', 'project_name': 'P2',
     'board_stage_name': 'Feito', 'desired_date': '2026-11-13', 'is_urgent': True, 'assignments': []},
]


def render(result, command, mode, **kwargs):
    out = io.StringIO()
    env = {'RR_SAIDA': mode, 'COLUMNS': '120', 'NO_COLOR': '1'}
    with patch.dict(os.environ, env):
        fmt.render(result, command, out, ref=REF, **kwargs)
    return out.getvalue()


class PlainOutputTests(unittest.TestCase):
    def test_task_list_has_header_and_aligned_columns(self):
        text = render({'body': TASKS}, 'minhas', 'simples')
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith('ID'))
        self.assertIn('Prazo', lines[0])
        self.assertEqual(lines[1].index('Hoje'), lines[0].index('Título'))
        self.assertIn('16/11/2026 (hoje)', text)
        self.assertIn('13/11/2026 (há 3 dias)', text)
        self.assertIn('(urgente)', text)
        self.assertIn('2 tarefas', text)

    def test_terminal_table_fits_width_and_pipe_keeps_full_values(self):
        long = dict(TASKS[0], title='Título muito longo ' * 10, project_name='Projeto comprido ' * 4)

        class Tty(io.StringIO):
            def isatty(self): return True

        tty = Tty()
        with patch.dict(os.environ, {'RR_SAIDA': 'simples'}), \
                patch.object(fmt.shutil, 'get_terminal_size', return_value=os.terminal_size((80, 24))):
            fmt.render({'body': [long]}, 'minhas', tty, ref=REF)
        self.assertTrue(all(fmt.display_width(line) < 80 for line in tty.getvalue().splitlines()))
        self.assertIn('…', tty.getvalue())
        self.assertIn('16/11/2026 (hoje)', tty.getvalue())
        piped = render({'body': [long]}, 'minhas', 'simples')
        self.assertIn(long['title'].strip(), piped)

    def test_non_terminal_output_has_no_escape_sequences(self):
        out = io.StringIO()
        with patch.dict(os.environ, {'RR_SAIDA': ''}):
            fmt.render({'body': TASKS}, 'minhas', out, ref=REF)
        self.assertNotIn('\x1b', out.getvalue())
        self.assertIn('ID', out.getvalue())

    def test_stages_render_as_resources_not_tasks(self):
        text = render({'body': [{'id': 7, 'name': 'Backlog', 'board_id': 3}]}, 'etapas', 'simples')
        self.assertIn('Nome', text)
        self.assertIn('Backlog', text)
        self.assertNotIn('sem título', text)
        self.assertNotIn('Prazo', text)

    def test_task_card_uses_words_not_python_values(self):
        task = dict(TASKS[0], is_urgent=False, is_closed=False, tags_data=[{'name': 'a'}, {'name': 'b'}],
                    assignments=[{'assignee_id': 'ana', 'assignee_name': 'Ana', 'is_working_on': True}])
        text = render({'body': task, 'description': '<p>Um</p><ul><li>dois</li><li>três</li></ul>'}, 'ver', 'simples')
        for expected in ('Urgente: ', 'não', 'a, b', 'Ana (trabalhando)', '• dois\n• três',
                         'https://runrun.it/pt-BR/tasks/1'):
            self.assertIn(expected, text)
        for raw in ('False', 'None', "[{'name'"):
            self.assertNotIn(raw, text)

    def test_summary_is_a_table(self):
        body = {'total': 3, 'por': 'prazo', 'grupos': {'Atrasadas': 1, 'Futuras': 2}}
        text = render({'body': body}, 'resumo', 'simples')
        self.assertIn('Futuras    2', text)
        self.assertIn('3 tarefas abertas', text)
        self.assertNotIn('{', text)

    def test_dry_run_does_not_repeat_plan_on_stdout(self):
        text = render({'status': 200, 'preview': True, 'body': {'method': 'PUT'}}, 'prazo', 'simples')
        self.assertEqual(text.strip(), 'Prévia; nenhuma alteração executada.')

    def test_output_wrapper_keeps_json_mode(self):
        args = type('Args', (), {'json': True, 'command': 'minhas'})()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.output({'status': 200, 'body': TASKS}, args)
        self.assertTrue(out.getvalue().lstrip().startswith('{'))


@unittest.skipUnless(HAS_RICH, 'rich não instalado')
class RichOutputTests(unittest.TestCase):
    def test_api_text_is_never_read_as_markup(self):
        text = render({'body': TASKS}, 'minhas', 'rica')
        self.assertIn('[bold red]x[/]', text)
        self.assertIn('[link=http://e.test]y[/]', text)

    def test_rich_task_card_and_plan_keep_literal_payload(self):
        out = io.StringIO()
        with patch.dict(os.environ, {'RR_SAIDA': 'rica', 'COLUMNS': '120', 'NO_COLOR': '1'}):
            fmt.render_task(TASKS[1], out, ref=REF)
            fmt.render_plan('comentar', {'data': {'text': '<b>[red]oi[/]</b>\x1b'}}, out)
        text = out.getvalue()
        self.assertIn('#2 · [bold red]x[/]', text)
        self.assertIn('<b>[red]oi[/]</b>\\u001b', text)
        # Rich mantém negrito com NO_COLOR; fora desses estilos não pode sobrar ESC do payload.
        self.assertNotIn('\x1b', re.sub(r'\x1b\[[0-9;]*m', '', text))


if __name__ == '__main__':
    unittest.main()
