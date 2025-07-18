from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv
from trello import TrelloClient
import json
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configuração do banco de dados
if os.getenv('FLASK_ENV') == 'production':
    # Em produção, usa o caminho absoluto
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/blog_trello.db'
else:
    # Em desenvolvimento, usa o caminho relativo
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog_trello.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'chave-secreta-padrao')  # Adicione uma chave secreta no .env

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Garante que o banco de dados seja criado
with app.app_context():
    db.create_all()

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

# Modelo de usuário
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
   'https://blog.eagenda.com.br/wp-json/wp/v2/docs?doc_category=35&per_page=100',
   'https://blog.etalentos.com.br/wp-json/wp/v2/docs?doc_category=8&per_page=100',
   'https://blog.etalentos.com.br/wp-json/wp/v2/docs?doc_category=7&per_page=100',
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
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)  # Permite customizar posts por página
    
    # Limita o per_page a valores razoáveis
    if per_page not in [6, 12, 24, 48]:
        per_page = 12
    
    # Obtém os filtros da URL
    category = request.args.get('category')
    status = request.args.get('status')
    search = request.args.get('search')
    source = request.args.get('source')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Inicia a query
    query = Post.query
    
    # Aplica os filtros
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(review_status=status)
    if search:
        query = query.filter(Post.title.ilike(f'%{search}%'))
    if source:
        query = query.filter_by(source=source)
    if date_from:
        query = query.filter(Post.updated_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Post.updated_at <= datetime.strptime(date_to, '%Y-%m-%d'))
    
    # Obtém todas as categorias únicas
    categories = db.session.query(Post.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    # Obtém todas as fontes únicas
    sources = db.session.query(Post.source).distinct().all()
    sources = [src[0] for src in sources if src[0]]
    
    # Obtém o total geral de posts
    total_posts = query.count()
    
    # Obtém contagens por status
    total_updated = query.filter_by(review_status='recent').count()
    total_need_review = query.filter_by(review_status='old').count()
    total_never_reviewed = query.filter_by(review_status='never').count()
    
    # Aplica a paginação e ordenação (mais antigos primeiro)
    pagination = query.order_by(Post.updated_at.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    posts = pagination.items
    
    return render_template('index.html', 
                         posts=posts, 
                         pagination=pagination, 
                         categories=categories, 
                         sources=sources,
                         total_posts=total_posts,
                         total_updated=total_updated,
                         total_need_review=total_need_review,
                         total_never_reviewed=total_never_reviewed)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print(f"Tentativa de login para usuário: {username}")  # Log para debug
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            print(f"Login bem sucedido para: {username}")  # Log para debug
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        print(f"Falha no login para: {username}")  # Log para debug
        flash('Usuário ou senha inválidos')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/create_user', methods=['POST'])
def create_user():
    if not User.query.first():  # Permite criar o primeiro usuário sem autenticação
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Usuário já existe'})
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Não autorizado'}), 403

@app.route('/create_trello_card', methods=['POST'])
@login_required
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
        # Ajusta a data para o final do dia no fuso horário local
        if due_date:
            due_date = f"{due_date}T23:59:59"
            
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
@login_required
def refresh_posts():
    """Endpoint para atualizar o cache de posts"""
    fetch_posts()
    return jsonify({'success': True})

@app.route('/get_trello_members')
@login_required
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

@app.route('/create_independent_card', methods=['POST'])
@login_required
def create_independent_card():
    """Cria um card independente no Trello"""
    data = request.json
    card_type = data.get('card_type')
    source = data.get('source')
    title = data.get('title')
    link = data.get('link', '')
    assignee_id = data.get('assignee')
    due_date = data.get('due_date')
    description = data.get('description', '')
    canva_type = data.get('canva_type', '')
    
    try:
        # Ajusta a data para o final do dia no fuso horário local
        if due_date:
            due_date = f"{due_date}T23:59:59"
        
        # Define o prefixo baseado no tipo
        if card_type == 'post':
            prefix = "Criar Post:"
        elif card_type == 'tutorial':
            prefix = "Criar Tutorial:"
        elif card_type == 'canva':
            prefix = f"Criar {canva_type.capitalize()} Canva:"
        else:
            prefix = "Tarefa:"
        
        # Busca o nome do responsável
        assignee_name = "Não atribuído"
        if assignee_id:
            board = trello_client.get_board(os.getenv('TRELLO_BOARD_ID'))
            members = board.get_members()
            for member in members:
                if member.id == assignee_id:
                    assignee_name = member.full_name
                    break

        # Formata a data para exibição
        display_date = "Não definido"
        if due_date:
            display_date = datetime.strptime(due_date, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y")

        # Monta a descrição do card
        card_description = ""
        
        if source:
            card_description += f"**Fonte:** {source}\n"
        
        if assignee_id:
            card_description += f"**Responsável:** {assignee_name}\n"
        
        if due_date:
            card_description += f"**Prazo:** {display_date}\n"
        
        if card_description:
            card_description += "\n"
        
        if link:
            card_description += f"**Link:** {link}\n\n"
        
        if card_type == 'canva':
            card_description += f"**Tipo de Publicação:** {canva_type.capitalize()}\n\n"
            card_description += "**Dimensões Recomendadas:**\n"
            if canva_type == 'post':
                card_description += "- 1080 x 1350 pixels\n\n"
            elif canva_type == 'story':
                card_description += "- 1080 x 1920 pixels\n\n"
            
            card_description += "**Instruções:**\n"
            card_description += "1. Criar o material no Canva usando as dimensões acima\n"
            card_description += "2. Ao finalizar, copiar o link do material\n"
            card_description += "3. Anexar o link na descrição deste card\n\n"
        
        if description:
            card_description += f"**Detalhes:**\n{description}"

        # Cria o card no Trello
        card = trello_client.get_list(os.getenv('TRELLO_LIST_ID')).add_card(
            name=f"{prefix} {title}",
            desc=card_description,
            due=due_date
        )

        # Adiciona o membro ao card
        if assignee_id:
            card.assign(assignee_id)

        return jsonify({'success': True, 'card_id': card.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/mark_post_updated', methods=['POST'])
@login_required
def mark_post_updated():
    try:
        data = request.get_json()
        post_id = data.get('post_id')
        
        if not post_id:
            return jsonify({'success': False, 'error': 'ID do post não fornecido'})
        
        # Atualiza o status do post
        post = Post.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'error': 'Post não encontrado'})
            
        # Atualiza a data da última revisão e o status
        post.last_review_date = datetime.now()
        post.update_review_status()
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_post', methods=['POST'])
@login_required
def delete_post():
    """Exclui um post do cache"""
    try:
        data = request.get_json()
        post_id = data.get('post_id')
        
        if not post_id:
            return jsonify({'success': False, 'error': 'ID do post não fornecido'})
        
        # Busca o post
        post = Post.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'error': 'Post não encontrado'})
            
        # Exclui o post
        db.session.delete(post)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/mark_recent_posts_updated', methods=['POST'])
@login_required
def mark_recent_posts_updated():
    """Marca como atualizados todos os posts modificados nos últimos 30 dias e que não estejam atualizados"""
    try:
        # Calcula a data de 30 dias atrás
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Busca todos os posts modificados nos últimos 30 dias e que não estão atualizados
        recent_posts = Post.query.filter(
            Post.updated_at >= thirty_days_ago,
            Post.review_status != 'recent'
        ).all()
        
        # Contador de posts atualizados
        updated_count = 0
        
        # Atualiza cada post
        for post in recent_posts:
            post.last_review_date = datetime.now()
            post.update_review_status()
            updated_count += 1
        
        # Salva as alterações
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{updated_count} posts foram marcados como atualizados'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/create_batch_cards', methods=['POST'])
@login_required
def create_batch_cards():
    """Cria um card individual em lote com distribuição opcional na semana"""
    data = request.json
    card_type = data.get('card_type')
    source = data.get('source')
    assignee_ids = data.get('assignees', [])
    canva_type = data.get('canva_type', '')
    distribute_week = data.get('distribute_week', False)
    distribute_period = data.get('distribute_period', False)
    start_day = data.get('start_day', 'monday')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    titles = data.get('titles', [])
    card_index = data.get('card_index', 0)
    
    try:
        # Busca os nomes dos responsáveis
        assignee_names = []
        if assignee_ids:
            board = trello_client.get_board(os.getenv('TRELLO_BOARD_ID'))
            members = board.get_members()
            for assignee_id in assignee_ids:
                for member in members:
                    if member.id == assignee_id:
                        assignee_names.append(member.full_name)
                        break

        # Calcula as datas disponíveis baseado no tipo de distribuição
        today = datetime.now()
        available_days = []
        
        if distribute_period and start_date and end_date:
            # Distribuição por período específico
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            current = start
            while current <= end:
                # Ignora sábados (5) e domingos (6)
                if current.weekday() < 5:  # 0=segunda, 1=terça, ..., 4=sexta
                    available_days.append(current)
                current += timedelta(days=1)
                
        elif distribute_week:
            # Distribuição na semana atual
            # Mapeia os dias da semana
            day_mapping = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 
                'thursday': 3, 'friday': 4
            }
            
            # Calcula o próximo dia de início
            start_day_num = day_mapping.get(start_day, 0)
            current_weekday = today.weekday()
            
            # Se o dia de início já passou esta semana, vai para a próxima semana
            if current_weekday > start_day_num:
                days_until_start = 7 - current_weekday + start_day_num
            else:
                days_until_start = start_day_num - current_weekday
            
            start_date = today + timedelta(days=days_until_start)
            
            # Cria lista de dias disponíveis a partir do dia de início
            for i in range(5):  # Segunda a sexta
                day = start_date + timedelta(days=i)
                if day.weekday() < 5:  # Apenas dias úteis
                    available_days.append(day)
        else:
            available_days = []

        # Processa apenas o primeiro título da lista (um card por vez)
        if not titles:
            return jsonify({'success': False, 'error': 'Nenhum título fornecido'})
        
        title = titles[0]
        
        # Define o prefixo baseado no tipo
        if card_type == 'post':
            prefix = "Criar Post:"
        elif card_type == 'tutorial':
            prefix = "Criar Tutorial:"
        elif card_type == 'canva':
            prefix = f"Criar {canva_type.capitalize()} Canva:"
        else:
            prefix = "Tarefa:"

        # Escolhe o responsável e dia para este card (distribuição equilibrada)
        selected_assignee_id = None
        due_date = None
        
        if assignee_ids and (distribute_week or distribute_period) and available_days:
            # Calcula quantos cards por responsável por dia
            total_assignees = len(assignee_ids)
            total_days = len(available_days)
            
            # Determina qual responsável e qual dia para este card
            assignee_index = card_index % total_assignees
            day_index = (card_index // total_assignees) % total_days
            
            selected_assignee_id = assignee_ids[assignee_index]
            due_date = available_days[day_index].strftime("%Y-%m-%d") + "T23:59:59"
            
        elif assignee_ids:
            # Se não há distribuição por dia, apenas rota entre responsáveis
            selected_assignee_id = assignee_ids[card_index % len(assignee_ids)]
            
        elif (distribute_week or distribute_period) and available_days:
            # Se não há responsáveis selecionados, apenas distribui por dia
            day_index = card_index % len(available_days)
            due_date = available_days[day_index].strftime("%Y-%m-%d") + "T23:59:59"

        # Monta a descrição do card
        card_description = ""
        
        if source:
            card_description += f"**Fonte:** {source}\n"
        
        if assignee_names:
            card_description += f"**Responsáveis:** {', '.join(assignee_names)}\n"
        
        if due_date:
            display_date = datetime.strptime(due_date, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y")
            card_description += f"**Prazo:** {display_date}\n"
        
        if card_description:
            card_description += "\n"
        
        if card_type == 'canva':
            card_description += f"**Tipo de Publicação:** {canva_type.capitalize()}\n\n"
            card_description += "**Dimensões Recomendadas:**\n"
            if canva_type == 'post':
                card_description += "- 1080 x 1350 pixels\n\n"
            elif canva_type == 'story':
                card_description += "- 1080 x 1920 pixels\n\n"
            
            card_description += "**Instruções:**\n"
            card_description += "1. Criar o material no Canva usando as dimensões acima\n"
            card_description += "2. Ao finalizar, copiar o link do material\n"
            card_description += "3. Anexar o link na descrição deste card\n\n"

        # Cria o card no Trello
        card = trello_client.get_list(os.getenv('TRELLO_LIST_ID')).add_card(
            name=f"{prefix} {title}",
            desc=card_description,
            due=due_date
        )

        # Adiciona o responsável selecionado ao card
        if selected_assignee_id:
            card.assign(selected_assignee_id)

        return jsonify({
            'success': True, 
            'created_count': 1,
            'card_id': card.id,
            'message': f'Card "{title}" criado com sucesso!'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port) 