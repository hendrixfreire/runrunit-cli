#!/usr/bin/env python3
"""Interface em português para a integração existente do Runrun.it."""
import argparse
from collections import Counter
from datetime import date, datetime
import html
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
import webbrowser
from zoneinfo import ZoneInfo
import runrunit_api as api

TZ = ZoneInfo('America/Sao_Paulo')
LISTS = {'minhas', 'buscar', 'hoje', 'atrasadas', 'trabalhando', 'resumo'}
COLLECTIONS = {'comentarios': 'comments', 'subtarefas': 'subtasks', 'arquivos': 'documents'}
RESOURCES = {'quadros': '/boards', 'projetos': '/projects', 'usuarios': '/users',
             'tipos': '/task_types', 'equipes': '/teams'}
ACTIONS = {'iniciar': 'play', 'pausar': 'pause', 'entregar': 'deliver', 'reabrir': 'reopen'}


def plain(value):
    text = html.unescape(re.sub(r'<[^>]*>', ' ', str(value if value is not None else '')))
    return ''.join(c for c in text if c == '\n' or not unicodedata.category(c).startswith('C'))


def literal(value):
    """Preserve authorized payload text; only neutralize terminal controls."""
    text = str(value if value is not None else '')
    escaped = []
    for char in text:
        if char == '\n':
            escaped.append(char)
        elif unicodedata.category(char).startswith('C'):
            code = ord(char)
            escaped.append(f'\\x{code:02x}' if code < 0x100 else
                           f'\\u{code:04x}' if code < 0x10000 else f'\\U{code:08x}')
        else:
            escaped.append(char)
    return ''.join(escaped)


def show_task(t, stream=None):
    stream = stream or sys.stdout
    for label, key in [('Tarefa', 'id'), ('Título', 'title'), ('Cliente', 'client_name'),
                       ('Projeto', 'project_name'), ('Quadro', 'board_id'), ('Etapa', 'board_stage_name'),
                       ('Prazo', 'desired_date'), ('Urgente', 'is_urgent'), ('Fechada', 'is_closed'), ('Tags', 'tags_data')]:
        print(f'{label}: {plain(t.get(key))}', file=stream)
    for a in t.get('assignments') or []:
        print(f"Responsável: {plain(a.get('assignee_id'))} | fechado={a.get('is_closed')} | trabalhando={a.get('is_working_on')}", file=stream)
    print(f"https://runrun.it/pt-BR/tasks/{t.get('id')}", file=stream)


def output(result, args):
    if args.json:
        api.emit(result)
        return
    body = result['body']
    if result.get('preview'):
        print('Prévia; nenhuma alteração executada.')
    if isinstance(body, list):
        for item in body:
            if not isinstance(item, dict):
                print(plain(item)); continue
            keys = ('id', 'title', 'project_name', 'board_stage_name', 'desired_date') if 'assignments' in item or 'board_stage_name' in item else ('id', 'name', 'title', 'description', 'checked', 'user_name', 'text', 'file_name', 'file_size')
            print(' | '.join(plain(item.get(k)).replace('\n', ' ') for k in keys if item.get(k) is not None))
        print(f'{len(body)} resultado(s).')
    elif isinstance(body, dict) and ('assignments' in body or 'board_id' in body) and not result.get('preview'):
        show_task(body)
    elif body is None and args.command == 'checklist':
        print('Esta tarefa não possui checklist.')
    else:
        print(plain(json.dumps(body, ensure_ascii=False, indent=2)) if isinstance(body, dict) else plain(body))
    if result.get('description') is not None:
        print('\nDescrição:\n' + plain(result['description']))
    if result.get('verification'):
        print('Verificação: ' + plain(result['verification']))
    if result.get('truncated'):
        print('Resultado parcial: limite de paginação atingido; aumente --max-pages/--max-items.', file=sys.stderr)


