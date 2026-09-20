from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.changes.service import ChangePlanService
from app.configuration.backup import ConfigBackupService
from app.core.config import Settings, get_settings
from app.credentials.service import CredentialService
from app.db.session import get_session
from app.discovery.engine import DiscoveryConfig
from app.monitoring.service import MonitoringService
from app.topology.service import TopologyService


async def get_db(session: AsyncSession = Depends(get_session)) -> AsyncIterator[AsyncSession]:
    yield session


def get_app_settings() -> Settings:
    return get_settings()


def get_audit_service(session: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(session)


def get_credential_service(session: AsyncSession = Depends(get_db)) -> CredentialService:
    return CredentialService(session)


def get_backup_service(
    session: AsyncSession = Depends(get_db), settings: Settings = Depends(get_app_settings)
) -> ConfigBackupService:
    return ConfigBackupService(session, settings.config_backup_dir)


def get_topology_service(session: AsyncSession = Depends(get_db)) -> TopologyService:
    return TopologyService(session)


def get_monitoring_service(session: AsyncSession = Depends(get_db)) -> MonitoringService:
    return MonitoringService(session)


def get_change_plan_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    credentials: CredentialService = Depends(get_credential_service),
    audit: AuditService = Depends(get_audit_service),
) -> ChangePlanService:
    backups = ConfigBackupService(session, settings.config_backup_dir)
    return ChangePlanService(
        session,
        backup_service=backups,
        credential_service=credentials,
        audit_service=audit,
        known_hosts_path=settings.ssh_known_hosts_path,
        allow_insecure_ssh=settings.ssh_allow_insecure_lab_mode,
    )


def default_discovery_config(settings: Settings) -> DiscoveryConfig:
    return DiscoveryConfig(
        timeout_seconds=settings.discovery_default_timeout_seconds,
        max_concurrency=settings.discovery_default_max_concurrency,
        retry_count=settings.discovery_default_retry_count,
        snmp_community=settings.snmp_default_community or None,
        snmp_port=settings.snmp_default_port,
    )
