import pytest

from app.discovery.scope import DiscoveryScope, InvalidScopeError


def test_valid_cidr_expands_to_hosts():
    scope = DiscoveryScope(["192.0.2.0/30"])
    hosts = scope.host_addresses()
    assert hosts == ["192.0.2.1", "192.0.2.2"]


def test_empty_scope_rejected():
    with pytest.raises(InvalidScopeError):
        DiscoveryScope([])


def test_garbage_cidr_rejected():
    with pytest.raises(InvalidScopeError):
        DiscoveryScope(["not-a-cidr"])


def test_oversized_scope_rejected_at_expansion_time():
    scope = DiscoveryScope(["10.0.0.0/8"])
    with pytest.raises(InvalidScopeError):
        scope.host_addresses()


def test_single_host_cidr():
    scope = DiscoveryScope(["192.0.2.5/32"])
    assert scope.host_addresses() == ["192.0.2.5"]