def iso_date(value):
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): raise ValueError()
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError('Use uma data válida em YYYY-MM-DD.')


def duration(value):
    m = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', value)
    if not m or not any(m.groups()):
        raise argparse.ArgumentTypeError('Use duração como 1h30m, 1h30, 90m ou 5400s.')
    seconds = sum(int(n or 0) * unit for n, unit in zip(m.groups(), (3600, 60, 1)))
    if seconds <= 0: raise argparse.ArgumentTypeError('A duração deve ser positiva.')
    return seconds


def parse_duration(value):
    return duration(value + 'm' if re.fullmatch(r'\d+h\d+', value) else value)


def nonempty(value):
    if not value.strip(): raise argparse.ArgumentTypeError('O texto não pode ser vazio.')
    return value


def parser():
    p = argparse.ArgumentParser(prog='rr', description='Suas tarefas do Runrun.it. Comandos técnicos preservados: task, request, paginate.')
    sub = p.add_subparsers(dest='command', required=True)
    helps = {
        'minhas': 'Suas tarefas abertas', 'buscar': 'Buscar título nas suas tarefas abertas',
        'hoje': 'Suas tarefas com prazo hoje', 'atrasadas': 'Suas tarefas com prazo vencido',
        'trabalhando': 'Seus contadores ativos', 'resumo': 'Panorama das suas tarefas abertas',
        'ver': 'Tarefa e descrição', 'comentarios': 'Ler comentários', 'abrir': 'Abrir tarefa no navegador',
        'criar': 'Criar tarefa', 'entregar': 'Entregar tarefa', 'reabrir': 'Reabrir tarefa',
        'mover': 'Mover para etapa do mesmo quadro', 'prazo': 'Alterar ou limpar prazo',
        'editar': 'Editar título ou descrição', 'urgente': 'Marcar ou desmarcar urgência',
        'atribuir': 'Adicionar ou remover responsável', 'tags': 'Ler, adicionar ou remover tags',
        'checklist': 'Ler e gerenciar checklist e itens', 'horas': 'Apontar duração manualmente',
        'subtarefas': 'Listar subtarefas', 'dependencias': 'Ler pré-requisitos e dependentes',
        'arquivos': 'Listar anexos', 'anexar': 'Enviar arquivo', 'iniciar': 'Iniciar trabalho',
        'pausar': 'Pausar trabalho', 'comentar': 'Publicar comentário',
        'quadros': 'Listar quadros', 'etapas': 'Listar etapas de um quadro', 'projetos': 'Listar projetos',
        'usuarios': 'Listar usuários', 'tipos': 'Listar tipos', 'equipes': 'Listar equipes',
    }
    for name, help_text in helps.items():
        s = sub.add_parser(name, help=help_text, description=help_text)
        s.add_argument('--json', action='store_true')
        if name in LISTS | set(COLLECTIONS) | set(RESOURCES) | {'dependencias', 'checklist', 'etapas'}:
            s.add_argument('--max-pages', type=int, default=10)
            s.add_argument('--max-items', type=int, default=1000)
        if name in LISTS:
            s.add_argument('--usuario', help='Responsável; padrão: RUNRUNIT_USER_ID ou o dono do User-Token')
        if name == 'resumo':
            s.add_argument('--por', choices=['projeto', 'prazo', 'urgencia'], default='projeto')
        if name == 'buscar': s.add_argument('texto', type=nonempty)
        if name not in LISTS | set(RESOURCES) | {'criar', 'etapas'}:
            s.add_argument('id', type=api.safe_id)
        if name in {'iniciar', 'pausar', 'comentar', 'criar', 'entregar', 'reabrir', 'mover', 'prazo', 'editar', 'urgente', 'atribuir', 'tags', 'checklist', 'horas', 'anexar'}:
            s.add_argument('--confirmar', metavar='ID_OU_CRIAR')
            s.add_argument('--dry-run', action='store_true', help='Ler e mostrar prévia, sem alterar')
        if name in {'comentar', 'criar'}: s.add_argument('texto', type=nonempty)
        if name == 'criar':
            s.add_argument('--quadro', required=True, type=api.safe_id)
            s.add_argument('--tipo', required=True, type=api.safe_id)
            s.add_argument('--projeto', type=api.safe_id)
            s.add_argument('--etapa', type=api.safe_id)
            s.add_argument('--descricao')
        if name == 'etapas': s.add_argument('--quadro', required=True, type=api.safe_id)
        if name == 'mover': s.add_argument('--etapa', required=True, type=api.safe_id)
        if name == 'prazo':
            s.add_argument('data', nargs='?', type=iso_date)
            s.add_argument('--limpar', action='store_true')
        if name == 'editar':
            s.add_argument('--titulo', type=nonempty)
            g = s.add_mutually_exclusive_group()
            g.add_argument('--descricao'); g.add_argument('--descricao-arquivo', type=Path)
        if name == 'urgente': s.add_argument('--remover', action='store_true')
        if name == 'atribuir':
            s.add_argument('--usuario', required=True, type=api.safe_id)
            s.add_argument('--equipe', type=api.safe_id)
            s.add_argument('--remover', action='store_true')
        if name == 'tags':
            s.add_argument('--adicionar', action='append', default=[], type=nonempty)
            s.add_argument('--remover', action='append', default=[], type=nonempty)
        if name == 'checklist':
            g = s.add_mutually_exclusive_group()
            for flag in ('criar', 'titulo', 'adicionar', 'concluir', 'reabrir', 'excluir-item', 'editar-item'):
                g.add_argument('--' + flag, type=nonempty)
            s.add_argument('--texto', type=nonempty, help='Novo texto para --editar-item')
        if name == 'horas':
            s.add_argument('--duracao', required=True, type=parse_duration)
            s.add_argument('--data', required=True, type=iso_date)
            s.add_argument('--motivo', default='')
            s.add_argument('--equipe', type=api.safe_id)
        if name == 'anexar': s.add_argument('arquivo', type=Path)
    return p


