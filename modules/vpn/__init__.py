"""
VPN module for optional WireGuard VPN support.
"""

from modules.vpn.manager import (
    get_vpn_manager,
    ensure_vpn_connected,
    disconnect_vpn,
    get_vpn_status
)

__all__ = [
    "get_vpn_manager",
    "ensure_vpn_connected",
    "disconnect_vpn",
    "get_vpn_status"
]

