"""Saída humana da CLI: tabelas e painéis com Rich no terminal, texto alinhado fora dele.

Todo dado vindo da API entra como texto literal (``rich.text.Text``), nunca como
markup, e passa antes pela limpeza de HTML e de caracteres de controle.
"""
from datetime import date, datetime
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Sao_Paulo')
TASK_LISTS = {'minhas', 'buscar', 'hoje', 'atrasadas', 'trabalhando', 'subtarefas'}
RESOURCE_TITLES = {'quadros': 'Quadros', 'projetos': 'Projetos', 'usuarios': 'Usuários',
                   'tipos': 'Tipos de tarefa', 'equipes': 'Equipes', 'etapas': 'Etapas'}
SUMMARY_TITLES = {'projeto': 'Projeto', 'prazo': 'Prazo', 'urgencia': 'Urgência'}


# ---------------------------------------------------------------- limpeza de texto

def clean(value):
    """Remove tags HTML, resolve entidades e descarta caracteres de controle."""
    text = html.unescape(re.sub(r'<[^>]*>', ' ', str(value if value is not None else '')))
    return ''.join(c for c in text if c == '\n' or not unicodedata.category(c).startswith('C'))


def html_to_text(value):
    """Como clean(), mas preserva quebras de parágrafo, de linha e itens de lista."""
    text = str(value if value is not None else '')
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)<li[^>]*>', '\n• ', text)
    text = re.sub(r'(?i)<h[1-6][^>]*>', '\n\n', text)
    text = re.sub(r'(?i)</li\s*>', '', text)
    text = re.sub(r'(?i)</(p|div|h[1-6]|tr|ul|ol)>', '\n', text)
    text = '\n'.join(' '.join(line.split()) for line in clean(text).split('\n'))
    text = re.sub(r'\n{3,}', '\n\n', text)
    return re.sub(r'\n\n(?=• )', '\n', text).strip()


def one_line(value):
    return ' '.join(clean(value).split())


def literal(value):
    """Preserva o texto autorizado; só neutraliza controles de terminal."""
    escaped = []
    for char in str(value if value is not None else ''):
        if char == '\n':
            escaped.append(char)
        elif unicodedata.category(char).startswith('C'):
            code = ord(char)
            escaped.append(f'\\x{code:02x}' if code < 0x100 else
                           f'\\u{code:04x}' if code < 0x10000 else f'\\U{code:08x}')
        else:
            escaped.append(char)
    return ''.join(escaped)


# ---------------------------------------------------------------- valores

def today():
    return datetime.now(TZ).date()


def parse_moment(value):
    """Devolve (date, datetime|None) no fuso de São Paulo, ou (None, None)."""
    if not value or not isinstance(value, str):
        return None, None
    try:
        if len(value) == 10:
            return date.fromisoformat(value), None
        moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
        moment = moment.replace(tzinfo=TZ) if moment.tzinfo is None else moment.astimezone(TZ)
        return moment.date(), moment
    except ValueError:
        return None, None


def due(value, ref=None):
    """Prazo como (texto, estilo): '20/11/2026 (hoje)', vermelho quando vencido."""
    if not value:
        return '-', 'dim'
    day, _ = parse_moment(value)
    if day is None:
        return one_line(value), None
    delta = (day - (ref or today())).days
    label = day.strftime('%d/%m/%Y')
    if delta < -1: return f'{label} (há {-delta} dias)', 'bold red'
    if delta == -1: return f'{label} (ontem)', 'bold red'
    if delta == 0: return f'{label} (hoje)', 'bold yellow'
    if delta == 1: return f'{label} (amanhã)', 'yellow'
    if delta <= 7: return f'{label} (em {delta} dias)', None
    return label, None


def moment(value):
    day, stamp = parse_moment(value)
    if stamp is not None: return stamp.strftime('%d/%m/%Y %H:%M')
    if day is not None: return day.strftime('%d/%m/%Y')
    return one_line(value) if value else None


def yes_no(value):
    return '-' if value is None else 'sim' if value else 'não'


