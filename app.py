import subprocess
import webbrowser
import os
import shutil
from tkinter import messagebox, Tk, Listbox, filedialog
import sys
import threading
from pathlib import Path
from datetime import datetime  # <- ADICIONADO para o Log
from typing import Optional, List, Dict, Self, Tuple, Any  # Para type hints
from github.Repository import Repository as GitHubRepository  # Importa Repository com um alias
# customtkinter
import customtkinter as ctk  # type: ignore

# PyGithub
from github import Github, GithubException  # type: ignore
from github.GithubObject import NotSet  # type: ignore
from github.AuthenticatedUser import AuthenticatedUser  # type: ignore
from github.Repository import Repository  # type: ignore

# grafico

import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any 
import pandas as pd  # <- Adicione esta linha
import matplotlib.pyplot as plt  # <- Adicione esta linha
from matplotlib.dates import DateFormatter # <- Adicione esta linha


# GitPython
import git  # type: ignore

# ------------------------------------
# Funções Auxiliares de Verificação
# (Fora da classe, pois são usadas antes)
# ------------------------------------


def _get_startup_info() -> Optional[subprocess.STARTUPINFO]:
    """Cria STARTUPINFO para ocultar janelas do console no Windows."""
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo
    return None


def check_git_installed() -> bool:
    """Verifica se o Git está disponível no PATH."""
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
            startupinfo=_get_startup_info()
        )
        print("✓ Git está instalado.")
        return True

    except FileNotFoundError:
        print("✗ Git NÃO foi encontrado.")
        root_popup = Tk()
        root_popup.withdraw()
        resposta = messagebox.askyesno(
            "Git não encontrado",
            "O Git não foi encontrado no seu computador.\n"
            "Ele é essencial para este aplicativo funcionar.\n\n"
            "Deseja ir para a página de download do Git agora?"
        )
        if resposta:
            webbrowser.open_new("https://git-scm.com/downloads")
        root_popup.destroy()
        return False

    except subprocess.CalledProcessError:
        root_popup = Tk()
        root_popup.withdraw()
        messagebox.showerror(
            "Erro de Git", "O Git parece estar instalado, mas falhou ao executar. Tente reinstalá-lo.")
        root_popup.destroy()
        return False


def check_git_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Verifica se há credenciais Git configuradas."""
    try:
        startupinfo = _get_startup_info()
        name = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True, text=True, startupinfo=startupinfo
        ).stdout.strip()

        email = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True, text=True, startupinfo=startupinfo
        ).stdout.strip()

        return name, email
    except Exception:
        return None, None

# -------------------------
# Início da aplicação
# -------------------------


if not check_git_installed():
    print("Execução interrompida. O Git é necessário.")
    sys.exit(1)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# --- Classe para o Pop-up de escolha do IDE ---
class IDEPrompt(ctk.CTkToplevel):
    """Janela de diálogo para perguntar qual IDE abrir."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.geometry("400x200")
        self.title("Abrir Repositório")
        self.choice: Optional[str] = None  # Onde vamos guardar a escolha

        self.label = ctk.CTkLabel(
            self, text="Clone bem-sucedido!\nDeseja abrir a pasta em qual IDE?", font=("", 14))
        self.label.pack(pady=10, padx=10)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=10)

        self.vscode_button = ctk.CTkButton(
            button_frame, text="VS Code", command=lambda: self.select_ide("vscode"))
        self.vscode_button.pack(fill="x", padx=10, pady=5)

        self.jetbrains_button = ctk.CTkButton(
            button_frame, text="JetBrains (ex: PyCharm)", command=lambda: self.select_ide("jetbrains"))
        self.jetbrains_button.pack(fill="x", padx=10, pady=5)

        self.vs_button = ctk.CTkButton(
            button_frame, text="Visual Studio", command=lambda: self.select_ide("visualstudio"))
        self.vs_button.pack(fill="x", padx=10, pady=5)

        self.cancel_button = ctk.CTkButton(
            self, text="Cancelar", fg_color="gray", command=self.destroy)
        self.cancel_button.pack(pady=(0, 10))

        self.transient(self.master)  # type: ignore
        self.grab_set()

    def select_ide(self, ide_name: str) -> None:
        self.choice = ide_name
        self.destroy()

    def get_choice(self) -> Optional[str]:
        # Espera a janela ser fechada
        self.master.wait_window(self)
        return self.choice