def pages(path, args):
    return api.paginate(path, api.positive(args.max_pages, 'max-pages'), api.positive(args.max_items, 'max-items'))


def get(path):
    return api.call('GET', path)['body']


def token_owner():
    """Resolve the user that owns the configured User-Token; never guesses."""
    try:
        body = get('/users?me_first=true&limit=1')
    except SystemExit:
        raise SystemExit('Não foi possível identificar o dono do User-Token. '
                         'Configure RUNRUNIT_USER_ID ou use --usuario ID.') from None
    if not isinstance(body, list) or not body or not isinstance(body[0], dict) or not body[0].get('id'):
        raise SystemExit('A API não retornou o usuário do token. '
                         'Configure RUNRUNIT_USER_ID ou use --usuario ID.')
    return api.safe_id(str(body[0]['id']))


def resolve_user(usuario=None):
    """Precedence: --usuario, RUNRUNIT_USER_ID, token owner (network only in the last case)."""
    value = usuario if usuario is not None else os.environ.get('RUNRUNIT_USER_ID')
    if value is not None and str(value).strip():
        try:
            return api.safe_id(str(value).strip())
        except SystemExit:
            raise SystemExit(f'Identificador de usuário inválido: {value!r}. '
                             'Corrija --usuario ou RUNRUNIT_USER_ID.') from None
    return token_owner()


def confirm(args, task, plan):
    if task: show_task(task, sys.stderr)
    print('Operação: ' + args.command, file=sys.stderr)
    print(literal(json.dumps(plan, ensure_ascii=False, indent=2)), file=sys.stderr)
    if args.dry_run: return False
    expected = getattr(args, 'id', 'CRIAR')
    if args.confirmar is not None:
        if args.confirmar != expected: raise SystemExit(f'--confirmar deve ser {expected}.')
        return True
    if not sys.stdin.isatty():
        raise SystemExit(f'Nenhuma alteração executada. Revise a prévia e use --confirmar {expected}.')
    if input(f'Digite {expected} para confirmar: ').strip() != expected:
        raise SystemExit('Operação cancelada.')
    return True


