# Runrun.it CLI

Gerencie tarefas do Runrun.it pelo terminal, com comandos em português, saída legível e JSON para automações.

```bash
rr minhas
rr hoje
rr resumo --por prazo
rr ver 123456
```

A CLI usa a API oficial do Runrun.it. É escrita em Python, executada por um script Bash e não é um programa compilado. Não é um produto oficial do Runrun.it.

## O que você pode fazer

- Consultar tarefas abertas, buscar por título e filtrar prazos ou contadores ativos.
- Ver descrição, comentários, arquivos, subtarefas e dependências.
- Criar, entregar, reabrir, mover e editar tarefas.
- Gerenciar responsáveis, urgência, tags e checklists.
- Iniciar/pausar trabalho, registrar horas manuais e anexar arquivos.
- Usar `--json` para integrar com scripts e agentes.

## Requisitos

- macOS ou Linux com Bash, Git, Python 3.10 ou superior e o comando `realpath` no PATH.
- Conta Runrun.it com acesso à API e permissões para as operações desejadas.
- App-Key e User-Token fornecidos pelo Runrun.it.

A aplicação não precisa de bibliotecas Python externas. Windows nativo não foi validado; em Windows, use um ambiente Linux pelo WSL, observando os mesmos requisitos.

Confira o ambiente:

```bash
python3 --version
git --version
command -v bash
command -v realpath
```

