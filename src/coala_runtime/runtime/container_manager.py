"""Container manager for Docker operations."""

import asyncio
import logging
from typing import Dict, Optional

import docker
from docker.errors import DockerException

logger = logging.getLogger(__name__)


class ContainerManager:
    """Manages Docker container lifecycle and operations."""

    def __init__(self, docker_client: Optional[docker.DockerClient] = None):
        """Initialize container manager.

        Args:
            docker_client: Optional Docker client. If None, creates a new client.
        """
        self.client = docker_client or docker.from_env()
        self.containers: Dict[str, docker.models.containers.Container] = {}

    async def create_container(
        self,
        image: str,
        command: Optional[str] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        working_dir: str = "/workspace",
        environment: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
    ) -> docker.models.containers.Container:
        """Create a Docker container.

        Args:
            image: Docker image name
            command: Command to run in container
            volumes: Volume bind mounts (host_path: {bind: container_path, mode: mode})
            working_dir: Working directory in container
            environment: Environment variables
            name: Optional container name

        Returns:
            Created container object
        """
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: self.client.containers.create(
                    image=image,
                    command=command if command else None,
                    volumes=volumes or {},
                    working_dir=working_dir,
                    environment=environment or {},
                    name=name,
                    detach=True,
                    stdin_open=True,
                    tty=True,
                ),
            )
            container_id = container.id
            self.containers[container_id] = container
            logger.info(
                f"Created container {container_id[:12]} from image {image} with command: {command}"
            )
            return container
        except DockerException as e:
            logger.error(f"Failed to create container: {e}")
            raise

    async def start_container(self, container: docker.models.containers.Container) -> None:
        """Start a container.

        Args:
            container: Container to start
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, container.start)
            # Refresh container to get updated status
            container.reload()
            logger.info(f"Started container {container.id[:12]} (status: {container.status})")
        except DockerException as e:
            logger.error(f"Failed to start container: {e}")
            raise

    async def exec_command(
        self,
        container: docker.models.containers.Container,
        command: str,
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
    ) -> tuple[int, bytes, bytes]:
        """Execute a command in a running container.

        Args:
            container: Container to execute command in
            command: Command to execute
            workdir: Working directory for command
            environment: Environment variables

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            # Refresh container status to ensure it's running
            container.reload()
            if container.status != "running":
                raise DockerException(
                    f"Container {container.id[:12]} is not running (status: {container.status})"
                )

            loop = asyncio.get_event_loop()
            exec_result = await loop.run_in_executor(
                None,
                lambda: container.exec_run(
                    command,
                    workdir=workdir,
                    environment=environment or {},
                    stdout=True,
                    stderr=True,
                ),
            )
            exit_code = exec_result.exit_code
            output = exec_result.output
            # Split stdout and stderr (Docker API returns combined output)
            # For simplicity, we'll return the combined output as stdout
            # and empty stderr (actual stderr is in container logs)
            return exit_code, output, b""
        except DockerException as e:
            logger.error(f"Failed to execute command in container: {e}")
            raise

    async def get_logs(
        self, container: docker.models.containers.Container, tail: int = 1000
    ) -> str:
        """Get container logs.

        Args:
            container: Container to get logs from
            tail: Number of lines to retrieve

        Returns:
            Container logs as string
        """
        try:
            loop = asyncio.get_event_loop()
            logs_bytes = await loop.run_in_executor(
                None, lambda: container.logs(tail=tail, stdout=True, stderr=True)
            )
            return logs_bytes.decode("utf-8", errors="replace")
        except DockerException as e:
            logger.error(f"Failed to get container logs: {e}")
            return f"Error retrieving logs: {e}"

    async def remove_container(
        self, container: docker.models.containers.Container, force: bool = True
    ) -> None:
        """Remove a container.

        Args:
            container: Container to remove
            force: Force removal even if running
        """
        try:
            container_id = container.id
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: container.remove(force=force))
            if container_id in self.containers:
                del self.containers[container_id]
            logger.info(f"Removed container {container_id[:12]}")
        except DockerException as e:
            logger.warning(f"Failed to remove container: {e}")

    async def cleanup_all(self) -> None:
        """Remove all managed containers."""
        for container in list(self.containers.values()):
            await self.remove_container(container)

    def __del__(self):
        """Cleanup on deletion."""
        # Note: This is a fallback, but async cleanup should be done explicitly
        pass