def preview(plan):
    return {'status': 200, 'preview': True, 'body': plan}


def checked(result, ok):
    if not ok: raise SystemExit('A escrita pode ter sido executada, mas a leitura divergiu. Reconcilie antes de repetir.')
    result['verification'] = 'confirmado por leitura após a escrita'
    return result


def due_day(t):
    v = t.get('desired_date')
    if not v: return None
    try:
        if len(v) == 10: return date.fromisoformat(v)
        d = datetime.fromisoformat(v.replace('Z', '+00:00'))
        return d.replace(tzinfo=TZ).date() if d.tzinfo is None else d.astimezone(TZ).date()
    except (ValueError, TypeError):
        raise SystemExit(f"Prazo inválido na tarefa {t.get('id')}: {v!r}")


def list_tasks(args):
    usuario = resolve_user(args.usuario)
    args.usuario = usuario
    path = api.add_query('/tasks', [('assignee_id', usuario), ('is_closed', 'false'), ('limit', '100')])
    result = pages(path, args)
    tasks = [t for t in result['body'] if not t.get('is_closed') and any(
        a.get('assignee_id') == usuario and a.get('is_closed') is False for a in t.get('assignments') or [])]
    today = datetime.now(TZ).date()
    if args.command == 'buscar': tasks = [t for t in tasks if args.texto.casefold() in str(t.get('title', '')).casefold()]
    if args.command == 'hoje': tasks = [t for t in tasks if due_day(t) == today]
    if args.command == 'atrasadas': tasks = [t for t in tasks if due_day(t) and due_day(t) < today]
    if args.command == 'trabalhando': tasks = [t for t in tasks if any(a.get('assignee_id') == usuario and a.get('is_working_on') is True and not a.get('is_closed') for a in t.get('assignments') or [])]
    result['items_returned'] = len(tasks)
    result['body'] = tasks
    result['scope'] = 'Tarefas abertas atribuídas a ' + usuario
    if args.command == 'resumo':
        def group(t):
            if args.por == 'projeto': return f"{t.get('project_id') or '-'} | {t.get('project_name') or 'Sem projeto'}"
            if args.por == 'urgencia': return 'Urgentes' if t.get('is_urgent') else 'Normais'
            d = due_day(t)
            return 'Sem prazo' if d is None else 'Atrasadas' if d < today else 'Hoje' if d == today else 'Futuras'
        result['body'] = {'total': len(tasks), 'por': args.por, 'grupos': dict(sorted(Counter(group(t) for t in tasks).items()))}
    return result


def description(task_id):
    data = get(f'/tasks/{task_id}/description')
    return data.get('description', data) if isinstance(data, dict) else data


