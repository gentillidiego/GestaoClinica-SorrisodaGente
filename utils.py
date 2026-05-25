from flask_login import UserMixin
from database import query
from constants import Role

class User(UserMixin):
    def __init__(self, id, username, role, full_name=None, matricula=None, cro=None, cro_uf=None):
        self.id = id
        self.username = username
        self.role = role
        self.full_name = full_name
        self.matricula = matricula
        self.cro = cro
        self.cro_uf = cro_uf

    @staticmethod
    def get(user_id):
        user_data = query("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                role=user_data['role'],
                full_name=user_data.get('full_name'),
                matricula=user_data.get('matricula'),
                cro=user_data.get('cro'),
                cro_uf=user_data.get('cro_uf')
            )
        return None

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def is_dentista(self):
        return self.role == Role.DENTISTA

    @property
    def is_tsb(self):
        return self.role == Role.TSB

    @property
    def is_atendente(self):
        return self.role == Role.ATENDENTE
