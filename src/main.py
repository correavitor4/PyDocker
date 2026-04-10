# main.py
import docker
from docker.errors import APIError, DockerException

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Log, TabbedContent, TabPane
from textual.screen import Screen, ModalScreen
from textual.widgets import Input, Button, Label
from textual.containers import Vertical, Horizontal
import time

# --- Docker initial connection ---
try:
    docker_client = docker.from_env()
    docker_client.ping()
except DockerException:
    print("❌ Error: Unable to connect to Docker.")
    print("   Attempting to start Docker Desktop...")
    import subprocess
    try:
        subprocess.Popen(["C:\\Program Files\\Docker\\Docker Desktop.exe"])
        for _ in range(30):
            time.sleep(1)
            try:
                docker_client = docker.from_env()
                docker_client.ping()
                print("✅ Docker started successfully!")
                break
            except DockerException:
                pass
        else:
            print("   Docker did not start within 30 seconds. Please start Docker Desktop manually.")
            exit(1)
    except FileNotFoundError:
        print("   Docker Desktop not found at default location. Please start Docker manually.")
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
                    self.app.update_data()
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
    SUB_TITLE = "A terminal Docker dashboard - Built by Vitor Corrêa"

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
        Binding(key="v", action="refresh_volumes", description="🔄 Refresh volumes"),
        Binding(key="n", action="refresh_networks", description="🔄 Refresh networks"),
    ]

    def compose(self) -> ComposeResult:
        """Create and arrange UI widgets."""
        yield Header()
        with TabbedContent(id="tabs"):
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
        self.setup_tables()
        self.update_data()
        
        # Inicia a atualização automática a cada 2 segundos.
        # Intervalos maiores previnem "flickering" na interface.
        self.set_interval(2.0, self.update_data)

    def setup_tables(self) -> None:
        # Containers
        containers_table = self.query_one("#containers", DataTable)
        containers_table.add_columns("ID", "Name", "Image", "Status", "Ports", "Created", "Size")
        containers_table.cursor_type = "row"

        # Images
        images_table = self.query_one("#images", DataTable)
        images_table.add_columns("ID", "Repository", "Tag", "Size", "Created")
        images_table.cursor_type = "row"

        # Volumes
        volumes_table = self.query_one("#volumes", DataTable)
        volumes_table.add_columns("Name", "Driver", "Mountpoint", "Created")
        volumes_table.cursor_type = "row"

        # Networks
        networks_table = self.query_one("#networks", DataTable)
        networks_table.add_columns("Name", "Driver", "Scope", "Subnet")
        networks_table.cursor_type = "row"

    def update_data(self) -> None:
        """Verifica a aba ativa e atualiza a tabela correspondente."""
        try:
            active_tab = self.query_one("#tabs", TabbedContent).active
            
            if active_tab == "containers_tab":
                self.update_containers_table()
            elif active_tab == "images_tab":
                self.update_images_table()
            elif active_tab == "volumes_tab":
                self.update_volumes_table()
            elif active_tab == "networks_tab":
                self.update_networks_table()
        except Exception:
            pass

    def update_containers_table(self) -> None:
        """Fetch Docker container data and refresh the containers table."""
        try:
            table = self.query_one("#containers", DataTable)
            
            selected_key = None
            if table.cursor_row is not None and 0 <= table.cursor_row < len(table.rows):
                selected_key = list(table.rows.keys())[table.cursor_row]

            containers = docker_client.containers.list(all=True)
            
            # Limpa e repopula sem suspend_update
            table.clear()
            for container in containers:
                status = container.status
                if status == "running":
                    status_styled = f"[b green]{status}[/]"
                elif status.startswith("exited"):
                    status_styled = f"[b red]{status}[/]"
                else:
                    status_styled = f"[b yellow]{status}[/]"

                image_tag = container.image.tags[0] if container.image.tags and container.image.tags[0] is not None else "N/A"
                
                ports = []
                if container.ports:
                    for port_list in container.ports.values():
                        if port_list:
                            for p in port_list:
                                private = p.get('PrivatePort') or p.get('Port') or 'N/A'
                                public = p.get('PublicPort') or p.get('HostPort') or 'N/A'
                                protocol = p.get('Type') or p.get('Protocol') or 'tcp'
                                if private != 'N/A' and public != 'N/A':
                                    ports.append(f"{private}->{public}/{protocol}")
                                elif private != 'N/A':
                                    ports.append(f"{private}/{protocol}")
                                elif public != 'N/A':
                                    ports.append(f"{public}/{protocol}")
                ports_str = ', '.join(ports) if ports else "N/A"
                
                created = container.attrs.get('Created', 'N/A')[:19].replace("T", " ")
                size = f"{container.attrs.get('SizeRootFs', 0) // (1024**2)}MB"
                
                table.add_row(
                    container.short_id,
                    container.name,
                    image_tag,
                    status_styled,
                    ports_str,
                    created,
                    size,
                    key=container.id,
                )
            
            if selected_key and selected_key in table.rows:
                table.move_cursor(row=table.get_row_index(selected_key))

        except APIError:
            pass

    def update_images_table(self) -> None:
        """Fetch Docker image data and refresh images table."""
        try:
            table = self.query_one("#images", DataTable)
            images = docker_client.images.list(all=True)
            
            table.clear()
            for image in images:
                repo_tag = image.tags[0] if image.tags else "<none>:<none>"
                repo, tag = repo_tag.split(':', 1) if ':' in repo_tag else (repo_tag, '<none>')
                size = f"{image.attrs.get('Size', 0) // (1024**2)}MB"
                created = image.attrs.get('Created', 'N/A')[:19].replace("T", " ")
                
                table.add_row(
                    image.short_id,
                    repo,
                    tag,
                    size,
                    created,
                    key=image.id,
                )
        except APIError:
            pass

    def update_volumes_table(self) -> None:
        """Fetch Docker volume data and refresh volumes table."""
        try:
            table = self.query_one("#volumes", DataTable)
            volumes = docker_client.volumes.list()
            
            table.clear()
            for volume in volumes:
                mountpoint = volume.attrs.get('Mountpoint', 'N/A')
                created = volume.attrs.get('CreatedAt', 'N/A')
                if created != 'N/A':
                    created = created[:19].replace("T", " ")
                    
                table.add_row(
                    volume.name,
                    volume.attrs.get("Driver", "N/A"),
                    mountpoint,
                    created,
                    key=volume.id,
                )
        except APIError:
            pass

    def update_networks_table(self) -> None:
        """Fetch Docker network data and refresh networks table."""
        try:
            table = self.query_one("#networks", DataTable)
            networks = docker_client.networks.list()
            
            table.clear()
            for network in networks:
                scope = network.attrs.get('Scope', 'N/A')
                subnet = 'N/A'
                if network.attrs.get('IPAM') and network.attrs['IPAM'].get('Config'):
                    config = network.attrs['IPAM']['Config'][0]
                    subnet = config.get('Subnet', 'N/A')
                    
                table.add_row(
                    network.name,
                    network.attrs.get("Driver", "N/A"),
                    scope,
                    subnet,
                    key=network.id,
                )
        except APIError:
            pass

    # --- Ações dos Atalhos ---

    def action_refresh_tables(self) -> None:
        self.notify("🔄 Refreshing...")
        self.update_data()

    def _get_selected_container_id(self) -> str | None:
        table = self.query_one("#containers", DataTable)
        if not table.row_count or not (0 <= table.cursor_row < len(table.rows)):
            self.notify("No containers available.", severity="warning")
            return None
        row_key = list(table.rows.keys())[table.cursor_row]
        return row_key.value

    def action_stop_container(self) -> None:
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status == "running":
                    self.notify(f"Stopping container {container.name}...")
                    container.stop()
                    self.notify(f"✅ Container {container.name} stopped.", severity="information")
                else:
                    self.notify(f"⚠️ Container {container.name} is already stopped.", severity="warning")
                self.update_data()
            except APIError as e:
                self.notify(f"Error stopping container: {e}", severity="error")

    def action_start_container(self) -> None:
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status != "running":
                    self.notify(f"Starting container {container.name}...")
                    container.start()
                    self.notify(f"✅ Container {container.name} started.", severity="information")
                else:
                    self.notify(f"⚠️ Container {container.name} is already running.", severity="warning")
                self.update_data()
            except APIError as e:
                self.notify(f"Error starting container: {e}", severity="error")

    def action_remove_container(self) -> None:
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                if container.status != "running":
                    self.notify(f"Removing container {container.name}...")
                    container.remove()
                    self.notify(f"✅ Container {container.name} removed.", severity="information")
                    self.update_data()
                else:
                    self.notify("🛑 Stop the container before removing.", severity="error")
            except APIError as e:
                self.notify(f"Error removing container: {e}", severity="error")

    def action_show_logs(self) -> None:
        if container_id := self._get_selected_container_id():
            try:
                container = docker_client.containers.get(container_id)
                logs = container.logs(tail=100, stream=False, timestamps=True).decode('utf-8', errors='ignore')
                logs_screen = LogsScreen(logs)
                self.push_screen(logs_screen)
            except APIError as e:
                self.notify(f"Erro ao buscar logs: {e}", severity="error")

    def action_refresh_images(self) -> None:
        self.notify("🔄 Refreshing images...")
        self.update_data()

    def action_refresh_volumes(self) -> None:
        self.notify("🔄 Refreshing volumes...")
        self.update_data()

    def action_refresh_networks(self) -> None:
        self.notify("🔄 Refreshing networks...")
        self.update_data()

    def action_create_network(self) -> None:
        self.push_screen(CreateNetworkScreen())


if __name__ == "__main__":
    app = DockerTUI()
    app.run()