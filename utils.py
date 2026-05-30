from flask_login import UserMixin
from database import query
from constants import Role, get_role_label, role_has_permission

class User(UserMixin):
    def __init__(self, id, username, role, full_name=None, matricula=None, cro=None, cro_uf=None, active=True):
        self.id = id
        self.username = username
        self.role = role
        self.full_name = full_name
        self.matricula = matricula
        self.cro = cro
        self.cro_uf = cro_uf
        self.active = active

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
                cro_uf=user_data.get('cro_uf'),
                active=user_data.get('active', True)
            )
        return None

    @property
    def is_active(self):
        return bool(self.active)

    @property
    def role_label(self):
        return get_role_label(self.role)

    def can(self, permission):
        return role_has_permission(self.role, permission)

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
        return self.role in [Role.ATENDENTE, Role.ATENDIMENTO_LEGACY]
