import pytest

from app.credentials import crypto
from app.credentials.service import CredentialService


def test_encrypt_decrypt_round_trip():
    ciphertext = crypto.encrypt("hunter2")
    assert ciphertext != b"hunter2"
    assert crypto.decrypt(ciphertext) == "hunter2"


def test_ciphertext_does_not_contain_plaintext():
    secret = "SuperSecretPassword!"
    ciphertext = crypto.encrypt(secret)
    assert secret.encode() not in ciphertext


@pytest.mark.asyncio
async def test_ssh_profile_round_trip(db_session):
    service = CredentialService(db_session)
    profile = await service.create_ssh_profile(
        name="test-profile", username="admin", password="secret123", enable_password="enable456"
    )
    resolved = service.resolve_ssh(profile)
    assert resolved.username == "admin"
    assert resolved.password == "secret123"
    assert resolved.enable_password == "enable456"


@pytest.mark.asyncio
async def test_snmp_profile_round_trip(db_session):
    service = CredentialService(db_session)
    profile = await service.create_snmp_profile(name="snmp-ro", community="public123")
    resolved = service.resolve_snmp(profile)
    assert resolved.community == "public123"
    assert resolved.version == "v2c"


@pytest.mark.asyncio
async def test_credential_list_never_exposes_secrets(db_session):
    service = CredentialService(db_session)
    await service.create_ssh_profile(name="p1", username="admin", password="secret")
    profiles = await service.list_all()
    assert len(profiles) == 1
    # The ORM object itself only exposes the encrypted blob, never plaintext
    assert profiles[0].encrypted_password != b"secret"