def mutate_task(args, task):
    tid = args.id; base = f'/tasks/{tid}'; cmd = args.command
    method, path, payload = 'POST', base, None
    expected = {}; verify_path = base
    if cmd in ACTIONS:
        path += '/' + ACTIONS[cmd]
        if cmd in ('entregar', 'reabrir'): expected['is_closed'] = cmd == 'entregar'
    elif cmd == 'mover':
        stage = get(f"/boards/{api.safe_id(str(task['board_id']))}/stages/{args.etapa}")
        if str(stage['id']) != args.etapa: raise SystemExit('Etapa divergente.')
        if stage.get('board_id') is not None and str(stage['board_id']) != str(task['board_id']): raise SystemExit('Etapa pertence a outro quadro.')
        payload = {'board_stage_id': args.etapa}; path += '/move'; expected = {'board_stage_id': args.etapa}
    elif cmd == 'prazo':
        if bool(args.data) == bool(args.limpar): raise SystemExit('Informe a data ou --limpar.')
        expected = {'desired_date': None if args.limpar else args.data}
        method, payload = 'PUT', {'task': expected}
    elif cmd == 'urgente':
        expected = {'is_urgent': not args.remover}
        path += '/unmark_as_urgent' if args.remover else '/mark_as_urgent'
    elif cmd == 'comentar':
        path = '/comments'; payload = {'task_id': tid, 'text': args.texto}
    elif cmd == 'atribuir':
        get('/users/' + args.usuario)
        assignments = [a for a in task.get('assignments') or [] if a.get('assignee_id') == args.usuario]
        if args.remover:
            if len(assignments) != 1: raise SystemExit('Responsável ausente ou assignment ambíguo.')
            method, path = 'DELETE', base + '/assignments/' + api.safe_id(str(assignments[0]['id']))
        else:
            if assignments: raise SystemExit('Usuário já possui assignment; nenhuma alteração executada.')
            team = args.equipe or task.get('team_id')
            if not team: raise SystemExit('Informe --equipe ID.')
            get('/teams/' + api.safe_id(str(team)))
            path += '/create_assignments'; payload = {'assignments': [{'assignee_id': args.usuario, 'team_id': team}]}
    elif cmd == 'tags':
        current = task.get('tags_data') or []
        names = {t['name'] for t in current}
        if set(args.adicionar) & set(args.remover): raise SystemExit('A mesma tag não pode ser adicionada e removida.')
        if set(args.remover) - names: raise SystemExit('Tag a remover não está na tarefa.')
        tags = [dict(t) for t in current if t['name'] not in args.remover]
        for name in args.adicionar:
            if name not in names:
                matches = api.paginate(api.add_query('/tags', [('search_term', name), ('limit', '100')]), 10, 1000)
                if matches['truncated']: raise SystemExit('Busca de tags parcial; resolva antes de alterar.')
                exact = [t for t in matches['body'] if t.get('name') == name]
                if len(exact) > 1: raise SystemExit('Nome de tag ambíguo.')
                tag = {'name': name}
                if exact and exact[0].get('color'): tag['color'] = exact[0]['color']
                tags.append(tag); names.add(name)
        expected = {'tags_data': tags}; method, payload = 'PUT', {'task': expected}
    elif cmd == 'horas':
        stage = task.get('board_stage_id')
        if stage is None: raise SystemExit('Tarefa sem etapa; não é possível atribuir horas à etapa.')
        record = {'task_id': tid, 'seconds': args.duracao, 'date_to_apply': args.data,
                  'board_stage_id': stage, 'reason_comment': args.motivo}
        if args.equipe:
            get('/teams/' + args.equipe); record['team_id'] = args.equipe
        path, payload = '/manual_work_periods', {'manual_work_period': record}
    plan = {'method': method, 'path': path, 'data': payload}
    if not confirm(args, task, plan): return preview(plan)
    written = api.call(method, path, payload)
    if cmd == 'comentar':
        result = api.call('GET', '/comments/' + api.safe_id(str(written['body']['id'])))
        return checked(result, str(result['body'].get('task_id')) == tid and result['body'].get('text') == args.texto)
    if cmd == 'horas':
        result = api.call('GET', '/manual_work_periods/' + api.safe_id(str(written['body']['id'])))
        b = result['body']
        return checked(result, all(str(b.get(k)) == str(v) for k, v in record.items()))
    result = api.call('GET', verify_path); b = result['body']
    if cmd in ('iniciar', 'pausar'):
        me = token_owner()
        mine = [a for a in b.get('assignments') or [] if a.get('assignee_id') == me]
        return checked(result, bool(mine) and all(a.get('is_working_on') is (cmd == 'iniciar') for a in mine))
    if cmd == 'atribuir': return checked(result, any(a.get('assignee_id') == args.usuario for a in b.get('assignments') or []) is (not args.remover))
    if cmd == 'tags': return checked(result, {t['name'] for t in b.get('tags_data') or []} == {t['name'] for t in expected['tags_data']})
    if cmd == 'prazo': return checked(result, (due_day(b).isoformat() if due_day(b) else None) == expected['desired_date'])
    return checked(result, all(str(b.get(k)) == str(v) for k, v in expected.items()))


