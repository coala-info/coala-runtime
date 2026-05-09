"""Container manager using Singularity or Apptainer instances (``docker://`` images)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Optional, Sequence, Union

from docker.errors import DockerException

from coala_runtime.runtime.engine import singularity_image_uri

logger = logging.getLogger(__name__)


def _read_tail_lines(path: str, tail: int) -> str:
    """Return the last ``tail`` lines of a UTF-8 text file."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        if tail <= 0:
            return "\n".join(lines)
        return "\n".join(lines[-tail:])
    except OSError as e:
        return f"<read error: {e}>"


class SingularityInstanceContainer:
    """Tracks one ``singularity instance start`` session."""

    def __init__(self, instance_name: str, cli: str) -> None:
        self.id = instance_name
        self._cli = cli
        self.status = "running"

    def reload(self) -> None:
        try:
            r = subprocess.run(
                [self._cli, "instance", "list", "-j", self.id],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode != 0:
                self.status = "unknown"
                return
            data = json.loads(r.stdout or "{}")
            for inst in data.get("instances", []):
                if inst.get("instance") == self.id:
                    self.status = "running"
                    return
            self.status = "exited"
        except Exception:
            self.status = "unknown"


class SingularityContainerManager:
    """Manages Singularity/Apptainer instance lifecycle (OCI ``docker://`` URIs)."""

    def __init__(self, cli_binary: str = "singularity") -> None:
        exe = shutil.which(cli_binary)
        if not exe:
            raise DockerException(
                f"{cli_binary} executable not found on PATH; "
                f"install Singularity/Apptainer or set COALA_CONTAINER_ENGINE=docker|podman."
            )
        self.cli = exe
        self.containers: Dict[str, SingularityInstanceContainer] = {}

    def _bind_cli_args(self, volumes: Optional[Dict[str, Dict[str, str]]]) -> list[str]:
        args: list[str] = []
        if not volumes:
            return args
        for host, spec in volumes.items():
            dest = spec["bind"]
            mode = (spec.get("mode") or "rw").lower()
            opt = "ro" if mode == "ro" else "rw"
            args.extend(["-B", f"{host}:{dest}:{opt}"])
        return args

    async def ensure_image(self, image: str) -> None:
        """Images are fetched when the instance starts (same as lazy Docker pull)."""

    async def create_container(
        self,
        image: str,
        command: Optional[Union[str, Sequence[str]]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        working_dir: str = "/workspace",
        environment: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
    ) -> SingularityInstanceContainer:
        del working_dir, environment, name  # applied on exec, not instance start
        _ = command  # always use tail keeper like Docker path
        uri = singularity_image_uri(image)
        instance_name = f"coala_{uuid.uuid4().hex}"
        argv = [
            self.cli,
            "instance",
            "start",
            "--writable-tmpfs",
            "--compat",
        ]
        argv.extend(self._bind_cli_args(volumes))
        argv.extend([uri, instance_name, "tail", "-f", "/dev/null"])

        loop = asyncio.get_event_loop()

        def _start() -> None:
            r = subprocess.run(argv, capture_output=True, text=True)
            if r.returncode != 0:
                detail = (r.stderr or r.stdout or "").strip()
                raise DockerException(
                    f"{os.path.basename(self.cli)} instance start failed for {uri}: {detail}"
                )

        await loop.run_in_executor(None, _start)
        handle = SingularityInstanceContainer(instance_name, self.cli)
        self.containers[instance_name] = handle
        logger.info(
            "Started %s instance %s for image %s",
            os.path.basename(self.cli),
            instance_name[:12],
            image,
        )
        return handle

    async def start_container(self, container: SingularityInstanceContainer) -> None:
        """Instance is already running after ``instance start``."""

    async def exec_command(
        self,
        container: SingularityInstanceContainer,
        command: Union[str, Sequence[str]],
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
    ) -> tuple[int, bytes, bytes]:
        inst_url = f"instance://{container.id}"
        argv = [self.cli, "exec"]
        if workdir:
            argv.extend(["--pwd", workdir])
        argv.append(inst_url)

        env = os.environ.copy()
        if environment:
            env.update({k: str(v) for k, v in environment.items()})

        if isinstance(command, str):
            argv.extend(["/bin/sh", "-lc", command])
        else:
            argv.extend(list(command))

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()
        code = proc.returncode if proc.returncode is not None else -1
        return code, stdout or b"", stderr or b""

    async def get_logs(self, container: SingularityInstanceContainer, tail: int = 1000) -> str:
        try:
            r = subprocess.run(
                [self.cli, "instance", "list", "-j", container.id],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode != 0:
                return f"Could not list instance {container.id}: {r.stderr}"
            data = json.loads(r.stdout or "{}")
            instances = data.get("instances") or []
            if len(instances) != 1:
                return f"No log paths for instance {container.id}"
            out_path = instances[0].get("logOutPath") or ""
            err_path = instances[0].get("logErrPath") or ""
            parts: list[str] = []
            for label, path in (("stdout", out_path), ("stderr", err_path)):
                if path and os.path.isfile(path):
                    content = _read_tail_lines(path, tail)
                    parts.append(f"--- {label} ({path}) ---\n{content}")
            return "\n".join(parts) if parts else "Instance logs not available on disk yet."
        except Exception as e:
            return f"Error retrieving Singularity/Apptainer logs: {e}"

    async def remove_container(
        self, container: SingularityInstanceContainer, force: bool = True
    ) -> None:
        del force
        cid = container.id
        loop = asyncio.get_event_loop()

        def _stop() -> None:
            subprocess.run(
                [self.cli, "instance", "stop", cid],
                capture_output=True,
                text=True,
            )

        await loop.run_in_executor(None, _stop)
        self.containers.pop(cid, None)
        logger.info("Stopped %s instance %s", os.path.basename(self.cli), cid[:12])

    async def cleanup_all(self) -> None:
        for c in list(self.containers.values()):
            await self.remove_container(c)
