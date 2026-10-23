from ipaddress import IPv4Address, IPv4Network

from app.services.task_operations import OperationConflict


def private_host(value: str) -> str:
    address = IPv4Address(value)
    trusted = (IPv4Network('10.0.0.0/8'), IPv4Network('172.16.0.0/12'), IPv4Network('192.168.0.0/16'))
    if not address.is_loopback and not any(address in network for network in trusted):
        raise OperationConflict('bind to an explicit loopback or trusted-LAN address; wildcard/public binds are prohibited')
    return str(address)