Se algum comando não existir, instale-o pelo gerenciador de pacotes do seu sistema antes de continuar. O acesso à API depende das condições da sua conta Runrun.it; consulte a [documentação oficial](https://runrun.it/api/documentation).

## Instalação

### 1. Baixe o projeto

```bash
mkdir -p "$HOME/projetos"
git clone https://github.com/hendrixfreire/runrunit-cli.git "$HOME/projetos/runrunit-cli"
cd "$HOME/projetos/runrunit-cli"
./rr --help
```

Se o repositório estiver privado, você precisa de permissão e autenticação GitHub para clonar.

### 2. Disponibilize o comando `rr`

```bash
mkdir -p "$HOME/.local/bin"
ln -s "$HOME/projetos/runrunit-cli/rr" "$HOME/.local/bin/rr"
export PATH="$HOME/.local/bin:$PATH"
rr --help
```

Se já existir um comando/arquivo `~/.local/bin/rr`, confira seu destino antes de substituí-lo. O comando acima não sobrescreve instalações existentes.

Para manter o PATH nos próximos terminais, adicione esta linha ao `~/.zshrc` (Zsh) ou ao arquivo de inicialização usado pelo seu Bash, como `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Não mova ou apague a pasta clonada enquanto usar essa instalação: `rr` é um link para o código dela. Também é possível executar `./rr` diretamente nessa pasta.

## Configuração das credenciais

Use suas próprias credenciais, obtidas nas configurações de integrações/API da sua conta Runrun.it. O User-Token define em nome de quem a CLI atua e quais permissões ela possui.

### 1. Crie um arquivo local fora do projeto

```bash
mkdir -p "$HOME/.config/runrunit-cli"
touch "$HOME/.config/runrunit-cli/env"
chmod 600 "$HOME/.config/runrunit-cli/env"
nano "$HOME/.config/runrunit-cli/env"
```

Preencha o arquivo com os valores reais:

```dotenv
RUNRUNIT_APP_KEY=SUA_APP_KEY
RUNRUNIT_USER_TOKEN=SEU_USER_TOKEN
```

Esse arquivo contém segredos: mantenha-o local e não envie seus valores ao GitHub, em screenshots ou mensagens. O formato aceito é `NOME=valor`, uma variável por linha, sem espaços em torno de `=`. Aspas externas simples ou duplas são aceitas; não há expansão de variáveis ou execução de comandos no arquivo.

### 2. Indique o arquivo à CLI

No terminal atual:

```bash
export RUNRUNIT_ENV_FILE="$HOME/.config/runrunit-cli/env"
```

Para persistir, adicione essa mesma linha ao arquivo de inicialização do seu shell (`~/.zshrc` ou o equivalente do Bash).

Se `RUNRUNIT_APP_KEY` e `RUNRUNIT_USER_TOKEN` já estiverem definidos no ambiente, o wrapper usa essas variáveis. A configuração antiga do Hermes em `~/.hermes/profiles/profissional/.env` continua como fallback quando `RUNRUNIT_ENV_FILE` não está definido; Hermes não é necessário para instalar ou usar a CLI.

### 3. Descubra seu usuário

```bash
rr request GET '/users?me_first=true&limit=1'
```

Localize o `id` do primeiro usuário em `body` e acrescente ao arquivo de configuração:

```dotenv
RUNRUNIT_USER_ID=seu-id-de-usuario
```

Esse ID não é a App-Key nem o User-Token. Configure-o para que os filtros de tarefas usem seu usuário: a versão atual mantém `hendrix-freire` como fallback de compatibilidade se nenhum ID for informado. Também é possível escolher explicitamente:

```bash
rr minhas --usuario seu-id-de-usuario
```

### 4. Faça a primeira consulta

```bash
rr minhas
rr resumo --por projeto
```

## Uso diário

```bash
# Suas tarefas abertas e com assignment ativo
rr minhas

# Buscar texto no título dessas tarefas
rr buscar "Relatório"

# Prazos e contadores
rr hoje
rr atrasadas
rr trabalhando

# Panorama por projeto, prazo ou urgência
rr resumo --por projeto
rr resumo --por prazo
rr resumo --por urgencia

# Detalhes e colaboração; substitua 123456 por um ID real
rr ver 123456
rr comentarios 123456
rr arquivos 123456
rr subtarefas 123456
rr dependencias 123456
rr checklist 123456
rr abrir 123456
```

`buscar` procura somente no título das suas tarefas abertas atribuídas, sem distinguir maiúsculas; não é uma busca global. `hoje` e `atrasadas` consideram o dia do prazo em `America/Sao_Paulo`, e não o horário vencido dentro do dia atual. As consultas continuam sujeitas às permissões do usuário na API.

## Alterar tarefas com prévia e confirmação

Para revisar uma operação sem executá-la, use `--dry-run`:

```bash
rr prazo 123456 2026-12-15 --dry-run
rr editar 123456 --titulo "Título revisado" --dry-run
rr entregar 123456 --dry-run
rr comentar 123456 "Revisão concluída" --dry-run
```

Sem `--dry-run`, a CLI mostra a tarefa e a operação e pede que você digite o ID para confirmar:

```bash
rr prazo 123456 2026-12-15
rr iniciar 123456
rr pausar 123456
```

Em execução sem terminal interativo, é preciso passar a confirmação explicitamente, após revisar a operação:

```bash
rr prazo 123456 2026-12-15 --confirmar 123456
```

Para criar tarefa, consulte os IDs das referências e revise a proposta:

```bash
rr quadros
rr tipos
rr projetos
rr etapas --quadro 111
rr criar "Revisar relatório" --quadro 111 --tipo 222 --projeto 333 --dry-run
```

Os números acima são exemplos. Use IDs reais e válidos da sua conta. A criação usa a confirmação `CRIAR` no terminal ou `--confirmar CRIAR` em automação.

Mais exemplos:

```bash
rr reabrir 123456 --dry-run
rr mover 123456 --etapa 444 --dry-run
rr urgente 123456 --dry-run
rr atribuir 123456 --usuario outro-usuario --equipe 555 --dry-run
rr tags 123456 --adicionar revisao --dry-run
rr checklist 123456 --adicionar "Conferir totais" --dry-run
rr horas 123456 --duracao 1h30 --data 2026-12-15 --motivo "Revisão" --dry-run
rr anexar 123456 relatorio.md --dry-run
```

O checklist precisa existir antes de adicionar itens; crie com `rr checklist 123456 --criar "Validações"`. Veja todas as opções em [COMANDOS.md](COMANDOS.md) ou com `rr COMANDO --help`.

A CLI não repete escritas automaticamente. Após timeout ou divergência na verificação, consulte o estado antes de reenviar: a operação pode ter sido concluída. Editar título e descrição juntos envolve duas requisições e pode terminar parcialmente.

## JSON, paginação e automações

```bash
rr minhas --json
rr minhas --max-pages 20 --max-items 2000 --json
rr comentarios 123456 --json
```

Coleções usam, por padrão, no máximo 10 páginas e 1.000 itens. `truncated: true` indica resultado parcial; aumente os limites antes de tratar a lista ou o resumo como completo. O limite é aplicado aos itens recebidos da API antes dos filtros locais, portanto o total exibido pode ser menor.

JSON é escrito em stdout; prévias e diagnósticos usam stderr. Escritas exigem a confirmação mesmo com `--json`. Os comandos técnicos `request`, `task` e `paginate` continuam disponíveis, mas não possuem a confirmação interativa da interface em português: use-os com atenção, principalmente em alterações.

## Atualizar

Com a pasta de trabalho sem alterações locais pendentes:

```bash
cd "$HOME/projetos/runrunit-cli"
git pull --ff-only
rr --help
```

Como `rr` aponta para o clone, a próxima execução já usa o código atualizado. Se você editar o código, registre suas alterações em uma branch antes de atualizar; não use comandos de descarte para resolver conflitos sem revisar.

## Desinstalar

Remova o link somente depois de conferir que ele aponta para este projeto:

```bash
ls -l "$HOME/.local/bin/rr"
unlink "$HOME/.local/bin/rr"
```

Depois, você pode remover a pasta clonada, se não houver alterações que queira guardar. As credenciais em `~/.config/runrunit-cli/env` permanecem separadas; decida se deseja mantê-las e remova as linhas de PATH/configuração do seu shell caso não sejam mais necessárias.

## Desenvolvimento e testes

Arquivos principais:

- `rr`: ponto de entrada e carregamento da configuração local.
- `rr_cli.py`: comandos em português.
- `runrunit_api.py`: cliente HTTP e comandos técnicos.
- `rr_upload.py`: envio multipart e conferência de anexos por SHA-256.
- `test_rr_cli.py` e `test_rr_extended.py`: testes com mocks, sem alterar tarefas reais.

Execute na raiz do projeto:

```bash
python3 -m unittest discover -s . -p 'test_rr*.py'
```

Para contribuir, crie uma branch, implemente uma mudança coesa, rode os testes e abra um pull request. Nunca inclua arquivos de credenciais ou respostas reais com dados privados em fixtures.

## Problemas comuns

- **`rr: command not found`**: confira o link e o PATH; tente `./rr --help` na pasta do projeto.
- **`python3` ou `realpath` não encontrado**: instale o requisito ausente e abra outro terminal.
- **Credenciais ausentes / HTTP 401**: confira `RUNRUNIT_ENV_FILE` e as credenciais da sua conta, sem imprimir seus valores.
- **HTTP 403**: a conta pode não ter permissão para a operação ou recurso.
- **HTTP 404**: confira o ID e o acesso ao recurso. A consulta de checklist ausente é tratada como `body: null`.
- **Tarefas de outro usuário ou lista vazia inesperada**: configure `RUNRUNIT_USER_ID` ou use `--usuario ID`.
- **HTTP 429**: aguarde o período indicado pela API; novas tentativas imediatas não resolvem o limite.
- **Upload interrompido**: reconcilie o ID do documento informado antes de reenviar; o registro pode ter sido criado mesmo sem upload completo.

## Limitações

A instalação atual é por clone e link, sem pacote PyPI ou executáveis independentes. O ambiente validado é macOS; testes locais simulam escritas e storage, e não comprovam todas as operações ao vivo ou a compatibilidade com cada sistema. O destino padrão de upload segue o exemplo oficial atual e pode exigir atualização se o provedor mudar; consulte `COMANDOS.md` para configuração.

## Referências

- [API oficial do Runrun.it](https://runrun.it/api/documentation)
- [Exemplos oficiais de upload](https://github.com/Runrunit/api_examples)
- [Referência completa dos comandos](COMANDOS.md)
