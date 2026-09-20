from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import CredentialProfileCreate, CredentialProfileOut
from app.credentials.crypto import EncryptionNotConfigured
from app.credentials.service import CredentialService

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.get("", response_model=list[CredentialProfileOut])
async def list_credentials(session: AsyncSession = Depends(get_db)) -> list:
    return await CredentialService(session).list_all()


@router.post("", response_model=CredentialProfileOut, status_code=201)
async def create_credential(body: CredentialProfileCreate, session: AsyncSession = Depends(get_db)):
    service = CredentialService(session)
    try:
        if body.protocol == "ssh":
            return await service.create_ssh_profile(
                name=body.name,
                username=body.username or "",
                password=body.password,
                enable_password=body.enable_password,
                private_key=body.private_key,
            )
        elif body.protocol == "snmp":
            return await service.create_snmp_profile(
                name=body.name, version=body.snmp_version, community=body.snmp_community, username=body.username
            )
        raise HTTPException(status_code=400, detail="protocol must be 'ssh' or 'snmp'")
    except EncryptionNotConfigured as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{profile_id}", status_code=204)
async def delete_credential(profile_id: str, session: AsyncSession = Depends(get_db)) -> None:
    deleted = await CredentialService(session).delete(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No credential profile with id {profile_id}")