def edit(args, task):
    desc = args.descricao_arquivo.read_text(encoding='utf-8') if args.descricao_arquivo else args.descricao
    if args.titulo is None and desc is None:
        raise SystemExit('Informe --titulo, --descricao ou --descricao-arquivo.')
    base = f'/tasks/{args.id}'
    plan = []
    old_description = None
    if args.titulo is not None:
        plan.append({'method': 'PUT', 'path': base, 'data': {'task': {'title': args.titulo}}})
    if desc is not None:
        old_description = description(args.id)
        plan.append({'method': 'PUT', 'path': base + '/description', 'data': {'task_description': {'description': desc}}})
    preview_data = {'requests': plan, 'descricao_atual': old_description}
    if not confirm(args, task, preview_data): return preview(preview_data)
    completed = []
    for request in plan:
        try:
            api.call(request['method'], request['path'], request['data'])
            completed.append(request['path'])
        except (SystemExit, OSError):
            print('Operações anteriores já enviadas: ' + ', '.join(completed) + '. Reconcilie antes de repetir.', file=sys.stderr)
            raise
    result = api.call('GET', base)
    ok = args.titulo is None or result['body'].get('title') == args.titulo
    if desc is not None:
        result['description'] = description(args.id)
        ok = ok and result['description'] == desc
    return checked(result, ok)


def create(args):
    get('/boards/' + args.quadro); get('/task_types/' + args.tipo)
    if args.projeto: get('/projects/' + args.projeto)
    if args.etapa: get(f'/boards/{args.quadro}/stages/{args.etapa}')
    body = {'title': args.texto, 'board_id': args.quadro, 'type_id': args.tipo}
    for flag, key in [('projeto', 'project_id'), ('etapa', 'board_stage_id'), ('descricao', 'description')]:
        value = getattr(args, flag)
        if value is not None: body[key] = value
    plan = {'method': 'POST', 'path': '/tasks', 'data': {'task': body}}
    if not confirm(args, None, plan): return preview(plan)
    written = api.call('POST', '/tasks', plan['data'])
    task_id = api.safe_id(str(written['body']['id']))
    result = api.call('GET', '/tasks/' + task_id)
    expected = {k: v for k, v in body.items() if k != 'description'}
    ok = all(str(result['body'].get(k)) == str(v) for k, v in expected.items())
    if 'description' in body:
        try:
            result['description'] = description(task_id)
        except SystemExit:
            raise SystemExit(f'Tarefa {task_id} criada, mas a descrição não pôde ser confirmada. '
                             'Reconcilie antes de repetir.') from None
        ok = ok and result['description'] == body['description']
    return checked(result, ok)


