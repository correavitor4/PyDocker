import docker  # Continuamos usando a biblioteca docker-py, pois o Podman é compatível
from docker.errors import APIError, DockerException
import os
import subprocess
import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import DataTable, Footer, Header, Log, TabbedContent, TabPane, Input, Button, Label
from textual.screen import Screen, ModalScreen

# --- Podman Connection Helper ---
def get_podman_client():
    """
    Tenta conectar ao socket do Podman. 
    No Linux (Rootless), o caminho comum é /run/user/{uid}/podman/podman.sock
    """
    try:
        # Se estiver no Windows, o Podman Machine costuma expor via npipe
        # Se no Linux, tentamos detectar o socket do usuário
        if os.name != 'nt':
            uid = os.getuid()
            path = f"unix:///run/user/{uid}/podman/podman.sock"
            client = docker.DockerClient(base_url=path)
        else:
            client = docker.from_env() # No Windows/Mac, o Podman Desktop configura as envs
        
        client.ping()
        return client
    except Exception:
        return None

podman_client = get_podman_client()

if not podman_client:
    print("❌ Erro: Não foi possível conectar ao Podman.")
    print("   Certifique-se que o serviço do Podman está rodando:")
    print("   'podman system service --time=0 &'")
    # Opcional: Tentar iniciar o serviço automaticamente (Linux)
    if os.name != 'nt':
         subprocess.Popen(["podman", "system", "service", "--time=0"])
         time.sleep(2)
         podman_client = get_podman_client()
    
    if not podman_client:
        exit(1)

class CreateNetworkScreen(ModalScreen):
    """Modal para criar rede no Podman."""
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Nome da nova rede Podman:")
            yield Input(placeholder="Ex: minha-rede", id="network_name")
            with Horizontal():
                yield Button("Criar", id="create_btn", variant="primary")
                yield Button("Cancelar", id="cancel_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_btn":
            name = self.query_one("#network_name", Input).value.strip()
            if name:
                try:
                    podman_client.networks.create(name, driver="bridge")
                    self.app.notify(f"✅ Rede '{name}' criada!")
                    self.app.update_networks_table()
                except APIError as e:
                    self.app.notify(f"Erro: {e}", severity="error")
        self.app.pop_screen()

class LogsScreen(Screen):
    BINDINGS = [Binding("b", "back", "Voltar"), Binding("q", "quit", "Sair")]
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
        self.app.pop_screen()

class PodmanTUI(App):
    """Interface TUI para gerenciar Podman."""
    TITLE = "🦭 PyPodman"
    SUB_TITLE = "Dashboard para Podman (API Compatible)"

    BINDINGS = [
        Binding("r", "refresh_all", "🔄 Refresh Tudo"),
        Binding("s", "stop_container", "🛑 Stop"),
        Binding("d", "start_container", "▶️ Start"),
        Binding("x", "remove_container", "❌ Remove"),
        Binding("l", "show_logs", "📜 Logs"),
        Binding("c", "create_network", "🌐 Nova Rede"),
        Binding("q", "quit", "Sair"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Containers", id="containers_tab"):
                yield DataTable(id="containers")
            with TabPane("Imagens", id="images_tab"):
                yield DataTable(id="images")
            with TabPane("Volumes", id="volumes_tab"):
                yield DataTable(id="volumes")
            with TabPane("Redes", id="networks_tab"):
                yield DataTable(id="networks")
        yield Footer()

    def on_mount(self) -> None:
        # Setup de colunas (mesma lógica do Docker)
        self.setup_tables()
        self.update_all_data()
        self.set_interval(3000, self.update_all_data) # 3s para poupar CPU com Podman

    def setup_tables(self):
        c = self.query_one("#containers", DataTable)
        c.add_columns("ID", "Nome", "Imagem", "Status", "Portas", "Criado")
        c.cursor_type = "row"

        i = self.query_one("#images", DataTable)
        i.add_columns("ID", "Repo", "Tag", "Tamanho")
        i.cursor_type = "row"

        v = self.query_one("#volumes", DataTable)
        v.add_columns("Nome", "Driver", "Mountpoint")

        n = self.query_one("#networks", DataTable)
        n.add_columns("Nome", "Driver", "Subnet")

    def update_all_data(self) -> None:
        self.update_containers_table()
        self.update_images_table()
        self.update_volumes_table()
        self.update_networks_table()

    def update_containers_table(self) -> None:
        table = self.query_one("#containers", DataTable)
        selected_key = list(table.rows.keys())[table.cursor_row] if table.cursor_row is not None and table.rows else None
        table.clear()

        for container in podman_client.containers.list(all=True):
            status = container.status
            color = "green" if status == "running" else "red" if "exited" in status else "yellow"
            
            image = container.image.tags[0] if container.image.tags else container.image.short_id
            created = container.attrs.get('Created', '')[:16].replace('T', ' ')
            
            table.add_row(
                container.short_id,
                container.name,
                image,
                f"[b {color}]{status}[/]",
                str(container.attrs.get('NetworkSettings', {}).get('Ports', {})),
                created,
                key=container.id
            )
        if selected_key in table.rows:
            table.move_cursor(row=table.get_row_index(selected_key))

    def update_images_table(self) -> None:
        table = self.query_one("#images", DataTable)
        table.clear()
        for img in podman_client.images.list():
            tag = img.tags[0] if img.tags else "<none>"
            repo, t = tag.split(':') if ':' in tag else (tag, "")
            size = f"{img.attrs['Size'] // (1024**2)}MB"
            table.add_row(img.short_id, repo, t, size, key=img.id)

    def update_volumes_table(self) -> None:
        table = self.query_one("#volumes", DataTable)
        table.clear()
        for vol in podman_client.volumes.list():
            table.add_row(vol.name, vol.attrs.get('Driver', '-'), vol.attrs.get('Mountpoint', '-'))

    def update_networks_table(self) -> None:
        table = self.query_one("#networks", DataTable)
        table.clear()
        for net in podman_client.networks.list():
            subnet = "N/A"
            if 'IPAM' in net.attrs and net.attrs['IPAM'].get('Config'):
                subnet = net.attrs['IPAM']['Config'][0].get('Subnet', 'N/A')
            table.add_row(net.name, net.attrs.get('Driver', '-'), subnet)

    # --- Actions ---
    def _get_selected_id(self, table_id="#containers"):
        table = self.query_one(table_id, DataTable)
        if table.cursor_row is not None and table.rows:
            return list(table.rows.keys())[table.cursor_row].value
        return None

    def action_stop_container(self):
        if cid := self._get_selected_id():
            podman_client.containers.get(cid).stop()
            self.notify("🛑 Container parado")
            self.update_containers_table()

    def action_start_container(self):
        if cid := self._get_selected_id():
            podman_client.containers.get(cid).start()
            self.notify("▶️ Container iniciado")
            self.update_containers_table()

    def action_show_logs(self):
        if cid := self._get_selected_id():
            c = podman_client.containers.get(cid)
            logs = c.logs(tail=100).decode('utf-8', errors='ignore')
            self.push_screen(LogsScreen(logs))

    def action_refresh_all(self):
        self.update_all_data()
        self.notify("🔄 Dados atualizados")

    def action_create_network(self):
        self.push_screen(CreateNetworkScreen())

if __name__ == "__main__":
    PodmanTUI().run()