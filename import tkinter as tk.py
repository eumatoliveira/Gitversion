import subprocess
import webbrowser
import os
import shutil
from tkinter import messagebox, Tk, Listbox, filedialog
import sys
import threading
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any # Para type hints

# customtkinter
import customtkinter as ctk # type: ignore

# PyGithub
from github import Github, GithubException, NotSet, Repository # type: ignore
from github.AuthenticatedUser import AuthenticatedUser # type: ignore

# GitPython
import git # type: ignore  <- CORREÇÃO: Adicionado 'type: ignore'

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
        messagebox.showerror("Erro de Git", "O Git parece estar instalado, mas falhou ao executar. Tente reinstalá-lo.")
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
        self.choice: Optional[str] = None # Onde vamos guardar a escolha

        self.label = ctk.CTkLabel(self, text="Clone bem-sucedido!\nDeseja abrir a pasta em qual IDE?", font=("", 14))
        self.label.pack(pady=10, padx=10)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=10)

        self.vscode_button = ctk.CTkButton(button_frame, text="VS Code", command=lambda: self.select_ide("vscode"))
        self.vscode_button.pack(fill="x", padx=10, pady=5)

        self.jetbrains_button = ctk.CTkButton(button_frame, text="JetBrains (ex: PyCharm)", command=lambda: self.select_ide("jetbrains"))
        self.jetbrains_button.pack(fill="x", padx=10, pady=5)
        
        self.vs_button = ctk.CTkButton(button_frame, text="Visual Studio", command=lambda: self.select_ide("visualstudio"))
        self.vs_button.pack(fill="x", padx=10, pady=5)

        self.cancel_button = ctk.CTkButton(self, text="Cancelar", fg_color="gray", command=self.destroy)
        self.cancel_button.pack(pady=(0, 10))
        
        self.transient(self.master) # type: ignore
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
        self.current_repo_object: Optional[Repository.Repository] = None
        self.current_local_path: Optional[str] = None
        self.repo_map: Dict[str, Repository.Repository] = {}

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
        # MELHORIA: Adicionado o botão de terminal
        self.open_terminal_button: ctk.CTkButton 
        self.import_folder_button: ctk.CTkButton
        self.import_file_button: ctk.CTkButton
        self.issue_title_entry: ctk.CTkEntry
        self.issue_body_text: ctk.CTkTextbox
        self.create_issue_button: ctk.CTkButton
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
        self.grid_columnconfigure(1, weight=1)
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
        config_frame.grid(row=0, column=col, rowspan=2, padx=10, pady=10, sticky="nswe")

        # Frame de Autenticação
        auth_frame = ctk.CTkFrame(config_frame)
        auth_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(auth_frame, text="🔐 Token Pessoal (PAT)", font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.token_entry = ctk.CTkEntry(auth_frame, width=200, show="*", placeholder_text="ghp_...")
        self.token_entry.pack(fill="x", padx=5, pady=(0, 5))
        self.connect_button = ctk.CTkButton(
            auth_frame, text="Conectar e Carregar Repositórios", command=self.start_connect_and_load,
            fg_color=self.COLOR_SUCCESS, hover_color=self.COLOR_SUCCESS_HOVER
        )
        self.connect_button.pack(fill="x", padx=5, pady=5)

        # Frame de Configuração Git
        git_config_frame = ctk.CTkFrame(config_frame)
        git_config_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(git_config_frame, text="⚙️ Configuração Git", font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.git_name_entry = ctk.CTkEntry(git_config_frame, placeholder_text="Seu Nome")
        self.git_name_entry.pack(fill="x", padx=5, pady=2)
        self.git_email_entry = ctk.CTkEntry(git_config_frame, placeholder_text="seu@email.com")
        self.git_email_entry.pack(fill="x", padx=5, pady=2)
        self.save_git_config_button = ctk.CTkButton(
            git_config_frame, text="Salvar Configuração Git", command=self.save_git_config, height=30
        )
        self.save_git_config_button.pack(fill="x", padx=5, pady=5)

        # Frame de Criar Repositório
        create_repo_frame = ctk.CTkFrame(config_frame)
        create_repo_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(create_repo_frame, text="➕ Criar Novo Repositório", font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.repo_name_entry = ctk.CTkEntry(create_repo_frame, placeholder_text="Nome do Repositório")
        self.repo_name_entry.pack(fill="x", padx=5, pady=2)
        self.repo_desc_entry = ctk.CTkEntry(create_repo_frame, placeholder_text="Descrição (opcional)")
        self.repo_desc_entry.pack(fill="x", padx=5, pady=2)
        privacy_frame = ctk.CTkFrame(create_repo_frame, fg_color="transparent")
        privacy_frame.pack(fill="x", padx=5, pady=2)
        self.private_var = ctk.BooleanVar(value=False)
        self.private_checkbox = ctk.CTkCheckBox(privacy_frame, text="Repositório Privado", variable=self.private_var)
        self.private_checkbox.pack(side="left", padx=5)
        self.create_repo_button = ctk.CTkButton(
            create_repo_frame, text="Criar Repositório", command=self.start_create_repo,
            fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_PRIMARY_HOVER
        )
        self.create_repo_button.pack(fill="x", padx=5, pady=5)

    def _create_repo_list_column(self, col: int) -> None:
        """Cria a coluna central (Repositórios e Issues)."""
        # Lista de Repositórios
        repo_list_frame = ctk.CTkFrame(self)
        repo_list_frame.grid(row=0, column=col, padx=(0, 10), pady=10, sticky="nswe")
        repo_header = ctk.CTkFrame(repo_list_frame, fg_color="transparent")
        repo_header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(repo_header, text="📁 Meus Repositórios", font=self.FONT_BOLD).pack(side="left")
        self.refresh_repos_button = ctk.CTkButton(
            repo_header, text="🔄", width=40, command=self.start_connect_and_load
        )
        self.refresh_repos_button.pack(side="right")
        self.search_entry = ctk.CTkEntry(repo_list_frame, placeholder_text="🔍 Buscar repositório...")
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

        # Lista de Issues
        issue_list_frame = ctk.CTkFrame(self)
        issue_list_frame.grid(row=1, column=col, padx=(0, 10), pady=(0, 10), sticky="nswe")
        ctk.CTkLabel(issue_list_frame, text="📋 Tarefas (Issues)", font=self.FONT_BOLD).pack(anchor="w", padx=10, pady=5)
        self.issue_textbox = ctk.CTkTextbox(issue_list_frame, state="disabled", font=self.FONT_LISTBOX)
        self.issue_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _create_actions_column(self, col: int) -> None:
        """Cria a coluna da direita (Ações e Operações)."""
        actions_frame = ctk.CTkFrame(self)
        actions_frame.grid(row=0, column=col, rowspan=2, padx=(0, 10), pady=10, sticky="nswe")

        # Operações Locais
        local_frame = ctk.CTkFrame(actions_frame)
        local_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(local_frame, text="💻 Repositório Local", font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.clone_button = ctk.CTkButton(
            local_frame, text="⬇️ Clonar Repositório", command=self.start_clone_repo,
            fg_color=self.COLOR_SECONDARY, hover_color=self.COLOR_SECONDARY_HOVER
        )
        self.clone_button.pack(fill="x", padx=5, pady=2)
        self.link_local_button = ctk.CTkButton(
            local_frame, text="🔗 Conectar Pasta e Fazer Push", command=self.start_link_local_repo,
            fg_color=self.COLOR_INFO, hover_color=self.COLOR_INFO_HOVER
        )
        self.link_local_button.pack(fill="x", padx=5, pady=2)
        self.pull_button = ctk.CTkButton(
            local_frame, text="⬇️ Pull (Atualizar Local)", command=self.start_pull_repo
        )
        self.pull_button.pack(fill="x", padx=5, pady=2)
        
        # MELHORIA: Adicionado botão para chamar a função open_terminal
        self.open_terminal_button = ctk.CTkButton(
            local_frame, text=" BTerminal", command=self.open_terminal
        )
        self.open_terminal_button.pack(fill="x", padx=5, pady=(10, 2)) # Espaço extra acima

        # Importar do Computador
        import_frame = ctk.CTkFrame(actions_frame)
        import_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(import_frame, text="📤 Importar do Computador", font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.import_folder_button = ctk.CTkButton(
            import_frame, text="📁 Importar Pasta", command=self.start_import_local_folder
        )
        self.import_folder_button.pack(fill="x", padx=5, pady=2)
        self.import_file_button = ctk.CTkButton(
            import_frame, text="📄 Importar Arquivo", command=self.start_import_local_file
        )
        self.import_file_button.pack(fill="x", padx=5, pady=2)

        # Criar Issue
        create_issue_frame = ctk.CTkFrame(actions_frame)
        create_issue_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(create_issue_frame, text="✏️ Criar Nova Tarefa", font=self.FONT_BOLD).pack(anchor="w", padx=5)
        self.issue_title_entry = ctk.CTkEntry(create_issue_frame, placeholder_text="Título da Tarefa")
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
            self, text="✓ Pronto. Insira seu token e conecte.", height=30,
            fg_color="#1e1e1e", corner_radius=0
        )
        self.status_bar.grid(row=2, column=0, columnspan=3, padx=0, pady=0, sticky="we")

    # ---------------------------------
    # --- Métodos Auxiliares e Lógica ---
    # ---------------------------------

    def set_status(self, message: str, color: Optional[str] = None) -> None:
        """Atualiza a barra de status (UI thread)."""
        self.status_bar.configure(text=message)

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

    def _get_selected_repo(self) -> Optional[Repository.Repository]:
        """
        Retorna o objeto do repositório selecionado.
        Mostra um erro e retorna None se nada estiver selecionado.
        """
        if not self.current_repo_object:
            messagebox.showerror("Erro", "Nenhum repositório selecionado.")
            return None
        return self.current_repo_object

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
            subprocess.run(["git", "config", "--global", "user.name", name], check=True, startupinfo=startupinfo)
            subprocess.run(["git", "config", "--global", "user.email", email], check=True, startupinfo=startupinfo)
            
            messagebox.showinfo("Sucesso", "Configuração Git salva com sucesso!")
            self.set_status(f"✓ Git configurado: {name} <{email}>")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao configurar Git: {e}")

    # --- Conectar e Carregar Repos ---
    def start_connect_and_load(self) -> None:
        """(UI Thread) Inicia a conexão com o GitHub."""
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showerror("Erro", "Por favor, insira um Token (PAT) válido.")
            return
        self.set_status("🔄 Conectando ao GitHub...")
        self.connect_button.configure(state="disabled")
        self.run_in_thread(self.connect_and_load, token)

    def connect_and_load(self, token: str) -> None:
        """(Worker Thread) Conecta à API e carrega os repositórios."""
        try:
            self.github_api = Github(token)
            # Força a chamada para verificar a autenticação e obter o usuário
            # A anotação 'type: ignore' é usada aqui porque PyGithub pode retornar NotSet,
            # mas a lógica subsequente garante que self.github_user será um AuthenticatedUser ou None.
            self.github_user = self.github_api.get_user() # type: ignore
            
            # CORREÇÃO: Adiciona verificação para satisfazer o linter e garantir que github_user não é None
            if not self.github_user:
                raise GithubException(status=401, data={"message": "Não foi possível obter o utilizador autenticado."})
                
            login = self.github_user.login
            self.after(0, self.set_status, f"✓ Conectado como: {login}. Carregando repositórios...")
            
            repos = list(self.github_user.get_repos(sort="updated"))
            self.after(0, self.update_repo_list, repos)

        except GithubException as e:
            self.after(0, lambda: messagebox.showerror("Erro", f"Falha na API do GitHub: {str(e)}"))
            self.after(0, self.set_status, "✗ Erro de conexão.")
            self.github_user = None # Reset user on failure
            self.github_api = None # Reset API on failure
        except Exception as e: # type: ignore
            self.after(0, lambda: messagebox.showerror("Erro", f"Erro inesperado: {e}"))
            self.after(0, self.set_status, "✗ Erro de conexão.")
        finally:
            self.after(0, lambda: self.connect_button.configure(state="normal"))

    def update_repo_list(self, repos: List[Repository.Repository]) -> None:
        """(UI Thread) Atualiza a Listbox com os repositórios."""
        self.repo_listbox.delete(0, "end")
        self.repo_map.clear()
        
        for repo in repos:
            self.repo_listbox.insert("end", repo.name)
            self.repo_map[repo.name] = repo
        
        self.set_status(f"✓ {len(repos)} repositórios carregados.")
        self.filter_repositories() # Aplica filtro de busca se houver

    # --- Criar Repositório ---
    def start_create_repo(self) -> None:
        """(UI Thread) Inicia a criação de um novo repositório."""
        repo_name = self.repo_name_entry.get().strip()
        if not repo_name:
            messagebox.showerror("Erro", "O nome do repositório é obrigatório.")
            return
        
        # CORREÇÃO: Verificação de 'None' mais robusta
        if not self.github_user:
            messagebox.showerror("Erro", "Não conectado. Conecte-se primeiro.")
            return
            
        self.set_status(f"🔄 Criando '{repo_name}'...")
        self.create_repo_button.configure(state="disabled")
        
        description = self.repo_desc_entry.get().strip()
        is_private = self.private_var.get()
        
        self.run_in_thread(self.create_repo, repo_name, description, is_private, self.github_user)

    def create_repo(self, name: str, description: str, is_private: bool, user: AuthenticatedUser) -> None:
        """(Worker Thread) Cria o novo repositório no GitHub."""
        try:
            user.create_repo(
                name=name,
                description=description if description else NotSet,
                private=is_private
            )
            
            self.after(0, self.set_status, f"✓ Repositório '{name}' criado com sucesso!")
            self.after(0, self.repo_name_entry.delete, 0, "end")
            self.after(0, self.repo_desc_entry.delete, 0, "end")
            self.after(0, messagebox.showinfo, "Sucesso", f"Repositório '{name}' criado!")
            
            # Recarrega repositórios
            self.after(1000, self.start_connect_and_load)
            
        except GithubException as e:
            self.after(0, messagebox.showerror, "Erro", f"Falha ao criar repositório: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao criar repositório.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
            self.after(0, self.set_status, "✗ Erro ao criar repositório.")
        finally:
            self.after(0, lambda: self.create_repo_button.configure(state="normal"))

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

    def delete_repo(self, repo: Repository.Repository) -> None:
        """(Worker Thread) Exclui o repositório do GitHub."""
        try:
            repo_name = repo.name
            repo.delete()
            self.after(0, self.set_status, f"✓ Repositório '{repo_name}' excluído.")
            self.after(0, messagebox.showinfo, "Sucesso", f"Repositório '{repo_name}' excluído!")
            
            # Limpa a seleção atual se for o repo excluído
            if self.current_repo_object == repo:
                self.current_repo_object = None
            
            self.after(1000, self.start_connect_and_load)
            
        except GithubException as e:
            self.after(0, messagebox.showerror, "Erro", f"Falha ao excluir: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao excluir repositório.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")

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

    def get_issues(self, repo: Repository.Repository) -> None:
        """(Worker Thread) Carrega as issues do repositório selecionado."""
        try:
            issues = list(repo.get_issues(state="open"))
            self.after(0, self.update_issue_list, issues)
        except GithubException as e:
            self.after(0, messagebox.showerror, "Erro", f"Não foi possível carregar as Issues: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao carregar issues.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
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
                text += f"   Por: {issue.user.login} | Criado: {issue.created_at.strftime('%d/%m/%Y')}\n"
                if issue.labels:
                    labels = ", ".join([l.name for l in issue.labels])
                    text += f"   Labels: {labels}\n"
                text += "   " + "-" * 60 + "\n\n"
                self.issue_textbox.insert("end", text)
        
        self.issue_textbox.configure(state="disabled")
        
        if self.current_repo_object:
            self.set_status(f"✓ {len(issues)} tarefas carregadas de '{self.current_repo_object.name}'.")

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

    def create_issue(self, repo: Repository.Repository, title: str, body: str) -> None:
        """(Worker Thread) Cria a nova issue no repositório."""
        try:
            repo.create_issue(title=title, body=body if body else NotSet)
            self.after(0, self.set_status, f"✓ Tarefa '{title}' criada!")
            self.after(0, self.issue_title_entry.delete, 0, "end")
            self.after(0, self.issue_body_text.delete, "1.0", "end")
            self.after(0, messagebox.showinfo, "Sucesso", f"Tarefa '{title}' criada!")
            
            # Recarrega issues
            self.after(500, self.get_issues, repo)
            
        except GithubException as e:
            self.after(0, messagebox.showerror, "Erro", f"Falha ao criar tarefa: {str(e)}")
            self.after(0, self.set_status, "✗ Erro ao criar tarefa.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
        finally:
            self.after(0, lambda: self.create_issue_button.configure(state="normal"))

    # --- Clonar Repositório ---
    def start_clone_repo(self) -> None:
        """(UI Thread) Inicia o clone de um repositório."""
        repo = self._get_selected_repo()
        if not repo:
            return
        
        local_path_str = filedialog.askdirectory(title="Selecione onde clonar o repositório")
        if not local_path_str:
            return
        
        self.set_status(f"⬇️ Clonando '{repo.name}'...")
        self.clone_button.configure(state="disabled")
        self.run_in_thread(self.clone_repo, repo, Path(local_path_str))

    def clone_repo(self, repo: Repository.Repository, local_path: Path) -> None:
        """(Worker Thread) Clona o repositório e pergunta se quer abrir no IDE."""
        try:
            destination = local_path / repo.name
            
            if destination.exists():
                self.after(0, messagebox.showerror, "Erro", f"A pasta '{repo.name}' já existe em {local_path}")
                return
            
            self.after(0, self.set_status, f"⬇️ Clonando para {destination}...")
            git.Repo.clone_from(repo.clone_url, str(destination))
            
            self.after(0, self.set_status, f"✓ Repositório clonado em: {destination}")
            self.after(0, messagebox.showinfo, "Sucesso", f"Repositório clonado com sucesso!\n\nLocalização: {destination}")
            
            # Pergunta se quer abrir no IDE
            self.after(100, self.prompt_open_ide, str(destination))
            
        except git.GitCommandError as e:
            self.after(0, messagebox.showerror, "Erro de Git", f"Falha ao clonar:\n{e}")
            self.after(0, self.set_status, "✗ Erro ao clonar repositório.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
            self.after(0, self.set_status, "✗ Erro ao clonar.")
        finally:
            self.after(0, lambda: self.clone_button.configure(state="normal"))

    # --- Conectar Pasta Local e Fazer Push ---
    def start_link_local_repo(self) -> None:
        """(UI Thread) Inicia a conexão de uma pasta local com um repo remoto."""
        repo = self._get_selected_repo()
        if not repo:
            return
        
        local_path = filedialog.askdirectory(title="Selecione a Pasta do Projeto Local")
        if not local_path:
            self.set_status("Operação cancelada.")
            return
        
        self.current_local_path = local_path
        self.set_status(f"🔗 Conectando pasta local a '{repo.name}'...")
        self.link_local_button.configure(state="disabled")
        self.run_in_thread(self.link_local_repo, repo, local_path)

    def link_local_repo(self, repo_remote: Repository.Repository, local_path: str) -> None:
        """(Worker Thread) Conecta a pasta local ao repositório e faz push."""
        # CORREÇÃO: Inicializa branch_name para evitar erro 'unbound'
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
            self.after(0, self.set_status, "📝 Adicionando arquivos (git add)...")
            repo_local.git.add(all=True)
            
            # Commit (apenas se houver mudanças)
            if repo_local.is_dirty(untracked_files=True):
                self.after(0, self.set_status, "💾 Criando commit...")
                repo_local.index.commit("Commit via Gestor GitHub")
            else:
                self.after(0, self.set_status, "ℹ️ Nenhuma mudança para commitar. Prosseguindo...")
            
            # Determina o branch atual
            try:
                branch_name = repo_local.active_branch.name
            except TypeError:
                # Se não houver branch (repo novo), cria 'main'
                repo_local.git.branch("-M", branch_name) # branch_name ainda é "main"
            
            # Push (SEM --force)
            self.after(0, self.set_status, f"⬆️ Enviando branch '{branch_name}' para o GitHub...")
            repo_local.git.push("--set-upstream", "origin", branch_name)
            
            self.after(0, self.set_status, "✓ Sucesso! Pasta local conectada e enviada.")
            self.after(0, messagebox.showinfo, "Sucesso", "Seus arquivos foram enviados para o GitHub com sucesso!")
            
        except git.GitCommandError as e:
            # Tenta lidar com o erro comum 'main' vs 'master'
            if "src refspec main does not match any" in str(e) and branch_name == "main":
                self.after(0, self.set_status, "ℹ️ 'main' falhou, tentando 'master'...")
                # Re-abre o repo para garantir que o estado está correto
                repo_local = git.Repo(local_path) 
                repo_local.git.branch("-M", "master")
                repo_local.git.push("--set-upstream", "origin", "master")
                self.after(0, self.set_status, "✓ Sucesso! Pasta local conectada e enviada.")
                self.after(0, messagebox.showinfo, "Sucesso", "Seus arquivos foram enviados para o GitHub com sucesso!")
            else:
                self.after(0, messagebox.showerror, "Erro de Git", f"Um comando Git falhou:\n{e}")
                self.after(0, self.set_status, "✗ Erro durante operação do Git.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Ocorreu um erro inesperado:\n{e}")
            self.after(0, self.set_status, "✗ Erro inesperado.")
        finally:
            self.after(0, lambda: self.link_local_button.configure(state="normal"))

    # --- Pull (Atualizar Local) ---
    def start_pull_repo(self) -> None:
        """(UI Thread) Inicia o 'pull' para um repositório local."""
        local_path = filedialog.askdirectory(title="Selecione o Repositório Local para Atualizar")
        if not local_path:
            return
        
        self.set_status("⬇️ Atualizando repositório local...")
        self.pull_button.configure(state="disabled")
        self.run_in_thread(self.pull_repo, local_path)

    def pull_repo(self, local_path: str) -> None:
        """(Worker Thread) Faz 'pull' do repositório remoto."""
        try:
            repo = git.Repo(local_path)
            if not repo.remotes:
                self.after(0, messagebox.showerror, "Erro", "Nenhum remote configurado neste repositório.")
                return
            
            origin = repo.remotes.origin
            self.after(0, self.set_status, "⬇️ Baixando atualizações...")
            origin.pull()
            
            self.after(0, self.set_status, "✓ Repositório atualizado com sucesso!")
            self.after(0, messagebox.showinfo, "Sucesso", "Repositório local atualizado com as últimas mudanças!")
            
        except git.GitCommandError as e:
            self.after(0, messagebox.showerror, "Erro de Git", f"Falha ao fazer pull:\n{e}")
            self.after(0, self.set_status, "✗ Erro ao atualizar repositório.")
        except git.InvalidGitRepositoryError:
            self.after(0, messagebox.showerror, "Erro", "A pasta selecionada não é um repositório Git válido.")
            self.after(0, self.set_status, "✗ Repositório inválido.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro inesperado: {e}")
            self.after(0, self.set_status, "✗ Erro ao atualizar.")
        finally:
            self.after(0, lambda: self.pull_button.configure(state="normal"))

    # --- Importar Pasta Local ---
    def start_import_local_folder(self) -> None:
        """(UI Thread) Inicia a importação de uma pasta para o repositório."""
        repo = self._get_selected_repo()
        if not repo:
            return
        
        local_folder_path = filedialog.askdirectory(title="Selecione a Pasta para Importar")
        if not local_folder_path:
            self.set_status("Importação de pasta cancelada.")
            return
        
        self.set_status(f"📤 Importando pasta '{Path(local_folder_path).name}'...")
        self.import_folder_button.configure(state="disabled")
        self.import_file_button.configure(state="disabled")
        self.run_in_thread(self.import_local_folder, repo, Path(local_folder_path))

    def import_local_folder(self, repo_remote: Repository.Repository, local_folder_path: Path) -> None:
        """(Worker Thread) Clona, copia, commita e faz push da pasta."""
        temp_dir = self.TEMP_DIR
        repo_dir = temp_dir / repo_remote.name
        
        try:
            # Limpa pasta temporária se existir
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Clona repositório
            self.after(0, self.set_status, "⬇️ Clonando repositório temporariamente...")
            repo_local = git.Repo.clone_from(repo_remote.clone_url, str(repo_dir))
            
            # Copia pasta para o repositório
            self.after(0, self.set_status, "📁 Copiando arquivos...")
            destination = repo_dir / local_folder_path.name
            shutil.copytree(local_folder_path, destination, dirs_exist_ok=True)
            
            # Adiciona, commita e faz push
            self.after(0, self.set_status, "💾 Fazendo commit...")
            repo_local.git.add(all=True)
            repo_local.index.commit(f"Importar pasta: {local_folder_path.name}")
            
            self.after(0, self.set_status, "⬆️ Enviando para o GitHub...")
            repo_local.remotes.origin.push()
            
            self.after(0, self.set_status, f"✓ Pasta '{local_folder_path.name}' importada com sucesso!")
            self.after(0, messagebox.showinfo, "Sucesso", f"Pasta '{local_folder_path.name}' foi importada para o repositório!")
            
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro ao importar pasta: {e}")
            self.after(0, self.set_status, "✗ Erro ao importar pasta.")
        finally:
            self.after(0, lambda: self.import_folder_button.configure(state="normal"))
            self.after(0, lambda: self.import_file_button.configure(state="normal"))
            # Limpa pasta temp em caso de falha
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    print(f"Não foi possível limpar a pasta temporária: {e}")

    # --- Importar Arquivo Local ---
    def start_import_local_file(self) -> None:
        """(UI Thread) Inicia a importação de um arquivo para o repositório."""
        repo = self._get_selected_repo()
        if not repo:
            return
        
        local_file_path = filedialog.askopenfilename(title="Selecione o Arquivo para Importar")
        if not local_file_path:
            self.set_status("Importação de arquivo cancelada.")
            return
        
        self.set_status(f"📤 Importando arquivo '{Path(local_file_path).name}'...")
        self.import_file_button.configure(state="disabled")
        self.import_folder_button.configure(state="disabled")
        self.run_in_thread(self.import_local_file, repo, Path(local_file_path))

    def import_local_file(self, repo: Repository.Repository, local_file_path: Path) -> None:
        """(Worker Thread) Lê e faz upload do arquivo (apenas texto)."""
        try:
            try:
                # Tenta ler como texto
                content = local_file_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                self.after(0, messagebox.showwarning, "Aviso", 
                           f"O arquivo '{local_file_path.name}' parece ser binário (ex: imagem, .exe).\n"
                           "Esta função suporta apenas a importação de arquivos de texto.\n\n"
                           "Operação cancelada.")
                self.after(0, self.set_status, "✗ Importação cancelada (arquivo binário).")
                return
            
            file_name = local_file_path.name
            
            # Verifica se o arquivo já existe no repo
            try:
                existing_file = repo.get_contents(file_name)
                # Atualiza arquivo existente
                self.after(0, self.set_status, f"📝 Atualizando arquivo '{file_name}'...")
                repo.update_file(
                    file_name,
                    f"Atualizar {file_name}",
                    content,
                    existing_file.sha # type: ignore
                )
                message = f"Arquivo '{file_name}' atualizado com sucesso!"
                
            except GithubException as e: 
                if e.status == 404: # Se o arquivo não existe
                    # Cria novo arquivo
                    self.after(0, self.set_status, f"📝 Criando arquivo '{file_name}'...")
                    repo.create_file(
                        file_name,
                        f"Adicionar {file_name}",
                        content
                    )
                    message = f"Arquivo '{file_name}' importado com sucesso!"
                else:
                    raise # Re-levanta outras exceções da API
            
            self.after(0, self.set_status, f"✓ {message}")
            self.after(0, messagebox.showinfo, "Sucesso", message)
            
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Erro ao importar arquivo: {e}")
            self.after(0, self.set_status, "✗ Erro ao importar arquivo.")
        finally:
            self.after(0, lambda: self.import_file_button.configure(state="normal"))
            self.after(0, lambda: self.import_folder_button.configure(state="normal"))

    # --- Funções do Prompt de IDE ---
    def prompt_open_ide(self, path: str) -> None:
        """(UI Thread) Cria o diálogo para escolher o IDE."""
        dialog = IDEPrompt(self)
        choice = dialog.get_choice() # Espera o utilizador escolher
        
        if choice:
            self.run_in_thread(self.open_in_ide, path, choice)

    def open_in_ide(self, path: str, ide_choice: str) -> None:
        """(Worker Thread) Tenta abrir a pasta do projeto no IDE escolhido."""
        self.after(0, self.set_status, f"Abrindo {path} em {ide_choice}...")
        
        # CORREÇÃO: Inicializa command_str para evitar erro 'unbound'
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
                subprocess.Popen(command, cwd=path, shell=shell_needed, startupinfo=_get_startup_info())
            
        except FileNotFoundError:
            self.after(0, messagebox.showerror, "Erro", 
                       f"Não foi possível encontrar o comando para '{command_str}'.\n"
                       f"Certifique-se de que o IDE está instalado e o seu comando ('{command_str}') está no PATH do sistema.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Falha ao abrir o IDE: {e}")

    # --- Abrir Terminal ---
    # (LIMPEZA: Funções 'find_git_bash' e 'open_git_bash' removidas e substituídas por estas)
    def open_terminal(self) -> None:
        """(UI Thread) Abre o terminal (Git Bash no Windows, ou padrão no Linux/macOS) no diretório local."""
        path_to_open_str = self.current_local_path
        
        # Se não houver um path local atual, pede ao utilizador para selecionar um
        if not path_to_open_str or not Path(path_to_open_str).is_dir():
             path_to_open_str = filedialog.askdirectory(title="Selecione o diretório do repositório local")
             if not path_to_open_str:
                 self.set_status("Operação de terminal cancelada.")
                 return
        
        # Atualiza o path atual
        self.current_local_path = path_to_open_str

        self.set_status(f"Abrindo terminal em: {self.current_local_path}...")
        self.run_in_thread(self._open_terminal_worker, self.current_local_path)

    def _open_terminal_worker(self, path_to_open: str) -> None:
        """(Worker Thread) Lógica para abrir o terminal."""
        try:
            if os.name == 'nt':  # Windows
                git_bash_path = self.find_git_bash() # Tenta encontrar o Git Bash
                if git_bash_path:
                    subprocess.Popen([str(git_bash_path), "--cd=" + path_to_open], startupinfo=_get_startup_info())
                    self.after(0, self.set_status, f"✓ Git Bash aberto em: {path_to_open}")
                else:
                    # Fallback para cmd se Git Bash não for encontrado
                    subprocess.Popen(["cmd.exe"], cwd=path_to_open, startupinfo=_get_startup_info())
                    self.after(0, self.set_status, f"✓ Prompt de Comando aberto em: {path_to_open}")
            else:  # Linux/macOS
                terminals = [ 
                    ["x-terminal-emulator", "-e", f"cd {path_to_open} && bash"],
                    ["gnome-terminal", "--", "bash", "-c", f"cd {path_to_open}; exec bash"],
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
                    self.after(0, self.set_status, f"✓ Terminal aberto em: {path_to_open}")
                else:
                     self.after(0, messagebox.showerror, "Erro", "Não foi possível abrir um terminal. Tente abrir manualmente.")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", f"Falha ao abrir o terminal: {e}")
            self.after(0, self.set_status, "✗ Erro ao abrir terminal.")

    def find_git_bash(self) -> Optional[Path]:
        """Tenta encontrar o executável do Git Bash no Windows (usando Pathlib)."""
        program_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
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