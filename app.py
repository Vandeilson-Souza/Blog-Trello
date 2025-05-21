from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from trello import TrelloClient
import json

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/blog_trello.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo para cache dos posts
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    trello_card_id = db.Column(db.String(100), nullable=True)
    last_review_date = db.Column(db.DateTime, nullable=True)
    review_status = db.Column(db.String(50), nullable=True)  # 'never', 'recent', 'old'

    def update_review_status(self):
        """Atualiza o status de revisão baseado na data da última revisão"""
        if not self.last_review_date:
            self.review_status = 'never'
        else:
            days_since_review = (datetime.now() - self.last_review_date).days
            if days_since_review < 30:
                self.review_status = 'recent'
            else:
                self.review_status = 'old'

# Configuração do cliente Trello
trello_client = TrelloClient(
    api_key=os.getenv('TRELLO_API_KEY'),
    token=os.getenv('TRELLO_TOKEN')
)

# Lista de URLs dos blogs
BLOG_URLS = [
    'https://meuatendimentovirtual.com.br/wp-json/wp/v2/docs?doc_category=35&per_page=100',
    'https://meuatendimentovirtual.com.br/wp-json/wp/v2/docs?doc_category=51&per_page=100',
    'https://meuatendimentovirtual.com.br/wp-json/wp/v2/docs?doc_category=50&per_page=100',
    'https://meuatendimentovirtual.com.br/wp-json/wp/v2/docs?doc_category=45&per_page=100',
    'https://meuatendimentovirtual.com.br/wp-json/wp/v2/docs?doc_category=46&per_page=100',
    'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=27&per_page=100',
    'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=4&per_page=100',
    'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=9&per_page=100',
    'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=28&per_page=100',
    'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=29&per_page=100',
    'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=32&per_page=100',
    'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=30&per_page=100',
]

def fetch_posts():
    """Busca posts de todas as URLs e atualiza o cache"""
    for url in BLOG_URLS:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                posts = response.json()
                for post in posts:
                    # Extrai o domínio para identificar a fonte
                    source = url.split('/')[2]
                    category = post.get('categories', ['Sem categoria'])[0]
                    
                    # Verifica se o post já existe no cache
                    existing_post = Post.query.filter_by(url=post['link']).first()
                    if existing_post:
                        existing_post.title = post['title']['rendered']
                        existing_post.updated_at = datetime.fromisoformat(post['modified'].replace('Z', '+00:00'))
                        existing_post.category = category
                        # Mantém a data da última revisão se já existir
                        if not existing_post.last_review_date:
                            existing_post.review_status = 'never'
                        else:
                            existing_post.update_review_status()
                    else:
                        new_post = Post(
                            title=post['title']['rendered'],
                            url=post['link'],
                            updated_at=datetime.fromisoformat(post['modified'].replace('Z', '+00:00')),
                            category=category,
                            source=source,
                            review_status='never',
                            last_review_date=None
                        )
                        db.session.add(new_post)
            
            db.session.commit()
        except Exception as e:
            print(f"Erro ao buscar posts de {url}: {str(e)}")

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Número de posts por página
    
    # Obtém os filtros da URL
    category = request.args.get('category')
    status = request.args.get('status')
    search = request.args.get('search')
    
    # Inicia a query
    query = Post.query
    
    # Aplica os filtros
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(review_status=status)
    if search:
        query = query.filter(Post.title.ilike(f'%{search}%'))
    
    # Obtém todas as categorias únicas
    categories = db.session.query(Post.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    # Se houver filtros ativos, mostra todos os resultados sem paginação
    if category or status or search:
        posts = query.order_by(Post.updated_at.desc()).all()
        return render_template('index.html', posts=posts, categories=categories)
    
    # Caso contrário, aplica a paginação
    pagination = query.order_by(Post.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    posts = pagination.items
    
    return render_template('index.html', posts=posts, pagination=pagination, categories=categories)

@app.route('/create_trello_card', methods=['POST'])
def create_trello_card():
    """Cria um card no Trello com as informações do post"""
    data = request.json
    post_id = data.get('post_id')
    assignee_id = data.get('assignee')
    due_date = data.get('due_date')
    labels = data.get('labels', [])
    description = data.get('description', '')

    post = Post.query.get_or_404(post_id)
    
    try:
        # Busca o nome do responsável
        assignee_name = "Não atribuído"
        if assignee_id:
            board = trello_client.get_board(os.getenv('TRELLO_BOARD_ID'))
            members = board.get_members()
            for member in members:
                if member.id == assignee_id:
                    assignee_name = member.full_name
                    break

        # Cria o card no Trello
        card = trello_client.get_list(os.getenv('TRELLO_LIST_ID')).add_card(
            name=f"Revisar post: {post.title}",
            desc=f"""Post original: {post.url}
Responsável: {assignee_name}
Prazo: {due_date}

Conteúdo para revisão:

{description}""",
            due=due_date
        )

        # Adiciona o membro ao card
        if assignee_id:
            card.assign(assignee_id)

        # Adiciona as labels
        for label in labels:
            card.add_label(label)

        # Atualiza o cache com o ID do card e a data da revisão
        post.trello_card_id = card.id
        post.last_review_date = datetime.now()
        post.update_review_status()
        db.session.commit()

        return jsonify({'success': True, 'card_id': card.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/refresh_posts')
def refresh_posts():
    """Endpoint para atualizar o cache de posts"""
    fetch_posts()
    return jsonify({'success': True})

@app.route('/get_trello_members')
def get_trello_members():
    """Retorna a lista de membros do board do Trello"""
    try:
        board = trello_client.get_board(os.getenv('TRELLO_BOARD_ID'))
        members = board.get_members()
        return jsonify({
            'success': True,
            'members': [{
                'id': member.id,
                'name': member.full_name,
                'username': member.username
            } for member in members]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port) 