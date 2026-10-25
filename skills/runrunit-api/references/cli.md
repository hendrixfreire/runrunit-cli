# CLI Runrun.it

Os comandos operacionais da API aceitam `--json`; `configurar` e `--version` são exceções. Exemplos de escrita abaixo mostram a preparação; use `--dry-run` para revisar sem alterar, ou execute no terminal e digite o ID para confirmar. Em automação autorizada, acrescente `--confirmar ID`; criar tarefa exige `--confirmar CRIAR`.

## Consultas e rotina

```bash
rr minhas
rr buscar "Relatório"
rr hoje
rr atrasadas
rr trabalhando
rr resumo --por projeto
rr resumo --por prazo
rr resumo --por urgencia
rr ver 123456
rr comentarios 123456
rr subtarefas 123456
rr dependencias 123456
rr arquivos 123456
rr abrir 123456
```

`dependencias` retorna pré-requisitos e dependentes separadamente. `abrir` consulta a tarefa e abre sua URL no navegador padrão. `hoje` considera o dia do prazo, e `atrasadas` os dias anteriores, não o horário vencido dentro do dia atual. `resumo` mantém projetos distintos pelo ID, mesmo com nomes iguais. Todos esses filtros e totais são sobre suas tarefas abertas atribuídas, dentro dos limites de paginação e permissões da API.

A identidade dessas consultas segue a precedência `--usuario ID`, `RUNRUNIT_USER_ID` e, na ausência dos dois, o dono do User-Token resolvido por `GET /users?me_first=true&limit=1`. Não há usuário padrão embutido. `--help` e comandos que não dependem de identidade não consultam usuários.

Coleções e consultas de rotina aceitam `--max-pages N --max-items N`. JSON inclui `truncated`; em dependências, esse indicador é verdadeiro se qualquer uma das duas coleções estiver parcial.

## Descobrir IDs

```bash
rr quadros
rr etapas --quadro 123
rr projetos
rr usuarios
rr tipos
rr equipes
```

Confirme IDs e contexto; nomes podem ser duplicados. `mover` aceita apenas etapa do quadro atual. Para criar, quadro e tipo são obrigatórios nesta CLI; projeto é opcional quando a conta permitir.

## Criar e alterar tarefas

```bash
rr criar "Revisar relatório" --quadro 123 --tipo ID --projeto ID --etapa ID --dry-run
rr entregar 123456 --dry-run
rr reabrir 123456 --dry-run
rr mover 123456 --etapa ID --dry-run
rr prazo 123456 2026-10-30 --dry-run
rr prazo 123456 --limpar --dry-run
rr editar 123456 --titulo "Novo título" --dry-run
rr editar 123456 --descricao '<p>Nova descrição</p>' --dry-run
rr editar 123456 --descricao-arquivo descricao.html --dry-run
rr urgente 123456 --dry-run
rr urgente 123456 --remover --dry-run
rr iniciar 123456 --dry-run
rr pausar 123456 --dry-run
rr comentar 123456 "Texto do comentário" --dry-run
```

Título e descrição podem ser editados juntos, mas não são atômicos: a primeira alteração pode concluir e a segunda falhar. Descrição usa recurso `/description`, separado da tarefa, e é enviada como HTML literal, sem converter Markdown. `--descricao-arquivo` lê UTF-8. Datas exigem `YYYY-MM-DD` válido. Limpar prazo envia `null`.

## Responsáveis e tags

```bash
rr atribuir 123456 --usuario ID --equipe ID --dry-run
rr atribuir 123456 --usuario ID --remover --dry-run
rr tags 123456
rr tags 123456 --adicionar auditoria --adicionar dados --remover antiga --dry-run
```

Adicionar responsável preserva os demais; equipe usa `--equipe` ou a equipe atual da tarefa, validada por leitura. Remover resolve o ID do assignment, não o ID do usuário. Assignment ausente/ambíguo é recusado. Tags preservam entradas e cores existentes; flags são repetíveis. Nomes são exatos e novas tags podem ser criadas pela API. A atualização substitui a coleção inteira; evite alterações concorrentes na mesma tarefa.

## Checklist

```bash
rr checklist 123456
rr checklist 123456 --criar "Validações" --dry-run
rr checklist 123456 --titulo "Novo título" --dry-run
rr checklist 123456 --adicionar "Conferir contagem" --dry-run
rr checklist 123456 --concluir ITEM_ID --dry-run
rr checklist 123456 --reabrir ITEM_ID --dry-run
rr checklist 123456 --editar-item ITEM_ID --texto "Nova descrição" --dry-run
rr checklist 123456 --excluir-item ITEM_ID --dry-run
```

A CLI resolve o checklist pela tarefa e confere a associação do item. Criar exige ausência de checklist; adicionar item exige checklist existente. Exclusão de item exige a mesma confirmação pelo ID da tarefa. Sem checklist, a consulta retorna `body: null`.

## Horas e anexos

```bash
rr horas 123456 --duracao 1h30 --data 2026-10-23 --motivo "Revisão" --dry-run
rr anexar 123456 relatorio.md --dry-run
```

Durações aceitas: `1h30`, `1h30m`, `90m`, `5400s`; devem ser positivas. Apontamento registra duração numa data, não intervalo início/fim. A etapa vem da tarefa. `--equipe ID` é opcional. Não repita após timeout sem consultar os apontamentos existentes.

Anexo congela os bytes antes da confirmação, mostra nome/tamanho/SHA-256, faz upload, confirma e baixa para comparar hash. Sem encaminhar App-Key/User-Token ao storage. Destino preferencial vem de `upload_url`/`action_url` da resposta; `RUNRUNIT_UPLOAD_URL` permite configuração local quando a API só retorna `fields`. O padrão atual é o destino Oracle publicado no exemplo oficial, e pode precisar de atualização se o provedor mudar. Não derive um endpoint apenas do bucket da Policy. O teste local simula o fluxo; um envio real exige autorização para anexar o arquivo à tarefa.

## Validação e fontes

```bash
# No checkout do repositório runrunit-cli, não na pasta da skill:
python -m unittest discover -s . -p 'test*.py'
```

Os testes usam mocks para escritas e storage. Leituras reais validam acesso/formatos, mas não provam execução real de cada escrita.

- Contrato: https://runrun.it/api/documentation
- Upload atual: https://github.com/Runrunit/api_examples/blob/main/upload_file_to_task.py

Contratos conferidos em 23/10/2026. Comandos técnicos `task`, `request`, `paginate` permanecem disponíveis; nenhuma escrita tem repetição automática.
