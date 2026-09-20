from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.credentials import crypto
from app.db.models import CredentialProfile


@dataclass
class ResolvedSSHCredential:
    username: str | None
    password: str | None
    enable_password: str | None
    private_key: str | None


@dataclass
class ResolvedSNMPCredential:
    version: str
    community: str | None
    username: str | None
    auth_protocol: str | None
    auth_key: str | None
    priv_protocol: str | None
    priv_key: str | None


class CredentialService:
    """Creates and resolves credential profiles.

    Plaintext secrets exist only transiently in memory while a connection is
    being established; they are never written to logs, never returned from
    list/get API responses, and never embedded in audit records.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_ssh_profile(
        self,
        *,
        name: str,
        username: str,
        password: str | None = None,
        enable_password: str | None = None,
        private_key: str | None = None,
    ) -> CredentialProfile:
        profile = CredentialProfile(
            name=name,
            protocol="ssh",
            username=username,
            encrypted_password=crypto.encrypt(password) if password else None,
            encrypted_enable_password=crypto.encrypt(enable_password) if enable_password else None,
            encrypted_ssh_private_key=crypto.encrypt(private_key) if private_key else None,
        )
        self.session.add(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def create_snmp_profile(
        self,
        *,
        name: str,
        version: str = "v2c",
        community: str | None = None,
        username: str | None = None,
        auth_protocol: str | None = None,
        auth_key: str | None = None,
        priv_protocol: str | None = None,
        priv_key: str | None = None,
    ) -> CredentialProfile:
        profile = CredentialProfile(
            name=name,
            protocol="snmp",
            username=username,
            snmp_version=version,
            snmp_v3_auth_protocol=auth_protocol,
            snmp_v3_priv_protocol=priv_protocol,
            encrypted_snmp_community=crypto.encrypt(community) if community else None,
            encrypted_snmp_v3_auth_key=crypto.encrypt(auth_key) if auth_key else None,
            encrypted_snmp_v3_priv_key=crypto.encrypt(priv_key) if priv_key else None,
        )
        self.session.add(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def get(self, profile_id: str) -> CredentialProfile | None:
        return await self.session.get(CredentialProfile, profile_id)

    async def list_all(self) -> list[CredentialProfile]:
        result = await self.session.execute(select(CredentialProfile))
        return list(result.scalars().all())

    async def delete(self, profile_id: str) -> bool:
        profile = await self.get(profile_id)
        if profile is None:
            return False
        await self.session.delete(profile)
        await self.session.commit()
        return True

    def resolve_ssh(self, profile: CredentialProfile) -> ResolvedSSHCredential:
        return ResolvedSSHCredential(
            username=profile.username,
            password=crypto.decrypt(profile.encrypted_password) if profile.encrypted_password else None,
            enable_password=(
                crypto.decrypt(profile.encrypted_enable_password) if profile.encrypted_enable_password else None
            ),
            private_key=(
                crypto.decrypt(profile.encrypted_ssh_private_key) if profile.encrypted_ssh_private_key else None
            ),
        )

    def resolve_snmp(self, profile: CredentialProfile) -> ResolvedSNMPCredential:
        return ResolvedSNMPCredential(
            version=profile.snmp_version or "v2c",
            community=(
                crypto.decrypt(profile.encrypted_snmp_community) if profile.encrypted_snmp_community else None
            ),
            username=profile.username,
            auth_protocol=profile.snmp_v3_auth_protocol,
            auth_key=(
                crypto.decrypt(profile.encrypted_snmp_v3_auth_key) if profile.encrypted_snmp_v3_auth_key else None
            ),
            priv_protocol=profile.snmp_v3_priv_protocol,
            priv_key=(
                crypto.decrypt(profile.encrypted_snmp_v3_priv_key) if profile.encrypted_snmp_v3_priv_key else None
            ),
        )
