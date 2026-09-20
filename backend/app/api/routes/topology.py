from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import TopologyEdgeOut, TopologyGraphOut, TopologyNodeOut
from app.topology.service import TopologyService

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("", response_model=TopologyGraphOut)
async def get_topology(
    device_type: str | None = None,
    vendor: str | None = None,
    online_only: bool = False,
    session: AsyncSession = Depends(get_db),
) -> TopologyGraphOut:
    service = TopologyService(session)
    graph = await service.get_graph(device_type=device_type, vendor=vendor, online_only=online_only)
    return TopologyGraphOut(
        nodes=[TopologyNodeOut(**n.__dict__) for n in graph.nodes],
        edges=[TopologyEdgeOut(**e.__dict__) for e in graph.edges],
        generated_at=graph.generated_at,
    )
