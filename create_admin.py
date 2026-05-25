import os
import sys
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from database import execute, query, init_db
from constants import Role

load_dotenv()

def create_default_user():
    username = os.getenv('ADMIN_USERNAME')
    password = os.getenv('ADMIN_PASSWORD')

    if not username or not password:
        print("❌ Defina ADMIN_USERNAME e ADMIN_PASSWORD no ambiente antes de executar.")
        print("   Exemplo: ADMIN_USERNAME=admin ADMIN_PASSWORD=senha_segura python create_admin.py")
        sys.exit(1)

    init_db()
    role = Role.ADMIN

    # Verifica se o usuário já existe
    existing_user = query("SELECT id FROM users WHERE username = %s", (username,), one=True)

    if not existing_user:
        hashed_password = generate_password_hash(password)
        execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, hashed_password, role))
        print(f"✅ Usuário '{username}' criado com sucesso!")
    else:
        print(f"ℹ️  Usuário '{username}' já existe.")

if __name__ == '__main__':
    create_default_user()
