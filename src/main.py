# main.py
import docker
from docker.errors import APIError, DockerException

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Log, TabbedContent, TabPane
from textual.widgets.data_table import Column
from textual.screen import ModalScreen
from textual.widgets import Input, Button, Label
from textual.containers import Vertical, Horizontal

# --- Conexão Inicial com o Docker ---
# Tenta conectar ao daemon do Docker. Se falhar, o programa não inicia.
try:
    docker_client = docker.from_env()
    # Um "ping" rápido para garantir que o daemon está respondendo.
    docker_client.ping()
except DockerException:
    print("❌ Erro: Não foi possível conectar ao Docker.")
    print("   Verifique se o serviço (daemon) do Docker está em execução.")
    exit(1)


class CreateNetworkScreen(ModalScreen):
    """Tela modal para criar uma nova rede Docker."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Nome da nova rede:")
            yield Input(placeholder="Digite o nome da rede", id="network_name")
            with Horizontal():
                yield Button("Criar", id="create_btn", variant="primary")
                yield Button("Cancelar", id="cancel_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_btn":
            network_name = self.query_one("#network_name", Input).value.strip()
            if network_name:
                try:
                    docker_client.networks.create(network_name, driver="bridge")
                    self.app.notify(f"✅ Rede '{network_name}' criada com sucesso!", severity="information")
                    self.app.query_one("#networks", DataTable).clear()
                    self.app.update_networks_table()
                except APIError as e:
                    self.app.notify(f"Erro ao criar rede: {e}", severity="error")
            else:
                self.app.notify("Nome da rede não pode estar vazio.", severity="warning")
        self.app.pop_screen()


class DockerTUI(App):
    """Uma Interface de Usuário de Terminal (TUI) para gerenciar o Docker."""

    TITLE = "🐳 Docker TUI"
    SUB_TITLE = "Um 'Docker Desktop' para o seu terminal"

    # --- Atalhos de Teclado (Key Bindings) ---
    BINDINGS = [
        Binding(key="r", action="refresh_tables", description="🔄 Atualizar"),
        Binding(key="s", action="stop_container", description="🛑 Parar"),
        Binding(key="d", action="start_container", description="▶️ Iniciar"),
        Binding(key="x", action="remove_container", description="❌ Remover"),
        Binding(key="l", action="show_logs", description="📜 Logs"),
        Binding(key="c", action="create_network", description="🌐 Criar rede"),
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="i", action="refresh_images", description="🔄 Atualizar imagens"),
    ]

    def compose(self) -> ComposeResult:
        """Cria e organiza os widgets da interface."""
        yield Header()
        with TabbedContent():
            with TabPane("Contêineres", id="containers_tab"):
                yield DataTable(id="containers")
            with TabPane("Imagens", id="images_tab"):
                yield DataTable(id="images")
            with TabPane("Volumes", id="volumes_tab"):
                yield DataTable(id="volumes")
            with TabPane("Redes", id="networks_tab"):
                yield DataTable(id="networks")
            with TabPane("Logs", id="logs_tab"):
                yield Log(id="logs", highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        """Chamado quando o app é montado. Configura as tabelas e carrega os dados."""
        # Esconde o painel de logs inicialmente
        self.query_one("#logs").display = False

        # Configura as colunas da tabela de contêineres
        containers_table = self.query_one("#containers", DataTable)
        containers_table.add_column("ID")
        containers_table.add_column("Nome")
        containers_table.add_column("Imagem")
        containers_table.add_column("Status")
        containers_table.cursor_type = "row"

        # Carrega os dados na tabela de contêineres
        self.update_containers_table()

        # Configura as colunas da tabela de imagens
        images_table = self.query_one("#images", DataTable)
        images_table.add_column("ID")
        images_table.add_column("Nome")
        images_table.add_column("Imagem")
        images_table.cursor_type = "row"

        # Carrega os dados na tabela de imagens
        self.update_images_table()

        # Configura as colunas da tabela de volumes
        volumes_table = self.query_one("#volumes", DataTable)
        volumes_table.add_column("Nome")
        volumes_table.add_column("Driver")
        volumes_table.cursor_type = "row"

        # Carrega os dados na tabela de volumes
        self.update_volumes_table()

        # Configura as colunas da tabela de redes
        networks_table = self.query_one("#networks", DataTable)
        networks_table.add_column("Nome")
        networks_table.add_column("Driver")
        networks_table.cursor_type = "row"

        # Carrega os dados na tabela de redes
        self.update_networks_table()

        # Inicia a atualização dos dados a cada 1s
        self.update_data_timer = self.set_interval(1000, self.update_data)

    def update_containers_table(self) -> None:
        """Busca os dados do Docker e atualiza a tabela de contêineres."""
        table = self.query_one("#containers", DataTable)
        
        # Salva a chave da linha selecionada para restaurar o cursor depois
        selected_row = table.cursor_row
        if selected_row is not None and 0 <= selected_row < len(table.rows):
            # table.rows é um dicionário, extraímos a chave (RowKey) pela posição
            selected_key = list(table.rows.keys())[selected_row]
        else:
            selected_key = None

        table.clear()

        try:
            for container in docker_client.containers.list(all=True):
                status = container.status
                # Adiciona cor ao status para melhor visualização
                if status == "running":
                    status_styled = f"[b green]{status}[/]"
                elif status.startswith("exited"):
                    status_styled = f"[b red]{status}[/]"
                else:
                    status_styled = f"[b yellow]{status}[/]"

                image_tag = container.image.tags[0] if container.image.tags and container.image.tags[0] is not None else "N/A"
                
                table.add_row(
                    container.short_id,
                    container.name,
                    image_tag,
                    status_styled,
                    key=container.id, # Chave única para identificar a linha
                )
            
            # Restaura a posição do cursor se a linha ainda existir
            if selected_key and selected_key in table.rows:
                table.move_cursor(row=table.get_row_index(selected_key))

        except APIError as e:
            self.notify(f"Erro de API do Docker: {e}", severity="error", timeout=10)
        
        self.sub_title = "Um 'Docker Desktop' para o seu terminal"

    # --- Ações dos Atalhos ---

    def action_refresh_tables(self) -> None:
        """Ação para o atalho 'r', atualiza a tabela."""
        self.notify("🔄 Atualizando lista de contêineres...")
        self.update_containers_table()

    def _get_selected_container_id(self) -> str | None:
        """Helper para obter o ID do contêiner selecionado na tabela."""
        table = self.query_one("#containers", DataTable)
        if not table.row_count or not (0 <= table.cursor_row < len(table.rows)):
            self.notify("Nenhum contêiner na lista.", severity="warning")
            return None
        
        # Obtém a RowKey da linha atual e retorna seu valor (o ID do contêiner)
        row_key = list(table.rows.keys())[table.cursor_row]
        return row_key.value

    def action_stop_container(self) -> None:
        """Ação para parar o contêiner selecionado."""
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status == "running":
                    self.notify(f"Parando contêiner {container.name}...")
                    container.stop()
                    self.notify(f"✅ Contêiner {container.name} parado.", severity="information")
                else:
                    self.notify(f"⚠️ Contêiner {container.name} já está parado.", severity="warning")
                self.update_containers_table()
            except APIError as e:
                self.notify(f"Erro ao parar: {e}", severity="error")

    def action_start_container(self) -> None:
        """Ação para iniciar o contêiner selecionado."""
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status != "running":
                    self.notify(f"Iniciando contêiner {container.name}...")
                    container.start()
                    self.notify(f"✅ Contêiner {container.name} iniciado.", severity="information")
                else:
                    self.notify(f"⚠️ Contêiner {container.name} já está em execução.", severity="warning")
                self.update_containers_table()
            except APIError as e:
                self.notify(f"Erro ao iniciar: {e}", severity="error")

    def action_remove_container(self) -> None:
        """Ação para remover o contêiner selecionado."""
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status != "running":
                    self.notify(f"Removendo contêiner {container.name}...")
                    container.remove()
                    self.notify(f"✅ Contêiner {container.name} removido.", severity="information")
                    self.update_containers_table()
                else:
                    self.notify("🛑 Pare o contêiner antes de remover.", severity="error")
            except APIError as e:
                self.notify(f"Erro ao remover: {e}", severity="error")

    def action_show_logs(self) -> None:
        """Ação para mostrar os logs do contêiner selecionado."""
        log_panel = self.query_one("#logs", Log)
        
        # Se o painel de log estiver visível, esconde e volta para a tabela
        if log_panel.display:
            log_panel.clear()
            log_panel.display = False
            self.query_one("#containers").display = True
            self.set_focus(self.query_one("#containers"))
            self.sub_title = "Um 'Docker Desktop' para o seu terminal"
            return

        # Se não, busca os logs e mostra o painel
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                self.sub_title = f"📜 Logs de {container.name} (pressione 'l' para voltar)"
                
                # Mostra o painel de logs e esconde a tabela
                self.query_one("#containers").display = False
                log_panel.display = True
                
                # Limpa logs antigos e escreve os novos
                log_panel.clear()
                logs = container.logs(stream=False, tail=200).decode("utf-8")
                log_panel.write(logs)
                log_panel.scroll_end(animate=False)
                self.set_focus(log_panel)

            except APIError as e:
                self.notify(f"Erro ao buscar logs: {e}", severity="error")

    def update_images_table(self) -> None:
        """Busca os dados do Docker e atualiza a tabela de imagens."""
        table = self.query_one("#images", DataTable)
        table.clear()

        try:
            for image in docker_client.images.list(all=True):
                table.add_row(
                    image.short_id,
                    image.tags[0] if image.tags else "N/A",
                    image.attrs["RepoTags"][0] if image.attrs["RepoTags"] else "N/A",
                    key=image.id,  # Chave única para identificar a linha
                )
        except APIError as e:
            self.notify(f"Erro de API do Docker: {e}", severity="error")

    def update_volumes_table(self) -> None:
        """Busca os dados do Docker e atualiza a tabela de volumes."""
        table = self.query_one("#volumes", DataTable)
        table.clear()

        try:
            for volume in docker_client.volumes.list():
                table.add_row(
                    volume.name,
                    volume.attrs.get("Driver", "N/A"),
                    key=volume.id,  # Chave única para identificar a linha
                )
        except APIError as e:
            self.notify(f"Erro de API do Docker: {e}", severity="error")

    def update_networks_table(self) -> None:
        """Busca os dados do Docker e atualiza a tabela de redes."""
        table = self.query_one("#networks", DataTable)
        table.clear()

        try:
            for network in docker_client.networks.list():
                table.add_row(
                    network.name,
                    network.attrs.get("Driver", "N/A"),
                    key=network.id,  # Chave única para identificar a linha
                )
        except APIError as e:
            self.notify(f"Erro de API do Docker: {e}", severity="error")

    def action_refresh_images(self) -> None:
        """Ação para o atalho 'r', atualiza a tabela de imagens."""
        self.notify("🔄 Atualizando lista de imagens...")
        self.update_images_table()

    def action_create_network(self) -> None:
        """Ação para criar uma nova rede Docker."""
        self.push_screen(CreateNetworkScreen())

    def update_data(self) -> None:
        """Atualiza os dados do Docker."""
        self.update_containers_table()
        self.update_images_table()
        self.update_volumes_table()
        self.update_networks_table()

if __name__ == "__main__":
    app = DockerTUI()
    app.run()
