"""Machine configuration collector/recorder for Linux.

Gathers platform identity and system configuration from stdlib, wraps
it in a WranglerEnvelope, and records it as a tensor via the Apacheta
interface. No external dependencies beyond the standard library and
what Yanantin already provides.
"""

from __future__ import annotations

import os
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_DNS

from pydantic import BaseModel, ConfigDict, Field

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models import (
    ProvenanceEnvelope,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)
from yanantin.collector._collector_base import CollectorBase
from yanantin.machine.base import _get_machine_id
from yanantin.recorder.base import RecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler


# ── Data Model ────────────────────────────────────────────────────


class MachineConfigData(BaseModel):
    """Immutable snapshot of machine platform configuration.

    All fields are gathered from the Python standard library at
    collection time. The model is frozen and strict — no extra
    fields, all defaults validated.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    hostname: str
    fqdn: str
    os_name: str
    os_version: str
    os_release: str
    architecture: str
    cpu_count: int | None
    python_version: str
    platform_string: str
    machine_id: str
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Collector ─────────────────────────────────────────────────────


class MachineConfigCollector(CollectorBase[MachineConfigData]):
    """Gathers platform identity and capabilities from stdlib.

    Provider ID is deterministic per machine — the same physical
    host always produces the same UUID, derived from the machine ID.
    """

    def __init__(self) -> None:
        self._provider_id = uuid5(
            NAMESPACE_DNS,
            f"yanantin.collector.machine_config.{_get_machine_id()}",
        )

    def collect(self, since: datetime | None = None) -> MachineConfigData:
        """Gather all machine configuration fields from stdlib.

        The ``since`` parameter is accepted but ignored — machine config
        always returns the full current state.
        """
        return MachineConfigData(
            hostname=socket.gethostname(),
            fqdn=socket.getfqdn(),
            os_name=platform.system(),
            os_version=platform.version(),
            os_release=platform.release(),
            architecture=platform.machine(),
            cpu_count=os.cpu_count(),
            python_version=platform.python_version(),
            platform_string=platform.platform(),
            machine_id=_get_machine_id(),
        )

    def get_provider_id(self) -> UUID:
        """Stable identifier for this machine's collector."""
        return self._provider_id

    def get_description(self) -> str:
        return (
            "Machine configuration collector "
            "— gathers platform identity and capabilities"
        )


# ── Recorder ──────────────────────────────────────────────────────


class MachineConfigRecorder(RecorderBase[MachineConfigData]):
    """Normalizes machine config into a tensor and stores it.

    Creates a two-strand tensor: platform identity (hostname, FQDN,
    machine ID) and system configuration (OS, arch, CPUs, Python).
    """

    def __init__(self, interface: ApachetaInterface) -> None:
        super().__init__(interface)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.recorder.machine_config",
        )

    def record(self, envelope: WranglerEnvelope[MachineConfigData]) -> UUID:
        """Create a tensor from the machine config and store it."""
        data = envelope.data

        identity_strand = StrandRecord(
            strand_index=0,
            title="Platform Identity",
            content=(
                f"hostname: {data.hostname}\n"
                f"fqdn: {data.fqdn}\n"
                f"machine_id: {data.machine_id}"
            ),
            topics=("machine-config", "identity"),
        )

        system_strand = StrandRecord(
            strand_index=1,
            title="System Configuration",
            content=(
                f"os: {data.os_name} {data.os_release}\n"
                f"kernel: {data.os_version}\n"
                f"architecture: {data.architecture}\n"
                f"cpu_count: {data.cpu_count}\n"
                f"python: {data.python_version}"
            ),
            topics=("machine-config", "system"),
        )

        content_tag = f"content:{self._content_hash(data)}"
        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                source=SourceIdentifier(
                    identifier=envelope.provider_id,
                    description="Machine configuration collector",
                ),
                author_model_family="collector",
            ),
            preamble=f"Machine configuration snapshot from {data.hostname}",
            strands=(identity_strand, system_strand),
            lineage_tags=("machine-config", content_tag),
        )

        self.interface.store_tensor(tensor)
        return tensor.id

    def get_recorder_id(self) -> UUID:
        """Stable identifier for the machine config recorder."""
        return self._recorder_id

    def get_description(self) -> str:
        return (
            "Machine configuration recorder "
            "— stores platform snapshots as tensors"
        )


# ── Convenience Functions ─────────────────────────────────────────


def collect_machine_config() -> MachineConfigData:
    """Collect machine configuration without recording it.

    Creates a throwaway collector, gathers the data, returns it.
    Useful for CLI display or testing without a storage backend.
    """
    collector = MachineConfigCollector()
    return collector.collect()


def collect_and_record(interface: ApachetaInterface) -> UUID:
    """Full pipeline: collect → wrangle → record.

    Wires a MachineConfigCollector through a DirectWrangler to a
    MachineConfigRecorder. Returns the UUID of the stored tensor.
    """
    collector = MachineConfigCollector()
    wrangler: DirectWrangler[MachineConfigData] = DirectWrangler()
    recorder = MachineConfigRecorder(interface)

    data = collector.collect()
    envelope: WranglerEnvelope[MachineConfigData] = WranglerEnvelope(
        data=data,
        provider_id=collector.get_provider_id(),
    )

    wrangler.deliver(envelope)
    received = wrangler.receive()
    if received is None:
        msg = "DirectWrangler returned None — this should not happen"
        raise RuntimeError(msg)

    return recorder.record(received)


def render_machine_config(data: MachineConfigData) -> str:
    """Render machine configuration as a human-readable string.

    Aligned label/value pairs, suitable for CLI output or logging.
    """
    return (
        f"  Hostname:    {data.hostname}\n"
        f"  FQDN:        {data.fqdn}\n"
        f"  Machine ID:  {data.machine_id}\n"
        f"  OS:          {data.os_name} {data.os_release}\n"
        f"  Kernel:      {data.os_version}\n"
        f"  Arch:        {data.architecture}\n"
        f"  CPUs:        {data.cpu_count}\n"
        f"  Python:      {data.python_version}\n"
        f"  Platform:    {data.platform_string}\n"
        f"  Collected:   {data.collected_at.isoformat()}"
    )
