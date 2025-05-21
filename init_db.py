from app import app, db
from datetime import datetime

with app.app_context():
    # Remove todas as tabelas existentes
    db.drop_all()
    # Cria todas as tabelas novamente
    db.create_all()
    print("Banco de dados inicializado com sucesso!") 