def seconds(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return None
    minutes = int(value) // 60
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h{minutes:02d}m' if hours else f'{minutes}m'


def file_size(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return one_line(value) if value is not None else '-'
    size = float(value)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            text = f'{size:.0f}' if unit == 'B' else f'{size:.1f}'.replace('.', ',')
            return f'{text} {unit}'
        size /= 1024


def tags(value):
    names = [one_line(t.get('name')) if isinstance(t, dict) else one_line(t) for t in value or []]
    return ', '.join(n for n in names if n) or '-'


def person(item, name_key, id_key):
    return one_line(item.get(name_key) or item.get(id_key) or '-')


def compact(value):
    if isinstance(value, bool) or value is None: return yes_no(value)
    if isinstance(value, (dict, list)): return one_line(json.dumps(value, ensure_ascii=False))
    return one_line(value)


def is_task(item):
    return isinstance(item, dict) and ('assignments' in item or 'board_stage_name' in item)


# ---------------------------------------------------------------- destinos de saída
#
# Um destino recebe blocos já prontos (tabela, ficha, texto, aviso). Cada célula é
# um texto ou um par (texto, estilo); o estilo vem sempre deste módulo, nunca da API.

def cell(value):
    return value if isinstance(value, tuple) else (value, None)


def display_width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF' else 1
               for c in text)


def truncate(text, width):
    if display_width(text) <= width: return text
    out = ''
    for char in text:
        if display_width(out + char) > width - 1: break
        out += char
    return out + '…'


class PlainOut:
    """Texto alinhado, sem cores. Usado fora do terminal e quando o Rich falta."""
    rich = False

    def __init__(self, stream):
        self.stream = stream

    def _print(self, text=''):
        print(text, file=self.stream)

    def _terminal_width(self):
        try:
            return shutil.get_terminal_size().columns if self.stream.isatty() else None
        except (AttributeError, ValueError, OSError):
            return None

    def table(self, title, columns, rows, caption=None):
        if title: self._print(title)
        grid = [[h for h, _ in columns]] + [[' '.join(cell(c)[0].split()) for c in row] for row in rows]
        widths = [max(display_width(r[i]) for r in grid) for i in range(len(columns))]
        limit = self._terminal_width()
        if limit:
            # No terminal, encolhe as colunas largas até caber; em pipe os valores ficam inteiros.
            grow = [i for i, (_, opts) in enumerate(columns) if opts.get('grow')]
            excess = sum(widths) + 2 * (len(widths) - 1) - (limit - 1)
            while excess > 0:
                shrinkable = [k for k in grow if widths[k] > 12]
                if not shrinkable: break
                i = max(shrinkable, key=lambda k: widths[k] - columns[k][1].get('keep', 0))
                widths[i] -= 1; excess -= 1
            grid = [[truncate(v, widths[i]) for i, v in enumerate(row)] for row in grid]
        for row in grid:
            parts = [v + ' ' * (widths[i] - display_width(v)) for i, v in enumerate(row)]
            self._print('  '.join(parts).rstrip())
        if caption: self._print(caption)

    def fields(self, title, pairs, footer=None):
        if title: self._print(title)
        width = max((display_width(k) for k, _ in pairs), default=0)
        for key, value in pairs:
            self._print(f'{key}:{" " * (width - display_width(key))} {cell(value)[0]}')
        if footer: self._print(footer)

    def text(self, title, body):
        self._print()
        if title: self._print(f'{title}:')
        self._print(body)

    def note(self, message, style=None, symbol=None):
        self._print(message)


class RichOut:
    """Tabelas e painéis do Rich; respeita NO_COLOR e a largura do terminal."""
    rich = True

    def __init__(self, console):
        from rich import box
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        self.console, self.box, self.Panel, self.Table, self.Text = console, box, Panel, Table, Text

    def _t(self, value):
        text, style = cell(value)
        return self.Text(text, style=style or '')

    def table(self, title, columns, rows, caption=None):
        table = self.Table(box=self.box.SIMPLE_HEAD, header_style='bold', title_justify='left',
                           title=self.Text(title, style='bold') if title else None,
                           caption=self.Text(caption, style='dim') if caption else None,
                           caption_justify='left', pad_edge=False)
        for header, opts in columns:
            grow = opts.get('grow')
            table.add_column(header, justify=opts.get('justify', 'left'), no_wrap=not grow,
                             overflow='fold' if grow else 'ellipsis', ratio=1 if grow else None,
                             style=opts.get('style'))
        for row in rows:
            table.add_row(*(self._t(c) for c in row))
        self.console.print(table)

    def fields(self, title, pairs, footer=None):
        grid = self.Table.grid(padding=(0, 2))
        grid.add_column(style='bold', no_wrap=True)
        grid.add_column(overflow='fold')
        for key, value in pairs:
            grid.add_row(self.Text(key), self._t(value))
        if footer:
            grid.add_row(self.Text(''), self.Text(footer, style='cyan'))
        self.console.print(self.Panel(grid, title=self.Text(title, style='bold') if title else None,
                                      title_align='left', box=self.box.ROUNDED, expand=False))

    def text(self, title, body):
        self.console.print(self.Panel(self.Text(body), title=self.Text(title, style='bold') if title else None,
                                      title_align='left', box=self.box.ROUNDED, expand=False))

    def note(self, message, style=None, symbol=None):
        self.console.print(self.Text(f'{symbol} {message}' if symbol else message, style=style or ''))


def wants_rich(stream):
    mode = os.environ.get('RR_SAIDA', '').strip().lower()
    if mode == 'simples': return False
    if mode != 'rica':
        try:
            if not stream.isatty() or os.environ.get('TERM') == 'dumb': return False
        except (AttributeError, ValueError):
            return False
    try:
        import rich  # noqa: F401
    except ImportError:
        return False
    return True


def destination(stream=None):
    stream = stream or sys.stdout
    if not wants_rich(stream):
        return PlainOut(stream)
    from rich.console import Console
    forced = os.environ.get('RR_SAIDA', '').strip().lower() == 'rica'
    return RichOut(Console(file=stream, markup=False, emoji=False, highlight=False,
                           force_terminal=True if forced else None))


# ---------------------------------------------------------------- tarefas

def task_title(t, out):
    title = one_line(t.get('title')) or '(sem título)'
    marks = []
    if t.get('is_urgent'): marks.append('⚑' if out.rich else '(urgente)')
    if any(a.get('is_working_on') for a in t.get('assignments') or [] if isinstance(a, dict)) or t.get('is_working_on') is True:
        marks.append('▶' if out.rich else '(trabalhando)')
    return ' '.join(marks + [title]) if out.rich else ' '.join([title] + marks)


def task_rows(tasks, out, ref=None):
    rows = []
    for t in tasks:
        urgent = 'bold' if t.get('is_urgent') else None
        rows.append([(one_line(t.get('id')), 'cyan'), (task_title(t, out), urgent),
                     one_line(t.get('project_name') or t.get('client_name') or '-'),
                     one_line(t.get('board_stage_name') or '-'), due(t.get('desired_date'), ref)])
    return rows


TASK_COLUMNS = [('ID', {'justify': 'right'}), ('Título', {'grow': True, 'keep': 25}), ('Projeto', {'grow': True}),
                ('Etapa', {}), ('Prazo', {})]


def task_table(out, title, tasks, ref=None):
    count = len(tasks)
    caption = f'{count} tarefa' + ('' if count == 1 else 's')
    if not tasks:
        if title: out.note(title, 'bold')
        out.note('Nenhuma tarefa.', 'dim')
        return
    out.table(title, TASK_COLUMNS, task_rows(tasks, out, ref), caption)


def task_card(out, t, ref=None):
    pairs = [('Cliente', one_line(t.get('client_name') or '-')),
             ('Projeto', one_line(t.get('project_name') or '-')),
             ('Tipo', one_line(t.get('type_name') or t.get('type_id') or '-')),
             ('Quadro', one_line(t.get('board_name') or t.get('board_id') or '-')),
             ('Etapa', one_line(t.get('board_stage_name') or '-')),
             ('Prazo', due(t.get('desired_date'), ref)),
             ('Urgente', ('sim', 'bold red') if t.get('is_urgent') else yes_no(t.get('is_urgent'))),
             ('Fechada', yes_no(t.get('is_closed'))),
             ('Tags', tags(t.get('tags_data')))]
    people = []
    for a in t.get('assignments') or []:
        if not isinstance(a, dict): continue
        state = 'trabalhando' if a.get('is_working_on') else 'concluído' if a.get('is_closed') else 'aberto'
        people.append(f"{person(a, 'assignee_name', 'assignee_id')} ({state})")
    pairs.append(('Responsáveis', ', '.join(people) or '-'))
    worked, estimate = seconds(t.get('time_worked')), seconds(t.get('current_estimate_seconds'))
    if worked or estimate:
        pairs.append(('Tempo', f"{worked or '0m'} trabalhado" + (f' de {estimate} estimado' if estimate else '')))
    title = f"#{one_line(t.get('id'))} · {one_line(t.get('title')) or '(sem título)'}"
    out.fields(title, pairs, f"https://runrun.it/pt-BR/tasks/{one_line(t.get('id'))}")


# ---------------------------------------------------------------- outros recursos

def comments(out, items):
    if not items:
        out.note('Nenhum comentário.', 'dim'); return
    for c in items:
        author = person(c, 'user_name', 'user_id')
        header = ' · '.join(p for p in (author, moment(c.get('created_at'))) if p)
        out.text(header, html_to_text(c.get('text')) or '(vazio)')
    out.note(f'{len(items)} comentário' + ('' if len(items) == 1 else 's'), 'dim')


def documents(out, items):
    rows = [[(one_line(d.get('id')), 'cyan'), one_line(d.get('file_name') or d.get('name') or '-'),
             file_size(d.get('file_size')), moment(d.get('created_at')) or '-'] for d in items]
    out.table(None, [('ID', {'justify': 'right'}), ('Arquivo', {'grow': True}),
                     ('Tamanho', {'justify': 'right'}), ('Enviado em', {})], rows,
              f'{len(items)} arquivo' + ('' if len(items) == 1 else 's'))


def checklist_items(out, items, container=None):
    title = one_line(container.get('title')) if isinstance(container, dict) else None
    done = sum(1 for i in items if i.get('checked'))
    rows = [[('[x]', 'green') if i.get('checked') else ('[ ]', 'dim'),
             (one_line(i.get('description')), 'dim' if i.get('checked') else None),
             (one_line(i.get('id')), 'cyan')] for i in items]
    out.table(f'Checklist: {title}' if title else 'Checklist',
              [('', {}), ('Item', {'grow': True}), ('ID', {'justify': 'right'})], rows,
              f'{done} de {len(items)} concluído' + ('' if done == 1 else 's'))


def tag_list(out, items):
    rows = [[one_line(t.get('name') if isinstance(t, dict) else t),
             one_line(t.get('color') or '-') if isinstance(t, dict) else '-'] for t in items]
    out.table(None, [('Tag', {'grow': True}), ('Cor', {})], rows, f'{len(items)} tag(s)')


def resource_list(out, command, items):
    extras = [(key, label) for key, label in (('client_name', 'Cliente'), ('board_name', 'Quadro'),
                                              ('email', 'E-mail'), ('position', 'Posição'))
              if any(isinstance(i, dict) and i.get(key) for i in items)]
    columns = [('ID', {'justify': 'right'}), ('Nome', {'grow': True})] + [(label, {}) for _, label in extras]
    rows = [[(one_line(i.get('id')), 'cyan'), one_line(i.get('name') or i.get('title') or '-')] +
            [one_line(i.get(key) or '-') for key, _ in extras] for i in items]
    out.table(RESOURCE_TITLES.get(command), columns, rows, f'{len(items)} resultado(s)')


def generic_list(out, items):
    if not all(isinstance(i, dict) for i in items):
        for i in items: out.note(one_line(i))
        out.note(f'{len(items)} resultado(s).', 'dim'); return
    preferred = ('id', 'name', 'title', 'description', 'checked', 'user_name', 'text', 'file_name', 'file_size')
    keys = [k for k in preferred if any(i.get(k) is not None for i in items)] or ['id']
    rows = [[compact(i.get(k)) for k in keys] for i in items]
    out.table(None, [(k, {'grow': k in ('title', 'description', 'text', 'name')}) for k in keys], rows,
              f'{len(items)} resultado(s).')


def summary(out, body):
    groups = body.get('grupos') or {}
    label = SUMMARY_TITLES.get(body.get('por'), 'Grupo')
    by_project = body.get('por') == 'projeto'
    ordered = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))
    if by_project:
        columns = [('ID', {'justify': 'right'}), (label, {'grow': True}), ('Tarefas', {'justify': 'right'})]
        rows = [[(k.partition(' | ')[0], 'cyan'), k.partition(' | ')[2] or k, str(v)] for k, v in ordered]
    else:
        columns = [(label, {'grow': True}), ('Tarefas', {'justify': 'right'})]
        styles = {'Atrasadas': 'bold red', 'Hoje': 'bold yellow', 'Urgentes': 'bold red'}
        rows = [[(k, styles.get(k)), (str(v), styles.get(k))] for k, v in ordered]
    out.table(f'Resumo por {label.lower()}', columns, rows, f"{body.get('total', 0)} tarefas abertas")


