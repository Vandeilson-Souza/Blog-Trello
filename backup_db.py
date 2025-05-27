import os
import shutil
from datetime import datetime
import sys

def backup_database():
    # Determina o caminho do banco de dados
    if os.getenv('FLASK_ENV') == 'production':
        db_path = '/app/data/blog_trello.db'
    else:
        # Em desenvolvimento, procura na pasta instance
        db_path = os.path.join('instance', 'blog_trello.db')

    # Verifica se o banco de dados existe
    if not os.path.exists(db_path):
        print(f"Erro: Banco de dados não encontrado em {db_path}")
        sys.exit(1)

    # Cria o diretório de backup se não existir
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    # Gera o nome do arquivo de backup com timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'blog_trello_backup_{timestamp}.db')

    try:
        # Faz uma cópia do banco de dados
        shutil.copy2(db_path, backup_file)
        print(f"Backup criado com sucesso: {backup_file}")
    except Exception as e:
        print(f"Erro ao criar backup: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    backup_database() 