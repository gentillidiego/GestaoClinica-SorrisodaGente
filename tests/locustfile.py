"""
Locust Load Test — GestãoClínica
==================================
Simula o fluxo real de 100 usuários simultâneos na aplicação.

Pré-requisitos:
    pip install locust

Como executar:
    locust -f tests/locustfile.py --host=http://localhost:5002
    # Depois abra http://localhost:8089 no browser

Metas de aprovação (S8):
    - P95 < 2000ms
    - Taxa de erros < 0.5%
    - RPS > 20 com 100 usuários

Ajuste USERNAME e PASSWORD para um usuário válido do sistema.
"""
from locust import HttpUser, task, between
from bs4 import BeautifulSoup

USERNAME = "admin"   # ← Trocar pelo usuário de teste
PASSWORD = "admin"   # ← Trocar pela senha de teste


class ClinicaUser(HttpUser):
    """Usuário clínico típico navegando entre pacientes e abas."""
    wait_time = between(1, 3)  # Espera realista entre ações

    def on_start(self):
        """Faz login ao iniciar a sessão do usuário virtual."""
        # Obter o token CSRF da página de login
        response = self.client.get("/login")
        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_token_input = soup.find('input', {'name': 'csrf_token'})
        csrf_token = csrf_token_input['value'] if csrf_token_input else ''

        response = self.client.post("/login", data={
            "username": USERNAME,
            "password": PASSWORD,
            "csrf_token": csrf_token
        }, allow_redirects=True)
        if response.status_code != 200:
            self.environment.runner.quit()

    @task(4)
    def list_patients(self):
        """Lista de pacientes — operação mais frequente."""
        self.client.get("/patients/list", name="/patients/list")

    @task(3)
    def view_patient(self):
        """Abre prontuário de um paciente."""
        self.client.get("/patients/view/1", name="/patients/view/[id]")

    @task(2)
    def view_tab_atendimento(self):
        """Abre aba de atendimento — query com índice em patient_id."""
        self.client.get(
            "/patients/view/1/tab/tab-atendimento",
            name="/patients/view/[id]/tab/tab-atendimento"
        )

    @task(2)
    def view_tab_tratamento(self):
        """Abre aba de tratamento."""
        self.client.get(
            "/patients/view/1/tab/tab-tratamento",
            name="/patients/view/[id]/tab/tab-tratamento"
        )

    @task(1)
    def view_tab_exames(self):
        """Abre aba de exames."""
        self.client.get(
            "/patients/view/1/tab/tab-exames",
            name="/patients/view/[id]/tab/tab-exames"
        )

    @task(1)
    def health_check(self):
        """Verifica o endpoint de health — simula monitoramento externo."""
        self.client.get("/health", name="/health")