def comment_card(out, c):
    parts = (f"Comentário #{one_line(c.get('id'))}", person(c, 'user_name', 'user_id'), moment(c.get('created_at')))
    header = ' · '.join(p for p in parts if p and p != '-')
    out.text(header, html_to_text(c.get('text')) or '(vazio)')


def record(out, title, body):
    pairs = [(str(k), compact(v)) for k, v in body.items()]
    out.fields(title, pairs or [('', '-')])


# ---------------------------------------------------------------- ponto de entrada

def render(result, command, stream=None, ref=None):
    """Mostra o resultado de um comando na saída humana."""
    out = destination(stream)
    body = result.get('body')
    if result.get('preview'):
        out.note('Prévia; nenhuma alteração executada.', 'bold yellow', '!' if out.rich else None)
    elif isinstance(body, list):
        if command in TASK_LISTS: task_table(out, None, body, ref)
        elif command == 'comentarios': comments(out, body)
        elif command == 'arquivos': documents(out, body)
        elif command == 'checklist': checklist_items(out, body, result.get('checklist'))
        elif command == 'tags': tag_list(out, body)
        elif command in RESOURCE_TITLES: resource_list(out, command, body)
        elif body and all(is_task(i) for i in body): task_table(out, None, body, ref)
        else: generic_list(out, body)
    elif body is None and command == 'checklist':
        out.note('Esta tarefa não possui checklist.', 'dim')
    elif isinstance(body, dict) and command == 'resumo' and 'grupos' in body:
        summary(out, body)
    elif isinstance(body, dict) and command == 'dependencias':
        task_table(out, 'Pré-requisitos', body.get('pre_requisitos') or [], ref)
        task_table(out, 'Dependentes', body.get('dependentes') or [], ref)
    elif isinstance(body, dict) and command == 'abrir' and 'url' in body:
        out.note('Aberta no navegador: ' + one_line(body['url']), 'cyan')
    elif is_task(body) or (isinstance(body, dict) and 'board_id' in body and 'title' in body):
        task_card(out, body, ref)
    elif isinstance(body, dict) and 'text' in body and 'task_id' in body:
        comment_card(out, body)
    elif isinstance(body, dict):
        record(out, None, body)
    else:
        out.note(clean(body))
    if result.get('description') is not None:
        out.text('Descrição', html_to_text(result['description']) or '(sem descrição)')
    if result.get('verification'):
        out.note('Verificação: ' + clean(result['verification']), 'green', '✓' if out.rich else None)
    if result.get('truncated'):
        destination(sys.stderr).note('Resultado parcial: limite de paginação atingido; aumente --max-pages/--max-items.',
                                     'yellow', '!')


def render_task(task, stream=None, ref=None):
    task_card(destination(stream), task, ref)


def render_plan(command, plan, stream=None):
    """Prévia de uma escrita. O payload aparece literal: é o que será enviado."""
    out = destination(stream)
    out.note('Operação: ' + command, 'bold')
    payload = literal(json.dumps(plan, ensure_ascii=False, indent=2))
    if out.rich: out.text('Prévia da operação', payload)
    else: out.note(payload)
