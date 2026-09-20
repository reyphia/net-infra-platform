from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Connection, Device


@dataclass
class TopologyNode:
    id: str
    hostname: str | None
    management_ip: str
    device_type: str
    vendor: str | None
    management_state: str
    is_online: bool


@dataclass
class TopologyEdge:
    id: str
    source: str
    target: str
    source_interface: str | None
    target_interface: str | None
    discovery_methods: list[str]
    confidence: float


@dataclass
class TopologyGraph:
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    generated_at: str


class TopologyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_graph(
        self,
        *,
        device_type: str | None = None,
        vendor: str | None = None,
        online_only: bool = False,
    ) -> TopologyGraph:
        from datetime import datetime

        query = select(Device)
        if device_type:
            query = query.where(Device.device_type == device_type)
        if vendor:
            query = query.where(Device.vendor == vendor)
        if online_only:
            query = query.where(Device.is_online.is_(True))
        devices = (await self.session.execute(query)).scalars().all()
        device_ids = {d.id for d in devices}

        edge_rows = (await self.session.execute(select(Connection))).scalars().all()
        edges = [
            TopologyEdge(
                id=c.id,
                source=c.source_device_id,
                target=c.destination_device_id,
                source_interface=c.source_interface_name,
                target_interface=c.destination_interface_name,
                discovery_methods=c.discovery_methods,
                confidence=c.confidence,
            )
            for c in edge_rows
            if c.source_device_id in device_ids and c.destination_device_id in device_ids
        ]

        nodes = [
            TopologyNode(
                id=d.id,
                hostname=d.hostname,
                management_ip=d.management_ip,
                device_type=d.device_type,
                vendor=d.vendor,
                management_state=d.management_state,
                is_online=d.is_online,
            )
            for d in devices
        ]
        return TopologyGraph(nodes=nodes, edges=edges, generated_at=datetime.utcnow().isoformat())