def checklist(args, task):
    base = f'/tasks/{args.id}/checklist'
    cmd = next((k for k in ('criar', 'titulo', 'adicionar', 'concluir', 'reabrir', 'excluir_item', 'editar_item') if getattr(args, k)), None)
    if args.texto and cmd != 'editar_item': raise SystemExit('--texto exige --editar-item ID.')
    if cmd == 'criar':
        existing = api.call('GET', base, allow_not_found=True)['body']
        if existing: raise SystemExit('A tarefa já possui checklist; use --titulo ou --adicionar.')
        plan = {'method': 'POST', 'path': base, 'data': {'checklist': {'title': args.criar}}}
        if not confirm(args, task, plan): return preview(plan)
        api.call('POST', base, plan['data'])
        result = api.call('GET', base)
        return checked(result, result['body'].get('title') == args.criar and str(result['body'].get('task_id')) == args.id)
    container = api.call('GET', base, allow_not_found=True)['body']
    if not container:
        if cmd is not None: raise SystemExit('Crie primeiro o checklist com --criar TÍTULO.')
        return {'status': 200, 'body': None}
    if str(container.get('task_id')) != args.id: raise SystemExit('Checklist pertence a outra tarefa.')
    items_path = '/checklists/' + api.safe_id(str(container['id'])) + '/items'
    if cmd is None:
        result = pages(items_path + '?limit=100', args); result['checklist'] = container; return result
    method, path, data = 'PUT', base, None
    expected = {}
    if cmd == 'titulo': expected = {'title': args.titulo}; data = {'checklist': expected}
    elif cmd == 'adicionar': method, path = 'POST', items_path; expected = {'description': args.adicionar}; data = {'checklist_item': expected}
    else:
        item_id = api.safe_id(getattr(args, cmd)); path = items_path + '/' + item_id
        item = get(path)
        if str(item.get('checklist_id')) != str(container['id']): raise SystemExit('Item pertence a outro checklist.')
        if cmd == 'excluir_item': method = 'DELETE'
        else:
            if cmd == 'editar_item' and not args.texto: raise SystemExit('--editar-item exige --texto.')
            expected = {'description': args.texto} if cmd == 'editar_item' else {'checked': cmd == 'concluir'}
            data = {'checklist_item': expected}
    plan = {'method': method, 'path': path, 'data': data, 'checklist_atual': container}
    if cmd not in ('titulo', 'adicionar'): plan['item_atual'] = item
    if not confirm(args, task, plan): return preview(plan)
    written = api.call(method, path, data)
    if method == 'DELETE':
        result = pages(items_path + '?limit=100', args)
        return checked(result, not result['truncated'] and all(str(i['id']) != item_id for i in result['body']))
    if cmd == 'adicionar': path += '/' + api.safe_id(str(written['body']['id']))
    result = api.call('GET', path)
    return checked(result, all(result['body'].get(k) == v for k, v in expected.items()))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ('task', 'request', 'paginate'):
        api.main(); return
    args = parser().parse_args(argv); cmd = args.command
    if cmd in LISTS: result = list_tasks(args)
    elif cmd in RESOURCES: result = pages(RESOURCES[cmd] + '?limit=100', args)
    elif cmd == 'etapas': result = pages(f'/boards/{args.quadro}/stages?limit=100', args)
    elif cmd in COLLECTIONS: result = pages(f'/tasks/{args.id}/{COLLECTIONS[cmd]}?limit=100', args)
    elif cmd == 'dependencias':
        before = pages(f'/tasks/{args.id}/prerequisites?limit=100', args)
        after = pages(f'/tasks/{args.id}/descendants?limit=100', args)
        result = {'status': 200, 'body': {'pre_requisitos': before['body'], 'dependentes': after['body']}, 'truncated': before['truncated'] or after['truncated']}
    elif cmd == 'criar': result = create(args)
    else:
        task = get(f'/tasks/{args.id}')
        if cmd == 'ver': result = {'status': 200, 'body': task, 'description': description(args.id)}
        elif cmd == 'abrir':
            url = f'https://runrun.it/pt-BR/tasks/{args.id}'
            if not webbrowser.open(url): raise SystemExit('Não foi possível abrir: ' + url)
            result = {'status': 200, 'body': {'url': url}}
        elif cmd == 'tags' and not (args.adicionar or args.remover): result = {'status': 200, 'body': task.get('tags_data') or []}
        elif cmd == 'editar': result = edit(args, task)
        elif cmd == 'checklist': result = checklist(args, task)
        elif cmd == 'anexar':
            from rr_upload import attach
            result = attach(args, task, confirm, preview, checked)
        else: result = mutate_task(args, task)
    output(result, args)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'Erro: {exc}. Se houve escrita, reconcilie antes de repetir.') from exc
