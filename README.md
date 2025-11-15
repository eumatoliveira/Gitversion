# Gestor Completo de GitHub

Um gestor gráfico completo para GitHub, desenvolvido com CustomTkinter, PyGithub e GitPython, permitindo gerenciar repositórios, issues e operações Git locais em um único aplicativo.
Criado por @eumatoliveira (Vibing Code) em colaboração técnica com IA.

# ✨ Funcionalidades
🔐 Conexão com GitHub

- Autenticação via Token de Acesso Pessoal (PAT).

- Carregamento automático dos seus repositórios.

# 📂 Gestão de Repositórios

- Listagem, pesquisa e filtragem.

- Criação de repositórios públicos ou privados.

- Opção de criar README.md ao iniciar.

- Exclusão de repositórios pela interface.

# 💻 Operações Git Locais

- Clonar repositórios remotos.

- Fazer push de projetos locais para o GitHub.

- Fazer pull para sincronizar alterações.

# 📋 Gestão de Issues

- Listar issues abertas.

- Criar novas issues.

# 📊 Análise

- Gráficos de criação de repositórios ao longo do tempo.

# 📜 Log de Atividades

- Registro detalhado de ações, erros e horários.

# 🛠️ Pré-requisitos

Certifique-se de ter instalado:

🐍 Python 3.9+

🔷 Git adicionado ao PATH

# 🚀 Instalação e Configuração

1️⃣ Clonar o Repositório
````
git clone https://github.com/eumatoliveira/GITLIGHT.git
````
````
cd GITLIGHT
````
2️⃣ Criar e Ativar Ambiente Virtual
# Criar ambiente

````
python -m venv venv
````

# Ativar (Windows)

````
source venv/Scripts/activate
````

# Ativar (Linux/macOS)

````
source venv/bin/activate
````

3️⃣ Instalar Dependências

````
python -m pip install --upgrade pip
pip install -r requirements.txt
````

# Principais bibliotecas (caso falte algo no requirements):

````
pip install customtkinter pygithub gitpython pandas matplotlib
````

# 🔐 Gerando seu Token (PAT) no GitHub

Acesse: Settings

Vá até Developer settings

Entre em Personal access tokens → Tokens (classic)

Clique em Generate new token (classic)

Permissões necessárias:

````
repo
delete_repo

Copie o token gerado (formato ghp_XXXXXXXX).

````

▶️ Executar a Aplicação

Com o ambiente virtual ativado:

````
cd /pasta do arquivo que você clonou
````
````
python app.py

py app.py
````

# Se der tudo certo, o log mostrará:

[HH:MM:SS] ✓ Conectado como: seu-usuario
[HH:MM:SS] ✓ Repositórios carregados com sucesso

# 🔧 Tecnologias Utilizadas

CustomTkinter — Interface moderna

PyGithub — API do GitHub

GitPython — Operações git locais

Pandas & Matplotlib — Gráficos de atividade
