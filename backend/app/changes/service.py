"""Change management: PLAN -> VALIDATE -> PREVIEW -> CONFIRM(apply) -> VERIFY
-> optional ROLLBACK, executed against real devices through the driver
layer. Every device targeted by a plan gets its own ChangeExecution row, so
a batch operation across many devices has per-device success/failure, never
an all-or-nothing illusion.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.configuration.backup import ConfigBackupService
from app.configuration.diff import predict_applied_config, semantic_diff, semantic_diff_generic
from app.configuration.validation import validate_proposed_config
from app.credentials.service import CredentialService
from app.db.models import (
    ChangeExecution,
    ChangePlan,
    ChangePlanDevice,
    ChangePlanStatus,
    Device,
    ManagementMethod,
    RollbackStatus,
)
from app.drivers.base import DriverCommandError, DriverConnectionError, SSHCredential
from app.drivers.factory import create_driver

logger = logging.getLogger("app.changes")


class ChangePlanError(RuntimeError):
    pass


class ChangePlanService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        backup_service: ConfigBackupService,
        credential_service: CredentialService,
        audit_service: AuditService,
        known_hosts_path: str | None,
        allow_insecure_ssh: bool,
    ) -> None:
        self.session = session
        self.backups = backup_service
        self.credentials = credential_service
        self.audit = audit_service
        self.known_hosts_path = known_hosts_path
        self.allow_insecure_ssh = allow_insecure_ssh

    # ---------------------------------------------------------------- PLAN
    async def create_plan(
        self,
        *,
        name: str,
        operator: str,
        proposed_config: str,
        device_ids: list[str],
        save_after_apply: bool = False,
    ) -> ChangePlan:
        if not device_ids:
            raise ChangePlanError("A change plan must target at least one device.")
        plan = ChangePlan(
            name=name,
            operator=operator,
            proposed_config=proposed_config,
            save_after_apply=save_after_apply,
            status=ChangePlanStatus.DRAFT.value,
        )
        self.session.add(plan)
        await self.session.flush()
        for device_id in device_ids:
            self.session.add(ChangePlanDevice(plan_id=plan.id, device_id=device_id))
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def _plan_devices(self, plan_id: str) -> list[tuple[ChangePlanDevice, Device]]:
        rows = (
            await self.session.execute(
                select(ChangePlanDevice, Device)
                .join(Device, Device.id == ChangePlanDevice.device_id)
                .where(ChangePlanDevice.plan_id == plan_id)
            )
        ).all()
        return [(cpd, dev) for cpd, dev in rows]

    # ------------------------------------------------------------ VALIDATE
    async def validate_plan(self, plan_id: str) -> ChangePlan:
        plan = await self._require_plan(plan_id)
        proposed_lines = plan.proposed_config.splitlines()
        pairs = await self._plan_devices(plan_id)

        eligible_count = 0
        report: dict[str, dict] = {}
        for cpd, device in pairs:
            if ManagementMethod.SSH.value not in device.available_management_methods:
                cpd.eligible = False
                cpd.ineligibility_reason = "Device is not remotely manageable (no SSH access detected)."
            elif not device.driver_type or device.driver_type == "unsupported":
                cpd.eligible = False
                cpd.ineligibility_reason = f"No supported driver for this device (driver_type={device.driver_type!r})."
            else:
                validation = validate_proposed_config(proposed_lines, device.driver_type)
                if not validation.ok:
                    cpd.eligible = False
                    cpd.ineligibility_reason = "; ".join(i.message for i in validation.blocking_issues)
                else:
                    cpd.eligible = True
                    cpd.ineligibility_reason = None
                report[device.id] = {
                    "ok": validation.ok,
                    "issues": [asdict(i) for i in validation.issues],
                }
            if cpd.eligible:
                eligible_count += 1

        plan.validation_report = {
            "summary": {
                "total": len(pairs),
                "eligible": eligible_count,
                "ineligible": len(pairs) - eligible_count,
            },
            "per_device": report,
        }
        plan.status = ChangePlanStatus.VALIDATED.value if eligible_count > 0 else ChangePlanStatus.VALIDATION_FAILED.value
        await self.session.commit()
        await self.audit.record(
            operator=plan.operator,
            action="change_plan.validate",
            success=eligible_count > 0,
            detail=f"plan={plan.name} eligible={eligible_count}/{len(pairs)}",
        )
        await self.session.refresh(plan)
        return plan

    # -------------------------------------------------------------- PREVIEW
    async def preview_plan(self, plan_id: str) -> ChangePlan:
        plan = await self._require_plan(plan_id)
        if plan.status not in (ChangePlanStatus.VALIDATED.value,):
            raise ChangePlanError(f"Plan must be VALIDATED before preview (current status: {plan.status}).")

        proposed_lines = plan.proposed_config.splitlines()
        pairs = await self._plan_devices(plan_id)
        diff_report: dict[str, dict] = {}

        for cpd, device in pairs:
            if not cpd.eligible:
                continue
            try:
                current_config = await self._fetch_config(device, source="running")
            except (DriverConnectionError, DriverCommandError) as exc:
                cpd.eligible = False
                cpd.ineligibility_reason = f"Could not retrieve current config for preview: {exc}"
                continue

            if device.driver_type == "cisco_ios":
                predicted = predict_applied_config(current_config, proposed_lines)
                report = semantic_diff(current_config, predicted)
            else:
                # No block-merge predictor for RouterOS/generic yet; show the
                # proposed lines as a flat addition against current config.
                predicted = current_config + "\n" + "\n".join(proposed_lines)
                report = semantic_diff_generic(current_config, predicted)

            diff_report[device.id] = {
                "predicted": True,
                "note": "Predicted from current config + proposed lines; the authoritative diff is "
                "recomputed from the device after APPLY.",
                "raw_diff": report.raw_diff,
                "changes": [asdict(c) for c in report.changes],
                "categories_touched": report.categories_touched,
            }

        plan.diff_report = diff_report
        plan.status = ChangePlanStatus.PREVIEWED.value
        await self.session.commit()
        await self.audit.record(
            operator=plan.operator, action="change_plan.preview", success=True, detail=f"plan={plan.name}"
        )
        await self.session.refresh(plan)
        return plan

    # --------------------------------------------------------------- APPLY
    async def apply_plan(self, plan_id: str, *, confirmed_by: str) -> ChangePlan:
        """`confirmed_by` being supplied at all IS the explicit confirmation
        step -- the API layer requires the caller to re-submit the operator
        identity, so this can never be triggered as a side effect of
        validate/preview."""
        plan = await self._require_plan(plan_id)
        if plan.status != ChangePlanStatus.PREVIEWED.value:
            raise ChangePlanError(f"Plan must be PREVIEWED before it can be applied (current status: {plan.status}).")

        plan.status = ChangePlanStatus.APPLYING.value
        await self.session.commit()

        pairs = await self._plan_devices(plan_id)
        proposed_lines = plan.proposed_config.splitlines()
        any_failed = False
        any_applied = False

        for cpd, device in pairs:
            if not cpd.eligible:
                continue
            execution = ChangeExecution(plan_id=plan.id, device_id=device.id)
            self.session.add(execution)
            await self.session.flush()

            try:
                pre_backup = await self._backup_device(device, trigger="pre_change", operator=confirmed_by)
                if plan.pre_change_backup_id is None:
                    plan.pre_change_backup_id = pre_backup.id

                execution.apply_started_at = datetime.utcnow()
                driver = await self._connect(device)
                try:
                    result = await driver.apply_config(proposed_lines)
                    execution.apply_output = result.output
                    execution.apply_success = result.success
                    execution.apply_error = result.error

                    if result.success:
                        verified_config = await driver.get_config(source="running")
                        execution.verified = True  # apply reported success AND we could re-read config
                        execution.verification_detail = "Re-read running-config after apply; see post-change backup."
                        post_backup = await self.backups.create_backup(
                            device=device,
                            config_text=verified_config,
                            source="running",
                            driver_type=device.driver_type or "unknown",
                            operator=confirmed_by,
                            trigger="post_change",
                        )
                        if plan.post_change_backup_id is None:
                            plan.post_change_backup_id = post_backup.id

                        if plan.save_after_apply:
                            save_result = await driver.save_config()
                            if not save_result.success:
                                execution.apply_error = (execution.apply_error or "") + f" | save failed: {save_result.error}"
                    else:
                        any_failed = True
                finally:
                    await driver.disconnect()
                execution.apply_finished_at = datetime.utcnow()
                if execution.apply_success:
                    any_applied = True

                await self.audit.record(
                    operator=confirmed_by,
                    action="change_plan.apply",
                    success=bool(execution.apply_success),
                    device_id=device.id,
                    protocol="ssh",
                    detail=f"plan={plan.name} driver={device.driver_type}",
                    error=execution.apply_error,
                )
            except (DriverConnectionError, DriverCommandError) as exc:
                any_failed = True
                execution.apply_finished_at = datetime.utcnow()
                execution.apply_success = False
                execution.apply_error = str(exc)
                await self.audit.record(
                    operator=confirmed_by,
                    action="change_plan.apply",
                    success=False,
                    device_id=device.id,
                    protocol="ssh",
                    detail=f"plan={plan.name}",
                    error=str(exc),
                )

            await self.session.commit()

        plan.status = (
            ChangePlanStatus.APPLIED.value
            if any_applied and not any_failed
            else ChangePlanStatus.APPLY_FAILED.value
            if any_failed and not any_applied
            else ChangePlanStatus.VERIFIED.value
            if any_applied and any_failed
            else ChangePlanStatus.APPLY_FAILED.value
        )
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    # ------------------------------------------------------------ ROLLBACK
    async def rollback_execution(self, execution_id: str, *, operator: str) -> ChangeExecution:
        execution = await self.session.get(ChangeExecution, execution_id)
        if execution is None:
            raise ChangePlanError(f"No such change execution: {execution_id}")
        plan = await self.session.get(ChangePlan, execution.plan_id)
        device = await self.session.get(Device, execution.device_id)
        if plan is None or device is None:
            raise ChangePlanError("Change execution references a missing plan or device.")

        if not plan.pre_change_backup_id:
            execution.rollback_status = RollbackStatus.UNAVAILABLE.value
            execution.rollback_detail = "No pre-change backup was recorded for this plan; nothing to roll back to."
            await self.session.commit()
            return execution

        from app.db.models import ConfigurationBackup

        pre_backup = await self.session.get(ConfigurationBackup, plan.pre_change_backup_id)
        if pre_backup is None:
            execution.rollback_status = RollbackStatus.UNAVAILABLE.value
            execution.rollback_detail = "Pre-change backup record could not be found."
            await self.session.commit()
            return execution

        driver_cls_supports = device.driver_type == "cisco_ios"  # see NetworkDeviceDriver.supports_semantic_rollback
        if not driver_cls_supports:
            execution.rollback_status = RollbackStatus.UNAVAILABLE.value
            execution.rollback_detail = (
                f"Automatic rollback is not implemented for driver '{device.driver_type}'. "
                "Restore manually from the pre-change backup."
            )
            await self.session.commit()
            return execution

        pre_change_text = self.backups.read_backup_text(pre_backup)
        try:
            driver = await self._connect(device)
            try:
                current_text = await driver.get_config(source="running")
                report = semantic_diff(pre_change_text, current_text)
                inverse_lines: list[str] = []
                for change in report.changes:
                    if change.change_type == "added":
                        inverse_lines.append(f"no {change.entity}")
                    elif change.change_type == "modified":
                        inverse_lines.append(change.entity)
                        inverse_lines.extend(f"no {ln}" for ln in change.added_lines)
                        inverse_lines.extend(change.removed_lines)

                if not inverse_lines:
                    execution.rollback_status = RollbackStatus.SUCCESS.value
                    execution.rollback_detail = "Current config already matches the pre-change backup; nothing to do."
                    await self.session.commit()
                    return execution

                result = await driver.apply_config(inverse_lines)
                post_rollback_text = await driver.get_config(source="running")
                verify_report = semantic_diff(pre_change_text, post_rollback_text)

                if not result.success:
                    execution.rollback_status = RollbackStatus.FAILED.value
                    execution.rollback_detail = f"Rollback apply failed: {result.error}"
                elif not verify_report.changes:
                    execution.rollback_status = RollbackStatus.SUCCESS.value
                    execution.rollback_detail = "Verified: current config matches pre-change backup exactly."
                else:
                    execution.rollback_status = RollbackStatus.PARTIAL.value
                    execution.rollback_detail = (
                        f"Rollback applied but {len(verify_report.changes)} block(s) still differ from the "
                        "pre-change backup; manual review required."
                    )
            finally:
                await driver.disconnect()
        except (DriverConnectionError, DriverCommandError) as exc:
            execution.rollback_status = RollbackStatus.FAILED.value
            execution.rollback_detail = str(exc)

        await self.audit.record(
            operator=operator,
            action="change_plan.rollback",
            success=execution.rollback_status == RollbackStatus.SUCCESS.value,
            device_id=device.id,
            protocol="ssh",
            detail=f"execution={execution.id} status={execution.rollback_status}",
        )
        await self.session.commit()
        await self.session.refresh(execution)
        return execution

    # --------------------------------------------------------------- utils
    async def _require_plan(self, plan_id: str) -> ChangePlan:
        plan = await self.session.get(ChangePlan, plan_id)
        if plan is None:
            raise ChangePlanError(f"No such change plan: {plan_id}")
        return plan

    async def _connect(self, device: Device):  # noqa: ANN201 - returns a NetworkDeviceDriver subtype
        if not device.default_credential_profile_id:
            raise DriverConnectionError(
                f"No credential profile assigned to {device.management_ip}", reason="no_credentials", host=device.management_ip
            )
        profile = await self.credentials.get(device.default_credential_profile_id)
        if profile is None:
            raise DriverConnectionError(
                f"Credential profile for {device.management_ip} no longer exists",
                reason="no_credentials",
                host=device.management_ip,
            )
        resolved = self.credentials.resolve_ssh(profile)
        driver = create_driver(
            device.driver_type or "generic_ssh",
            device.management_ip,
            SSHCredential(
                username=resolved.username or "",
                password=resolved.password,
                enable_password=resolved.enable_password,
                private_key=resolved.private_key,
            ),
            known_hosts_path=self.known_hosts_path,
            allow_insecure=self.allow_insecure_ssh,
        )
        await driver.connect()
        return driver

    async def _fetch_config(self, device: Device, *, source: str) -> str:
        driver = await self._connect(device)
        try:
            return await driver.get_config(source=source)
        finally:
            await driver.disconnect()

    async def _backup_device(self, device: Device, *, trigger: str, operator: str):  # noqa: ANN201
        config_text = await self._fetch_config(device, source="running")
        return await self.backups.create_backup(
            device=device,
            config_text=config_text,
            source="running",
            driver_type=device.driver_type or "unknown",
            operator=operator,
            trigger=trigger,
        )
