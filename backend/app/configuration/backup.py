from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConfigurationBackup, Device


class ConfigBackupService:
    def __init__(self, session: AsyncSession, backup_dir: str) -> None:
        self.session = session
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup(
        self,
        *,
        device: Device,
        config_text: str,
        source: str,
        driver_type: str,
        operator: str,
        trigger: str = "manual",
    ) -> ConfigurationBackup:
        sha256 = hashlib.sha256(config_text.encode("utf-8")).hexdigest()
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        device_dir = self.backup_dir / device.id
        device_dir.mkdir(parents=True, exist_ok=True)
        file_path = device_dir / f"{source}_{timestamp}_{sha256[:12]}.cfg"
        file_path.write_text(config_text, encoding="utf-8")
        os.chmod(file_path, 0o600)  # backups may contain hashed secrets; keep them operator-only

        backup = ConfigurationBackup(
            device_id=device.id,
            source=source,
            driver_type=driver_type,
            operator=operator,
            file_path=str(file_path),
            sha256=sha256,
            byte_size=len(config_text.encode("utf-8")),
            trigger=trigger,
        )
        self.session.add(backup)
        await self.session.commit()
        await self.session.refresh(backup)
        return backup

    def read_backup_text(self, backup: ConfigurationBackup) -> str:
        return Path(backup.file_path).read_text(encoding="utf-8")
