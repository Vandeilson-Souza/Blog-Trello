# Blog Trello

Aplicação web para gerenciar posts de blogs WordPress e criar tarefas no Trello automaticamente.

## Funcionalidades

- Lista posts de múltiplos blogs WordPress
- Cria tarefas no Trello com informações dos posts
- Sistema de cache local dos posts
- Filtros por categoria, status e busca por título
- Interface moderna com Bootstrap 5

## Requisitos

- Python 3.8+
- Conta no Trello com API Key e Token
- Board e Lista no Trello para receber as tarefas

## Instalação

1. Clone o repositório:
```bash
git clone [URL_DO_REPOSITÓRIO]
cd blog-trello
```

2. Crie um ambiente virtual e ative-o:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:
```ini
FLASK_APP=app.py
FLASK_ENV=development
TRELLO_API_KEY=sua_api_key_aqui
TRELLO_TOKEN=seu_token_aqui
TRELLO_BOARD_ID=id_do_board_aqui
TRELLO_LIST_ID=id_da_lista_aqui
DATABASE_URL=sqlite:///blog_trello.db
```

## Como obter as credenciais do Trello

1. API Key:
   - Acesse https://trello.com/app-key
   - Copie a "API Key" gerada

2. Token:
   - Na mesma página, clique em "Token"
   - Autorize o acesso e copie o token gerado

3. Board ID e List ID:
   - Abra o board no Trello
   - Adicione `.json` ao final da URL
   - Procure por `id` do board e `id` da lista desejada

## Executando a aplicação

1. Inicialize o banco de dados:
```bash
flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
```

2. Execute a aplicação:
```bash
flask run
```

3. Acesse http://localhost:5000 no navegador

## Estrutura do Projeto

```
blog-trello/
├── app.py              # Aplicação principal
├── requirements.txt    # Dependências
├── .env               # Configurações
├── templates/         # Templates HTML
│   └── index.html     # Template principal
└── blog_trello.db     # Banco de dados SQLite
```

## Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Crie um Pull Request

## Licença

Este projeto está licenciado sob a MIT License - veja o arquivo LICENSE para detalhes. 