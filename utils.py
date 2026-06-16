from flask_login import UserMixin
from database import query
from constants import Role, canonical_role, get_role_label, role_has_permission

class User(UserMixin):
    def __init__(
        self,
        id,
        username,
        role,
        full_name=None,
        matricula=None,
        email=None,
        celular=None,
        data_nascimento=None,
        cro=None,
        cro_uf=None,
        cns=None,
        cbo=None,
        cnes=None,
        ine=None,
        active=True,
        is_first_access=False,
    ):
        self.id = id
        self.username = username
        self.role = role
        self.full_name = full_name
        self.matricula = matricula
        self.email = email
        self.celular = celular
        self.data_nascimento = data_nascimento
        self.cro = cro
        self.cro_uf = cro_uf
        self.cns = cns
        self.cbo = cbo
        self.cnes = cnes
        self.ine = ine
        self.active = active
        self.is_first_access = is_first_access

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
                email=user_data.get('email'),
                celular=user_data.get('celular'),
                data_nascimento=user_data.get('data_nascimento'),
                cro=user_data.get('cro'),
                cro_uf=user_data.get('cro_uf'),
                cns=user_data.get('cns'),
                cbo=user_data.get('cbo'),
                cnes=user_data.get('cnes'),
                ine=user_data.get('ine'),
                active=user_data.get('active', True),
                is_first_access=user_data.get('is_first_access', False),
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
        return canonical_role(self.role) == Role.CLINICOS

    @property
    def is_tsb(self):
        return canonical_role(self.role) == Role.CLINICOS

    @property
    def is_atendente(self):
        return canonical_role(self.role) == Role.RECEPCAO
