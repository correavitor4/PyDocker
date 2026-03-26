# main.py
import docker
from docker.errors import APIError, DockerException

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Log, TabbedContent, TabPane
from textual.widgets.data_table import Column
from textual.screen import Screen, ModalScreen
from textual.widgets import Input, Button, Label
from textual.containers import Vertical, Horizontal

# --- Docker initial connection ---
# Attempts to connect to the Docker daemon; exits on failure.
try:
    docker_client = docker.from_env()
    # Quick ping to ensure the daemon is responsive.
    docker_client.ping()
except DockerException:
    print("❌ Error: Unable to connect to Docker.")
    print("   Please check that the Docker daemon/service is running.")
    exit(1)


class CreateNetworkScreen(ModalScreen):
    """Modal screen to create a new Docker network."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("New network name:")
            yield Input(placeholder="Type network name", id="network_name")
            with Horizontal():
                yield Button("Create", id="create_btn", variant="primary")
                yield Button("Cancel", id="cancel_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_btn":
            network_name = self.query_one("#network_name", Input).value.strip()
            if network_name:
                try:
                    docker_client.networks.create(network_name, driver="bridge")
                    self.app.notify(f"✅ Network '{network_name}' created successfully!", severity="information")
                    self.app.query_one("#networks", DataTable).clear()
                    self.app.update_networks_table()
                except APIError as e:
                    self.app.notify(f"Error creating network: {e}", severity="error")
            else:
                self.app.notify("Network name cannot be empty.", severity="warning")
        self.app.pop_screen()


class LogsScreen(Screen):
    """Screen for viewing container logs."""

    BINDINGS = [
        Binding(key="b", action="back", description="⬅️ Voltar"),
        Binding(key="q", action="quit", description="Quit"),
    ]

    def __init__(self, logs: str):
        super().__init__()
        self.logs_content = logs

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="logs", highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#logs", Log).write(self.logs_content)

    def action_back(self) -> None:
        """Voltar para a interface principal."""
        self.app.pop_screen()


class DockerTUI(App):
    """A terminal UI for managing Docker resources."""

    TITLE = "🐳 PyDocker"
    SUB_TITLE = "A terminal Docker dashboard - Built by Vitor Corrêa (https://github.com/correavitor4)"

    # --- Atalhos de Teclado (Key Bindings) ---
    BINDINGS = [
        Binding(key="r", action="refresh_tables", description="🔄 Refresh"),
        Binding(key="s", action="stop_container", description="🛑 Stop"),
        Binding(key="d", action="start_container", description="▶️ Start"),
        Binding(key="x", action="remove_container", description="❌ Remove"),
        Binding(key="l", action="show_logs", description="📜 Logs"),
        Binding(key="c", action="create_network", description="🌐 Create network"),
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="i", action="refresh_images", description="🔄 Refresh images"),
    ]

    def compose(self) -> ComposeResult:
        """Create and arrange UI widgets."""
        yield Header()
        with TabbedContent():
            with TabPane("Containers", id="containers_tab"):
                yield DataTable(id="containers")
            with TabPane("Images", id="images_tab"):
                yield DataTable(id="images")
            with TabPane("Volumes", id="volumes_tab"):
                yield DataTable(id="volumes")
            with TabPane("Networks", id="networks_tab"):
                yield DataTable(id="networks")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted. Configure tables and load data."""
        # Setup containers table columns
        containers_table = self.query_one("#containers", DataTable)
        containers_table.add_column("ID")
        containers_table.add_column("Name")
        containers_table.add_column("Image")
        containers_table.add_column("Status")
        containers_table.cursor_type = "row"

        # Load containers data
        self.update_containers_table()

        # Configure columns for images table
        images_table = self.query_one("#images", DataTable)
        images_table.add_column("ID")
        images_table.add_column("Name")
        images_table.add_column("Image")
        images_table.cursor_type = "row"

        # Load images data
        self.update_images_table()

        # Configure columns for volumes table
        volumes_table = self.query_one("#volumes", DataTable)
        volumes_table.add_column("Name")
        volumes_table.add_column("Driver")
        volumes_table.cursor_type = "row"

        # Load volumes data
        self.update_volumes_table()

        # Configure columns for networks table
        networks_table = self.query_one("#networks", DataTable)
        networks_table.add_column("Name")
        networks_table.add_column("Driver")
        networks_table.cursor_type = "row"

        # Load networks data
        self.update_networks_table()

        # Inicia a atualização dos dados a cada 1s
        self.update_data_timer = self.set_interval(1000, self.update_data)

    def update_containers_table(self) -> None:
        """Fetch Docker container data and refresh the containers table."""
        table = self.query_one("#containers", DataTable)
        
        # Keep the selected row key so we can restore focus after table refresh
        selected_row = table.cursor_row
        if selected_row is not None and 0 <= selected_row < len(table.rows):
            # table.rows is a dict, so we fetch the RowKey by index
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
        
        self.sub_title = "A terminal Docker dashboard - Built by Vitor Corrêa (https://github.com/correavitor4)"

    # --- Ações dos Atalhos ---

    def action_refresh_tables(self) -> None:
        """Action for 'r' key binding: refresh all tables."""
        self.notify("🔄 Refreshing container list...")
        self.update_containers_table()

    def _get_selected_container_id(self) -> str | None:
        """Helper to get the selected container ID from the table."""
        table = self.query_one("#containers", DataTable)
        if not table.row_count or not (0 <= table.cursor_row < len(table.rows)):
            self.notify("No containers available.", severity="warning")
            return None
        
        # Get the current row's RowKey and return its value (container ID)
        row_key = list(table.rows.keys())[table.cursor_row]
        return row_key.value

    def action_stop_container(self) -> None:
        """Action to stop the selected container."""
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status == "running":
                    self.notify(f"Stopping container {container.name}...")
                    container.stop()
                    self.notify(f"✅ Container {container.name} stopped.", severity="information")
                else:
                    self.notify(f"⚠️ Container {container.name} is already stopped.", severity="warning")
                self.update_containers_table()
            except APIError as e:
                self.notify(f"Error stopping container: {e}", severity="error")

    def action_start_container(self) -> None:
        """Action to start the selected container."""
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status != "running":
                    self.notify(f"Starting container {container.name}...")
                    container.start()
                    self.notify(f"✅ Container {container.name} started.", severity="information")
                else:
                    self.notify(f"⚠️ Container {container.name} is already running.", severity="warning")
                self.update_containers_table()
            except APIError as e:
                self.notify(f"Error starting container: {e}", severity="error")

    def action_remove_container(self) -> None:
        """Action to remove the selected container."""
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status != "running":
                    self.notify(f"Removing container {container.name}...")
                    container.remove()
                    self.notify(f"✅ Container {container.name} removed.", severity="information")
                    self.update_containers_table()
                else:
                    self.notify("🛑 Stop the container before removing.", severity="error")
            except APIError as e:
                self.notify(f"Error removing container: {e}", severity="error")

    def action_show_logs(self) -> None:
        """Ação para mostrar os logs do contêiner selecionado."""
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                logs = container.logs(tail=100, stream=False, timestamps=True).decode('utf-8', errors='ignore')
                logs_screen = LogsScreen(logs)
                self.push_screen(logs_screen)
            except APIError as e:
                self.notify(f"Erro ao buscar logs: {e}", severity="error")
        else:
            self.notify("Selecione um contêiner para ver os logs.", severity="warning")

    def update_images_table(self) -> None:
        """Fetch Docker image data and refresh images table."""
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
        """Fetch Docker volume data and refresh volumes table."""
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
        """Fetch Docker network data and refresh networks table."""
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
        """Action for 'i' key binding: refresh images table."""
        self.notify("🔄 Refreshing image list...")
        self.update_images_table()

    def action_create_network(self) -> None:
        """Action to open network creation modal."""
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