class GitHubApp(ctk.CTk):

    # --- Constantes (Boas Práticas) ---
    APP_NAME = "Gestor Completo de GitHub"
    GEOMETRY = "1200x750"
    TEMP_DIR = Path.home() / ".github_manager_temp"
    
    # Type hints para atributos que são inicializados fora do __init__
    open_browser_button: ctk.CTkButton
    plot_button: ctk.CTkButton
    issue_textbox: ctk.CTkTextbox

    # Cores
    COLOR_SUCCESS = "#28a745"
    COLOR_SUCCESS_HOVER = "#218838"
    COLOR_DANGER = "#dc3545"
    COLOR_DANGER_HOVER = "#c82333"
    COLOR_PRIMARY = "#007bff"
    COLOR_PRIMARY_HOVER = "#0056b3"
    COLOR_SECONDARY = "#6f42c1"
    COLOR_SECONDARY_HOVER = "#5a32a3"
    COLOR_INFO = "#17a2b8"
    COLOR_INFO_HOVER = "#138496"

    # Fontes
    FONT_BOLD = ("", 14, "bold")
    FONT_LISTBOX = ("Consolas", 10)

    def __init__(self):
        super().__init__()
        self.title(self.APP_NAME)
        self.geometry(self.GEOMETRY)

        # Estado (com type hints)
        self.github_api: Optional[Github] = None
        self.github_user: Optional[AuthenticatedUser] = None
        self.current_repo_object: Optional[GitHubRepository] = None
        self.current_local_path: Optional[str] = None
        # CORRIGIDO: Removido .Repository extra
        self.repo_map: Dict[str, Repository] = {}

        # --- Widgets ---
        self.token_entry: ctk.CTkEntry
        self.connect_button: ctk.CTkButton
        self.git_name_entry: ctk.CTkEntry
        self.git_email_entry: ctk.CTkEntry
        self.save_git_config_button: ctk.CTkButton
        self.repo_name_entry: ctk.CTkEntry
        self.repo_desc_entry: ctk.CTkEntry
        self.private_var: ctk.BooleanVar
        self.private_checkbox: ctk.CTkCheckBox
        self.readme_var: ctk.BooleanVar  # <- ADICIONADO
        self.readme_checkbox: ctk.CTkCheckBox  # <- ADICIONADO
        self.create_repo_button: ctk.CTkButton
        self.refresh_repos_button: ctk.CTkButton
        self.search_entry: ctk.CTkEntry
        self.repo_listbox: Listbox
        self.delete_repo_button: ctk.CTkButton
        self.open_browser_button: ctk.CTkButton
        self.issue_textbox: ctk.CTkTextbox
        self.clone_button: ctk.CTkButton
        self.link_local_button: ctk.CTkButton
        self.pull_button: ctk.CTkButton
        self.open_terminal_button: ctk.CTkButton
        # REMOVIDO: self.import_folder_button
        # REMOVIDO: self.import_file_button
        self.issue_title_entry: ctk.CTkEntry
        self.issue_body_text: ctk.CTkTextbox
        self.create_issue_button: ctk.CTkButton
        self.log_textbox: ctk.CTkTextbox  # <- ADICIONADO
        self.status_bar: ctk.CTkLabel

        # Configurar UI
        self._setup_layout()
        self.setup_ui()
        self.check_git_config()

    # ---------------------------------
    # --- Funções de Configuração da UI ---
    # ---------------------------------

    def _setup_layout(self) -> None:
        """Configura o layout grid principal da aplicação."""
        self.grid_columnconfigure(0, weight=1)
        # ALTERADO: Coluna central mais larga
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)

    def setup_ui(self) -> None:
        """Configura toda a interface do usuário chamando helpers."""
        self._create_config_column(0)
        self._create_repo_list_column(1)
        self._create_actions_column(2)
        self._create_status_bar()

    def _create_config_column(self, col: int) -> None:
        """Cria a coluna da esquerda (Configuração e Criação)."""
        config_frame = ctk.CTkFrame(self)
        config_frame.grid(row=0, column=col, rowspan=2,
                          padx=10, pady=10, sticky="nswe")
        
        # Faz com que o log_frame (último item) expanda
        config_frame.grid_rowconfigure(3, weight=1) 

        # Frame de Autenticação
        auth_frame = ctk.CTkFrame(config_frame)
        auth_frame.pack(fill="x", padx=10, pady=10)
        # ALTERADO: Título da secção
        ctk.CTkLabel(auth_frame, text="🔐 Conexão com GitHub", font=self.FONT_BOLD).pack(
            anchor="w", padx=5)
        self.token_entry = ctk.CTkEntry(
            auth_frame, width=200, show="*", placeholder_text="ghp_...")
        self.token_entry.pack(fill="x", padx=5, pady=(0, 5))
        self.connect_button = ctk.CTkButton(
            auth_frame, text="Conectar e Carregar Repositórios", command=self.start_connect_and_load,
            fg_color=self.COLOR_SUCCESS, hover_color=self.COLOR_SUCCESS_HOVER
        )
        self.connect_button.pack(fill="x", padx=5, pady=5)

        # Frame de Configuração Git
        git_config_frame = ctk.CTkFrame(config_frame)
        git_config_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(git_config_frame, text="⚙️ Configuração Git",
                     font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.git_name_entry = ctk.CTkEntry(
            git_config_frame, placeholder_text="Seu Nome")
        self.git_name_entry.pack(fill="x", padx=5, pady=2)
        self.git_email_entry = ctk.CTkEntry(
            git_config_frame, placeholder_text="seu@email.com")
        self.git_email_entry.pack(fill="x", padx=5, pady=2)
        self.save_git_config_button = ctk.CTkButton(
            git_config_frame, text="Salvar Configuração Git", command=self.save_git_config, height=30
        )
        self.save_git_config_button.pack(fill="x", padx=5, pady=5)

        # Frame de Criar Repositório
        create_repo_frame = ctk.CTkFrame(config_frame)
        create_repo_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(create_repo_frame, text="➕ Criar Novo Repositório",
                     font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.repo_name_entry = ctk.CTkEntry(
            create_repo_frame, placeholder_text="Nome do Repositório")
        self.repo_name_entry.pack(fill="x", padx=5, pady=2)
        self.repo_desc_entry = ctk.CTkEntry(
            create_repo_frame, placeholder_text="Descrição (opcional)")
        self.repo_desc_entry.pack(fill="x", padx=5, pady=2)
        
        privacy_frame = ctk.CTkFrame(create_repo_frame, fg_color="transparent")
        privacy_frame.pack(fill="x", padx=5, pady=2)
        self.private_var = ctk.BooleanVar(value=False)
        self.private_checkbox = ctk.CTkCheckBox(
            privacy_frame, text="Repositório Privado", variable=self.private_var)
        self.private_checkbox.pack(side="left", padx=5)

        # ADICIONADO: Checkbox de README
        self.readme_var = ctk.BooleanVar(value=True)  # Começa marcado
        self.readme_checkbox = ctk.CTkCheckBox(
            privacy_frame, text="Adicionar README", variable=self.readme_var)
        self.readme_checkbox.pack(side="left", padx=5)

        self.create_repo_button = ctk.CTkButton(
            create_repo_frame, text="Criar Repositório", command=self.start_create_repo,
            fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_PRIMARY_HOVER
        )
        self.create_repo_button.pack(fill="x", padx=5, pady=5)

        # ADICIONADO: Frame do Log de Atividades
        log_frame = ctk.CTkFrame(config_frame)
        # fill e expand para ocupar o espaço restante
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(log_frame, text="📜 Log de Atividades",
                     font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.log_textbox = ctk.CTkTextbox(
            log_frame, state="disabled", font=self.FONT_LISTBOX)
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)


    def _create_repo_list_column(self, col: int) -> None:
        """Cria a coluna central (Repositórios e Issues)."""
        # Lista de Repositórios
        repo_list_frame = ctk.CTkFrame(self)
        repo_list_frame.grid(row=0, column=col, padx=(
            0, 10), pady=10, sticky="nswe")
        repo_header = ctk.CTkFrame(repo_list_frame, fg_color="transparent")
        repo_header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(repo_header, text="📁 Meus Repositórios",
                     font=self.FONT_BOLD).pack(side="left")
        self.refresh_repos_button = ctk.CTkButton(
            repo_header, text="🔄", width=40, command=self.start_connect_and_load
        )
        self.refresh_repos_button.pack(side="right")
        self.search_entry = ctk.CTkEntry(
            repo_list_frame, placeholder_text="🔍 Buscar repositório...")
        self.search_entry.pack(fill="x", padx=10, pady=5)
        self.search_entry.bind("<KeyRelease>", self.filter_repositories)
        self.repo_listbox = Listbox(
            repo_list_frame, bg="#2B2B2B", fg="white", selectbackground="#1F6AA5",
            borderwidth=0, highlightthickness=0, font=self.FONT_LISTBOX
        )
        self.repo_listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.repo_listbox.bind("<<ListboxSelect>>", self.on_repo_select)

        repo_actions = ctk.CTkFrame(repo_list_frame, fg_color="transparent")
        repo_actions.pack(fill="x", padx=10, pady=5)
        self.delete_repo_button = ctk.CTkButton(
            repo_actions, text="🗑️ Excluir", command=self.start_delete_repo,
            fg_color=self.COLOR_DANGER, hover_color=self.COLOR_DANGER_HOVER, width=100
        )
        self.delete_repo_button.pack(side="left", padx=2)
        self.open_browser_button = ctk.CTkButton(
            repo_actions, text="🌐 Abrir", command=self.start_open_repo_in_browser, width=100
        )
        self.open_browser_button.pack(side="left", padx=2)
        # --- Botão do Gráfico ---
        self.plot_button = ctk.CTkButton(
            repo_actions, text="📊 Gráfico", command=self.start_generate_plot, width=100
        )
        self.plot_button.pack(side="left", padx=2)

        # Lista de Issues
        issue_list_frame = ctk.CTkFrame(self)
        issue_list_frame.grid(row=1, column=col, padx=(
            0, 10), pady=(0, 10), sticky="nswe")
        ctk.CTkLabel(issue_list_frame, text="📋 Tarefas (Issues)",
                     font=self.FONT_BOLD).pack(anchor="w", padx=10, pady=5)
        self.issue_textbox = ctk.CTkTextbox(
            issue_list_frame, state="disabled", font=self.FONT_LISTBOX)
        self.issue_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _create_actions_column(self, col: int) -> None:
        """Cria a coluna da direita (Ações e Operações)."""
        actions_frame = ctk.CTkFrame(self)
        actions_frame.grid(row=0, column=col, rowspan=2,
                           padx=(0, 10), pady=10, sticky="nswe")

        # Operações Locais
        local_frame = ctk.CTkFrame(actions_frame)
        local_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(local_frame, text="💻 Repositório Local",
                     font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.clone_button = ctk.CTkButton(
            local_frame, text="⬇️ Clonar Repositório", command=self.start_clone_repo,
            fg_color=self.COLOR_SECONDARY, hover_color=self.COLOR_SECONDARY_HOVER
        )
        self.clone_button.pack(fill="x", padx=5, pady=2)

        # ALTERADO: Botão de Pull (antigo link_local_button)
        self.link_local_button = ctk.CTkButton(
            local_frame, text="⬇️ Pull (Atualizar Local)", command=self.start_pull_repo,
            fg_color=self.COLOR_INFO, hover_color=self.COLOR_INFO_HOVER
        )
        self.link_local_button.pack(fill="x", padx=5, pady=2)

        # ALTERADO: Botão de Push (antigo pull_button)
        self.pull_button = ctk.CTkButton(
            local_frame, text="⬆️ Push (Enviar Local)", command=self.start_link_local_repo
        )
        self.pull_button.pack(fill="x", padx=5, pady=2)

        self.open_terminal_button = ctk.CTkButton(
            local_frame, text=" BTerminal", command=self.open_terminal
        )
        self.open_terminal_button.pack(
            fill="x", padx=5, pady=(10, 2))  # Espaço extra acima

        # REMOVIDO: Frame "Importar do Computador"

        # Criar Issue
        create_issue_frame = ctk.CTkFrame(actions_frame)
        create_issue_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(create_issue_frame, text="✏️ Criar Nova Tarefa",
                     font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.issue_title_entry = ctk.CTkEntry(
            create_issue_frame, placeholder_text="Título da Tarefa")
        self.issue_title_entry.pack(fill="x", padx=5, pady=2)
        self.issue_body_text = ctk.CTkTextbox(create_issue_frame, height=100)
        self.issue_body_text.pack(fill="x", padx=5, pady=2)
        self.create_issue_button = ctk.CTkButton(
            create_issue_frame, text="Criar Tarefa", command=self.start_create_issue,
            fg_color=self.COLOR_SUCCESS, hover_color=self.COLOR_SUCCESS_HOVER
        )
        self.create_issue_button.pack(fill="x", padx=5, pady=5)

    def _create_status_bar(self) -> None:
        """Cria a barra de status inferior."""
        self.status_bar = ctk.CTkLabel(
            self, text="", height=30,  # ALTERADO: Começa vazio
            fg_color="#1e1e1e", corner_radius=0
        )
        self.status_bar.grid(row=2, column=0, columnspan=3,
                             padx=0, pady=0, sticky="we")

        # ADICIONADO: Define o status inicial usando a nova função
        self.set_status("✓ Pronto. Insira seu token e conecte.")

    # ---------------------------------
    # --- Métodos Auxiliares e Lógica ---
    # ---------------------------------

    def set_status(self, message: str, color: Optional[str] = None) -> None:
        """Atualiza a barra de status E o log de atividades (UI thread)."""
        # 1. Atualiza a barra de status inferior
        self.status_bar.configure(text=message)

        # 2. Prepara a mensagem do log com timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        # 3. Adiciona ao Log de Atividades
        try:
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", log_message)
            self.log_textbox.see("end")  # Rola para o final
            self.log_textbox.configure(state="disabled")
        except Exception as e:
            print(f"Erro ao atualizar o log: {e}")  # Segurança

    def run_in_thread(self, target_func: Any, *args: Any) -> None:
        """Executa uma função em uma thread separada para não travar a UI."""
        threading.Thread(target=target_func, args=args, daemon=True).start()

    def check_git_config(self) -> None:
        """Verifica e pré-preenche as configurações globais do Git."""
        name, email = check_git_credentials()
        if name:
            self.git_name_entry.insert(0, name)
        if email:
            self.git_email_entry.insert(0, email)

    def filter_repositories(self, event: Optional[Any] = None) -> None:
        """Filtra a lista de repositórios baseada no campo de busca."""
        search_term = self.search_entry.get().lower()
        self.repo_listbox.delete(0, "end")

        # Recarrega a lista baseada no mapa filtrado
        for repo_name in sorted(self.repo_map.keys()):
            if search_term in repo_name.lower():
                self.repo_listbox.insert("end", repo_name)

        # Atualiza a exibição do repositório selecionado
        self.update_selected_repo()

    def _get_selected_repo(self) -> Optional[GitHubRepository]:
        """
        Retorna o objeto do repositório selecionado.
        Mostra um erro e retorna None se nada estiver selecionado.
        """
        if not self.current_repo_object:
            messagebox.showerror("Erro", "Nenhum repositório selecionado.")
            return None
        return self.current_repo_object

    def update_selected_repo(self) -> None:
        """
        Atualiza o `current_repo_object` com base na seleção atual da listbox.
        Chamado após filtrar ou recarregar a lista.
        """
        selected_indices = self.repo_listbox.curselection()
        if selected_indices:
            repo_name = self.repo_listbox.get(selected_indices[0])
            self.current_repo_object = self.repo_map.get(repo_name)
        else:
            self.current_repo_object = None

    # ---------------------------------
    # --- Funções de Ação (Git/GitHub) ---
    # ---------------------------------

    # --- Configuração Git ---
    def save_git_config(self) -> None:
        """Salva a configuração global do Git (user.name e user.email)."""
        name = self.git_name_entry.get().strip()
        email = self.git_email_entry.get().strip()

        if not name or not email:
            messagebox.showerror("Erro", "Nome e email são obrigatórios.")
            return

        try:
            startupinfo = _get_startup_info()
            subprocess.run(["git", "config", "--global",
                           "user.name", name], check=True, startupinfo=startupinfo)
            subprocess.run(["git", "config", "--global",
                           "user.email", email], check=True, startupinfo=startupinfo)

            messagebox.showinfo("Sucesso", "Configuração Git salva com sucesso!")
            self.set_status(f"✓ Git configurado: {name} <{email}>")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao configurar Git: {e}")

    # --- Conectar e Carregar Repos ---
    def start_connect_and_load(self) -> None:
        """(UI Thread) Inicia a conexão com o GitHub."""
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showerror(
                "Erro", "Por favor, insira um Token (PAT) válido.")
            return
        self.set_status("🔄 Conectando ao GitHub...")
        self.connect_button.configure(state="disabled")
        self.run_in_thread(self.connect_and_load, token)

    def connect_and_load(self, token: str) -> None:
        """(Worker Thread) Conecta à API e carrega os repositórios."""
        try:
            self.github_api = Github(token)
            self.github_user = self.github_api.get_user()  # type: ignore

            if not self.github_user:
                raise GithubException(
                    status=401, data={"message": "Não foi possível obter o utilizador autenticado."})

            login = self.github_user.login
            self.after(
                0, self.set_status, f"✓ Conectado como: {login}. Carregando repositórios...")

            repos = list(self.github_user.get_repos(sort="updated"))
            self.after(0, self.update_repo_list, repos)

        except GithubException as e:
            self.after(
                0, lambda: messagebox.showerror("Erro", f"Falha na API do GitHub: {str(e)}"))
            self.after(0, self.set_status, "✗ Erro de conexão.")
            self.github_user = None  # Reset user on failure
            self.github_api = None  # Reset API on failure
        except Exception as e:  # type: ignore
            self.after(
                0, lambda: messagebox.showerror("Erro", f"Erro inesperado: {e}"))
            self.after(0, self.set_status, "✗ Erro de conexão.")
        finally:
            self.after(
                0, lambda: self.connect_button.configure(state="normal"))


    # funcao grafico
    # --- Gerar Gráfico de Atividade ---

    def start_generate_plot(self) -> None:
        """(UI Thread) Inicia a geração do gráfico de atividade."""
        if not self.github_user:
            messagebox.showerror("Erro", "Não conectado. Conecte-se primeiro.")
            return
            
        # Pega os repositórios que já carregámos
        repos = list(self.repo_map.values())
        if not repos:
            messagebox.showinfo("Gráfico", "Nenhum repositório carregado para analisar.")
            return
            
        self.set_status("📊 Gerando gráfico de atividade...")
        self.plot_button.configure(state="disabled")
        # Passa a lista de repos para a thread
        self.run_in_thread(self.generate_plot, repos)

    def generate_plot(self, repos: List[Repository]) -> None:
        """(Worker Thread) Processa os dados com Pandas e mostra o gráfico com Matplotlib."""
        try:
            # 1. Extrair dados
            data = []
            for repo in repos:
                data.append([repo.name, repo.created_at])

            # 2. Processar com Pandas
            df = pd.DataFrame(data, columns=['Nome', 'DataCriacao'])
            # Converte as datas (que são texto) para objetos datetime
            df['DataCriacao'] = pd.to_datetime(df['DataCriacao'])
            
            # Agrupa os repositórios por Mês e conta quantos há
            # 'M' significa 'Month' (Mês)
            repos_por_mes = df.set_index('DataCriacao').resample('M').size()
            
            # Remove meses sem criação para um gráfico mais limpo
            repos_por_mes = repos_por_mes[repos_por_mes > 0]

            if repos_por_mes.empty:
                 self.after(0, messagebox.showinfo, "Gráfico", "Nenhum dado de criação de repositório encontrado.")
                 return

            # 3. Criar Gráfico com Matplotlib
            plt.figure(figsize=(10, 6)) # Define o tamanho da janela do gráfico
            
            # Cria um gráfico de barras
            repos_por_mes.plot(kind='bar', color=self.COLOR_INFO) 
            
            plt.title('Criação de Repositórios ao Longo do Tempo')
            plt.ylabel('Nº de Repositórios Criados')
            plt.xlabel('Mês')
            
            # Formata as datas no eixo X para serem legíveis (ex: 2023-01)
            # Isto requer que o índice seja do tipo datetime
            ax = plt.gca() # type: ignore
            ax.set_xticklabels(repos_por_mes.index.strftime('%Y-%m'), rotation=45, ha='right') # type: ignore

            plt.tight_layout() # Ajusta o gráfico para caber na janela
            
            # Mostra o gráfico numa nova janela
            # (Nota: É possível embutir no app, mas é muito mais complexo)
            plt.show()

            self.after(0, self.set_status, "✓ Gráfico gerado com sucesso.")

        except Exception as e:
            self.after(0, messagebox.showerror, "Erro no Gráfico", f"Erro ao gerar gráfico: {e}")
            self.after(0, self.set_status, "✗ Erro ao gerar gráfico.")
        finally:
            self.after(0, lambda: self.plot_button.configure(state="normal"))
            
    # --- Atualizar Lista de Repositórios ---
    def update_repo_list(self, repos: List[Repository]) -> None:
        """(UI Thread) Atualiza a Listbox com os repositórios."""
        self.repo_listbox.delete(0, "end")
        self.repo_map.clear()

        for repo in repos:
            self.repo_listbox.insert("end", repo.name)
            self.repo_map[repo.name] = repo

        self.set_status(f"✓ {len(repos)} repositórios carregados.")
        self.filter_repositories()  # Aplica filtro de busca se houver

    # --- Criar Repositório ---
    def start_create_repo(self) -> None:
        """(UI Thread) Inicia a criação de um novo repositório."""
        repo_name = self.repo_name_entry.get().strip()
        if not repo_name:
            messagebox.showerror(
                "Erro", "O nome do repositório é obrigatório.")
            return

        if not self.github_user:
            messagebox.showerror("Erro", "Não conectado. Conecte-se primeiro.")
            return

        self.set_status(f"🔄 Criando '{repo_name}'...")
        self.create_repo_button.configure(state="disabled")

        description = self.repo_desc_entry.get().strip()
        is_private = self.private_var.get()
        add_readme = self.readme_var.get()  # <- ADICIONADO

        # <- ADICIONADO add_readme
        self.run_in_thread(self.create_repo, repo_name,
                           description, is_private, add_readme, self.github_user)

    # <- ADICIONADO add_readme
    def create_repo(self, name: str, description: str, is_private: bool, add_readme: bool, user: AuthenticatedUser) -> None:  # type: ignore
        """(Worker Thread) Cria o novo repositório no GitHub."""
        try:
            user.create_repo(
                name=name,
                description=description if description else NotSet,
                private=is_private,
                auto_init=add_readme  # <- ADICIONADO
            )

            self.after(
                0, self.set_status, f"✓ Repositório '{name}' criado com sucesso!")
            self.after(0, self.repo_name_entry.delete, 0, "end")
            self.after(0, self.repo_desc_entry.delete, 0, "end")
            self.after(
                0, messagebox.showinfo, "Sucesso", f"Repositório '{name}' criado!")

            # Recarrega repositórios
            self.after(1000, self.start_connect_and_load)

        except GithubException as e:
            self.after(0, messagebox.showerror,
                       "Erro", f"Falha ao criar repositório: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao criar repositório.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
            self.after(0, self.set_status, "✗ Erro ao criar repositório.")
        finally:
            self.after(
                0, lambda: self.create_repo_button.configure(state="normal"))

    # --- Deletar Repositório ---
    def start_delete_repo(self) -> None:
        """(UI Thread) Inicia a exclusão de um repositório."""
        repo = self._get_selected_repo()
        if not repo:
            return

        confirm = messagebox.askyesno(
            "Confirmar Exclusão",
            f"Tem certeza que deseja excluir o repositório '{repo.name}'?\n\n"
            "Esta ação é IRREVERSÍVEL!"
        )

        if confirm:
            self.set_status(f"🗑️ Excluindo '{repo.name}'...")
            self.run_in_thread(self.delete_repo, repo)

    def delete_repo(self, repo: GitHubRepository) -> None:
        """(Worker Thread) Exclui o repositório do GitHub."""
        try:
            repo_name = repo.name
            repo.delete()
            self.after(
                0, self.set_status, f"✓ Repositório '{repo_name}' excluído.")
            self.after(
                0, messagebox.showinfo, "Sucesso", f"Repositório '{repo_name}' excluído!")

            # Limpa a seleção atual se for o repo excluído
            if self.current_repo_object == repo:
                self.current_repo_object = None

            self.after(1000, self.start_connect_and_load)

        except GithubException as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Falha ao excluir: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao excluir repositório.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")

    # --- Abrir no Navegador ---
    def start_open_repo_in_browser(self) -> None:
        """(UI Thread) Abre o repositório no navegador."""
        repo = self._get_selected_repo()
        if not repo:
            return

        webbrowser.open_new(repo.html_url)
        self.set_status(f"🌐 Abrindo '{repo.name}' no navegador...")

    # --- Lógica das Issues ---
    def on_repo_select(self, event: Optional[Any] = None) -> None:
        """(UI Thread) Chamado quando um repositório é selecionado na lista."""
        selected_indices = self.repo_listbox.curselection()
        if not selected_indices:
            return

        repo_name = self.repo_listbox.get(selected_indices[0])
        self.current_repo_object = self.repo_map.get(repo_name)

        if self.current_repo_object:
            self.set_status(f"📋 Carregando tarefas de '{repo_name}'...")
            self.update_issue_list([])  # Limpa a caixa de issues
            self.run_in_thread(self.get_issues, self.current_repo_object)

    def get_issues(self, repo: GitHubRepository) -> None:
        """(Worker Thread) Carrega as issues do repositório selecionado."""
        try:
            issues = list(repo.get_issues(state="open"))
            self.after(0, self.update_issue_list, issues)
        except GithubException as e:
            self.after(0, messagebox.showerror,
                       "Erro", f"Não foi possível carregar as Issues: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao carregar issues.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
            self.after(0, self.set_status, "✗ Erro ao carregar issues.")

    def update_issue_list(self, issues: List[Any]) -> None:
        """(UI Thread) Atualiza a Textbox com a lista de issues."""
        self.issue_textbox.configure(state="normal")
        self.issue_textbox.delete("1.0", "end")

        if not issues:
            self.issue_textbox.insert("end", "Nenhuma tarefa aberta encontrada.\n")
        else:
            for issue in issues:
                text = f"#{issue.number} - {issue.title}\n"
                text += f"  Por: {issue.user.login} | Criado: {issue.created_at.strftime('%d/%m/%Y')}\n"
                if issue.labels:
                    labels = ", ".join([l.name for l in issue.labels])
                    text += f"  Labels: {labels}\n"
                text += "  " + "-" * 60 + "\n\n"
                self.issue_textbox.insert("end", text)

        self.issue_textbox.configure(state="disabled")

        if self.current_repo_object:
            self.set_status(
                f"✓ {len(issues)} tarefas carregadas de '{self.current_repo_object.name}'.")

    # --- Criar Issue ---
    def start_create_issue(self) -> None:
        """(UI Thread) Inicia a criação de uma nova issue."""
        repo = self._get_selected_repo()
        if not repo:
            return

        title = self.issue_title_entry.get().strip()
        if not title:
            messagebox.showerror("Erro", "O Título da tarefa é obrigatório.")
            return

        body = self.issue_body_text.get("1.0", "end-1c").strip()

        self.set_status(f"✏️ Criando tarefa '{title}'...")
        self.create_issue_button.configure(state="disabled")
        self.run_in_thread(self.create_issue, repo, title, body)

    def create_issue(self, repo: GitHubRepository, title: str, body: str) -> None:
        """(Worker Thread) Cria a nova issue no repositório."""
        try:
            repo.create_issue(title=title, body=body if body else NotSet)
            self.after(0, self.set_status, f"✓ Tarefa '{title}' criada!")
            self.after(0, self.issue_title_entry.delete, 0, "end")
            self.after(0, self.issue_body_text.delete, "1.0", "end")
            self.after(
                0, messagebox.showinfo, "Sucesso", f"Tarefa '{title}' criada!")

            # Recarrega issues
            self.after(500, self.get_issues, repo)

        except GithubException as e:
            self.after(0, messagebox.showerror,
                       "Erro", f"Falha ao criar tarefa: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao criar tarefa.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
        finally:
            self.after(
                0, lambda: self.create_issue_button.configure(state="normal"))

    # --- Clonar Repositório ---
    def start_clone_repo(self) -> None:
        """(UI Thread) Inicia o clone de um repositório."""
        repo = self._get_selected_repo()
        if not repo:
            return

        local_path_str = filedialog.askdirectory(
            title="Selecione onde clonar o repositório")
        if not local_path_str:
            return

        self.set_status(f"⬇️ Clonando '{repo.name}'...")
        self.clone_button.configure(state="disabled")
        self.run_in_thread(self.clone_repo, repo, Path(local_path_str))

    def clone_repo(self, repo: GitHubRepository, local_path: Path) -> None:
        """(Worker Thread) Clona o repositório e pergunta se quer abrir no IDE."""
        try:
            destination = local_path / repo.name

            if destination.exists():
                self.after(
                    0, messagebox.showerror, "Erro", f"A pasta '{repo.name}' já existe em {local_path}")
                return

            self.after(
                0, self.set_status, f"⬇️ Clonando para {destination}...")
            git.Repo.clone_from(repo.clone_url, str(destination))

            self.after(
                0, self.set_status, f"✓ Repositório clonado em: {destination}")
            self.after(0, messagebox.showinfo, "Sucesso",
                       f"Repositório clonado com sucesso!\n\nLocalização: {destination}")

            # Pergunta se quer abrir no IDE
            self.after(100, self.prompt_open_ide, str(destination))

        except git.GitCommandError as e:
            self.after(
                0, messagebox.showerror, "Erro de Git", f"Falha ao clonar:\n{e}")
            self.after(0, self.set_status, "✗ Erro ao clonar repositório.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
            self.after(0, self.set_status, "✗ Erro ao clonar.")
        finally:
            self.after(
                0, lambda: self.clone_button.configure(state="normal"))

    # --- Conectar Pasta Local e Fazer Push ---
    def start_link_local_repo(self) -> None:
        """(UI Thread) Inicia a conexão de uma pasta local com um repo remoto."""
        repo = self._get_selected_repo()
        if not repo:
            return

        local_path = filedialog.askdirectory(
            title="Selecione a Pasta do Projeto Local para Enviar (Push)")
        if not local_path:
            self.set_status("Operação cancelada.")
            return

        self.current_local_path = local_path
        self.set_status(f"🔗 Conectando e enviando pasta local para '{repo.name}'...")
        # ALTERADO: Desativa o botão de Push (antigo pull_button)
        self.pull_button.configure(state="disabled")
        self.run_in_thread(self.link_local_repo, repo, local_path)

    def link_local_repo(self, repo_remote: GitHubRepository, local_path: str) -> None:
        """(Worker Thread) Conecta a pasta local ao repositório e faz push."""
        branch_name: str = "main"

        try:
            repo_local = git.Repo.init(local_path)
            origin_url = repo_remote.clone_url

            # Configura remote origin
            if "origin" in [r.name for r in repo_local.remotes]:
                origin = repo_local.remotes.origin
                origin.set_url(origin_url)
            else:
                origin = repo_local.create_remote("origin", origin_url)

            # Adiciona todos os arquivos
            self.after(
                0, self.set_status, "📝 Adicionando arquivos (git add)...")
            repo_local.git.add(all=True)

            # Commit (apenas se houver mudanças)
            if repo_local.is_dirty(untracked_files=True):
                self.after(0, self.set_status, "💾 Criando commit...")
                repo_local.index.commit("Commit via Gestor GitHub")
            else:
                self.after(
                    0, self.set_status, "ℹ️ Nenhuma mudança para commitar. Prosseguindo...")

            # Determina o branch atual
            try:
                branch_name = repo_local.active_branch.name
            except TypeError:
                # Se não houver branch (repo novo), cria 'main'
                repo_local.git.branch("-M", branch_name)

            # Push
            self.after(
                0, self.set_status, f"⬆️ Enviando branch '{branch_name}' para o GitHub...")
            repo_local.git.push("--set-upstream", "origin", branch_name)

            self.after(
                0, self.set_status, "✓ Sucesso! Pasta local conectada e enviada.")
            self.after(0, messagebox.showinfo, "Sucesso",
                       "Seus arquivos foram enviados para o GitHub com sucesso!")

        except git.GitCommandError as e:
            # Tenta lidar com o erro comum 'main' vs 'master'
            if "src refspec main does not match any" in str(e) and branch_name == "main":
                self.after(
                    0, self.set_status, "ℹ️ 'main' falhou, tentando 'master'...")
                repo_local = git.Repo(local_path)
                repo_local.git.branch("-M", "master")
                repo_local.git.push("--set-upstream", "origin", "master")
                self.after(
                    0, self.set_status, "✓ Sucesso! Pasta local conectada e enviada.")
                self.after(0, messagebox.showinfo, "Sucesso",
                           "Seus arquivos foram enviados para o GitHub com sucesso!")
            else:
                self.after(
                    0, messagebox.showerror, "Erro de Git", f"Um comando Git falhou:\n{e}")
                self.after(0, self.set_status,
                           "✗ Erro durante operação do Git.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Ocorreu um erro inesperado:\n{e}")
            self.after(0, self.set_status, "✗ Erro inesperado.")
        finally:
            # ALTERADO: Reativa o botão de Push (antigo pull_button)
            self.after(0, lambda: self.pull_button.configure(state="normal"))

    # --- Pull (Atualizar Local) ---
    def start_pull_repo(self) -> None:
        """(UI Thread) Inicia o 'pull' para um repositório local."""
        local_path = filedialog.askdirectory(
            title="Selecione o Repositório Local para Atualizar")
        if not local_path:
            return

        self.set_status("⬇️ Atualizando repositório local...")
        # ALTERADO: Desativa o botão de Pull (antigo link_local_button)
        self.link_local_button.configure(state="disabled")
        self.run_in_thread(self.pull_repo, local_path)

    def pull_repo(self, local_path: str) -> None:
        """(Worker Thread) Faz 'pull' do repositório remoto."""
        try:
            repo = git.Repo(local_path)
            if not repo.remotes:
                self.after(
                    0, messagebox.showerror, "Erro", "Nenhum remote configurado neste repositório.")
                return

            origin = repo.remotes.origin
            self.after(0, self.set_status, "⬇️ Baixando atualizações...")
            origin.pull()

            self.after(
                0, self.set_status, "✓ Repositório atualizado com sucesso!")
            self.after(0, messagebox.showinfo, "Sucesso",
                       "Repositório local atualizado com as últimas mudanças!")

        except git.GitCommandError as e:
            self.after(
                0, messagebox.showerror, "Erro de Git", f"Falha ao fazer pull:\n{e}")
            self.after(0, self.set_status, "✗ Erro ao atualizar repositório.")
        except git.InvalidGitRepositoryError:
            self.after(0, messagebox.showerror,
                       "Erro", "A pasta selecionada não é um repositório Git válido.")
            self.after(0, self.set_status, "✗ Repositório inválido.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
            self.after(0, self.set_status, "✗ Erro ao atualizar.")
        finally:
            # ALTERADO: Reativa o botão de Pull (antigo link_local_button)
            self.after(
                0, lambda: self.link_local_button.configure(state="normal"))

    # REMOVIDO: Funções de Importar (start_import_local_folder, import_local_folder, start_import_local_file, import_local_file)

    # --- Funções do Prompt de IDE ---
    def prompt_open_ide(self, path: str) -> None:
        """(UI Thread) Cria o diálogo para escolher o IDE."""
        dialog = IDEPrompt(self)
        choice = dialog.get_choice()  # Espera o utilizador escolher

        if choice:
            self.run_in_thread(self.open_in_ide, path, choice)

    def open_in_ide(self, path: str, ide_choice: str) -> None:
        """(Worker Thread) Tenta abrir a pasta do projeto no IDE escolhido."""
        self.after(0, self.set_status, f"Abrindo {path} em {ide_choice}...")

        command_str: str = ""

        try:
            command: List[str] = []
            shell_needed = True if os.name == 'nt' else False

            if ide_choice == "vscode":
                command = ["code", "."]
                command_str = "code"
            elif ide_choice == "jetbrains":
                command = ["pycharm", "."]
                command_str = "pycharm"
            elif ide_choice == "visualstudio":
                command = ["devenv", "."]
                command_str = "devenv"

            if command:
                subprocess.Popen(
                    command, cwd=path, shell=shell_needed, startupinfo=_get_startup_info())

        except FileNotFoundError:
            self.after(0, messagebox.showerror, "Erro",
                       f"Não foi possível encontrar o comando para '{command_str}'.\n"
                       f"Certifique-se de que o IDE está instalado e o seu comando ('{command_str}') está no PATH do sistema.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Falha ao abrir o IDE: {e}")

    # --- Abrir Terminal ---
    def open_terminal(self) -> None:
        """(UI Thread) Abre o terminal (Git Bash no Windows, ou padrão no Linux/macOS) no diretório local."""
        path_to_open_str = self.current_local_path

        # Se não houver um path local atual, pede ao utilizador para selecionar um
        if not path_to_open_str or not Path(path_to_open_str).is_dir():
            path_to_open_str = filedialog.askdirectory(
                title="Selecione o diretório do repositório local")
            if not path_to_open_str:
                self.set_status("Operação de terminal cancelada.")
                return

        # Atualiza o path atual
        self.current_local_path = path_to_open_str

        self.set_status(f"Abrindo terminal em: {self.current_local_path}...")
        self.run_in_thread(self._open_terminal_worker,
                           self.current_local_path)

    def _open_terminal_worker(self, path_to_open: str) -> None:
        """(Worker Thread) Lógica para abrir o terminal."""
        try:
            if os.name == 'nt':  # Windows
                git_bash_path = self.find_git_bash()  # Tenta encontrar o Git Bash
                if git_bash_path:
                    subprocess.Popen(
                        [str(git_bash_path), "--cd=" + path_to_open], startupinfo=_get_startup_info())
                    self.after(
                        0, self.set_status, f"✓ Git Bash aberto em: {path_to_open}")
                else:
                    # Fallback para cmd se Git Bash não for encontrado
                    subprocess.Popen(["cmd.exe"], cwd=path_to_open,
                                     startupinfo=_get_startup_info())
                    self.after(
                        0, self.set_status, f"✓ Prompt de Comando aberto em: {path_to_open}")
            else:  # Linux/macOS
                terminals = [
                    ["x-terminal-emulator", "-e", f"cd {path_to_open} && bash"],
                    ["gnome-terminal", "--", "bash", "-c",
                        f"cd {path_to_open}; exec bash"],
                    ["konsole", "-e", f"cd {path_to_open} && bash"],
                    ["xterm", "-e", f"cd {path_to_open} && bash"]
                ]
                opened = False
                for t in terminals:
                    try:
                        subprocess.Popen(t)
                        opened = True
                        break
                    except FileNotFoundError:
                        continue

                if opened:
                    self.after(
                        0, self.set_status, f"✓ Terminal aberto em: {path_to_open}")
                else:
                    self.after(0, messagebox.showerror,
                               "Erro", "Não foi possível abrir um terminal. Tente abrir manualmente.")
        except Exception as e:
            self.after(
                0, messagebox.showerror, "Erro", f"Falha ao abrir o terminal: {e}")
            self.after(0, self.set_status, "✗ Erro ao abrir terminal.")

    def find_git_bash(self) -> Optional[Path]:
        """Tenta encontrar o executável do Git Bash no Windows (usando Pathlib)."""
        program_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        program_files_x86 = Path(
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
        local_app_data = Path(os.environ.get("LocalAppData", ""))

        common_paths = [
            program_files / "Git" / "bin" / "bash.exe",
            program_files_x86 / "Git" / "bin" / "bash.exe",
            local_app_data / "Programs" / "Git" / "bin" / "bash.exe",
            program_files / "Git" / "git-bash.exe",
        ]
        for path in common_paths:
            if path.exists():
                return path

        git_home_str = os.environ.get("GIT_HOME")
        if git_home_str:
            git_home = Path(git_home_str)
            if (git_home / "bin" / "bash.exe").exists():
                return git_home / "bin" / "bash.exe"

        for path_dir_str in os.environ["PATH"].split(os.pathsep):
            path_dir = Path(path_dir_str)
            if "git" in path_dir_str.lower() and (path_dir / "bash.exe").exists():
                return path_dir / "bash.exe"
        return None


# Ponto de entrada da aplicação
if __name__ == "__main__":
    app = GitHubApp()
    app.mainloop()
