"""
VPN Manager for optional WireGuard VPN support.
Uses zola-vpn package to route scraping traffic through VPN.

How It Works:
-----------
1. zola-vpn calls `wg-quick up` which creates a WireGuard interface at the system level
2. When WireGuard is connected, it routes ALL system network traffic through the VPN
3. This includes AsyncPRAW's aiohttp requests, as they use the system's network stack
4. For this to work, your WireGuard config MUST have: AllowedIPs = 0.0.0.0/0

Important:
----------
- WireGuard routes traffic at the OS level, not at the application level
- AsyncPRAW doesn't need special configuration - it automatically uses the VPN
- All network traffic from the container goes through the VPN when connected
- The VPN connection is persistent for the lifetime of the container
"""

import os
import subprocess
from typing import Optional, Any
from core.config import get_config
from core.logger import get_logger

logger = get_logger(__name__)

# Global VPN instance
_vpn_instance: Optional[Any] = None


def get_vpn_manager():
    """
    Get or create VPN manager instance.
    
    Returns:
        VPN manager if enabled, None otherwise
    """
    global _vpn_instance
    
    config = get_config()
    
    # If VPN is disabled, return None
    if not config.vpn_enabled:
        return None
    
    # If no config path, log warning and return None
    if not config.vpn_config_path:
        logger.warning("VPN is enabled but VPN_CONFIG_PATH is not set. VPN will not be used.")
        return None
    
    # Lazy import zola-vpn (optional dependency)
    try:
        from zola_vpn import VPNRequests
    except ImportError:
        logger.warning(
            "zola-vpn package not installed. Install with: "
            "pip install git+https://github.com/zxalif/zola-vpn.git#subdirectory=python"
        )
        return None
    
    # Create VPN instance if not exists
    if _vpn_instance is None:
        try:
            _vpn_instance = VPNRequests(
                config_path=config.vpn_config_path,
                auto_connect=True  # Auto-connect when making requests
            )
            logger.info(
                "Initialized VPN manager",
                config_path=config.vpn_config_path,
                auto_connect=True
            )
        except Exception as e:
            logger.error(
                "Failed to initialize VPN manager",
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    return _vpn_instance


def ensure_vpn_connected():
    """
    Ensure VPN is connected if enabled.
    This should be called before making scraping requests.
    
    Note: When WireGuard is connected via wg-quick, it routes ALL system traffic
    through the VPN interface. This means AsyncPRAW's requests will automatically
    go through the VPN, as long as the WireGuard config has:
    
        AllowedIPs = 0.0.0.0/0
    
    This routes all IPv4 traffic through the VPN. Without this, only specific
    IP ranges will be routed through the VPN.
    """
    vpn = get_vpn_manager()
    if vpn and not vpn.is_connected():
        try:
            success = vpn.connect()
            if success:
                logger.info("VPN connected for scraping")
                # Verify routing by checking IP (optional, but helpful for debugging)
                try:
                    current_ip = vpn.get_ip()
                    if current_ip:
                        logger.info(
                            "VPN routing verified",
                            current_ip=current_ip,
                            note="All system traffic (including AsyncPRAW) should now route through VPN"
                        )
                except Exception as ip_check_error:
                    logger.debug(
                        "Could not verify VPN IP (non-critical)",
                        error=str(ip_check_error)
                    )
            else:
                logger.warning("VPN connection failed, continuing without VPN")
        except Exception as e:
            logger.warning(
                "Failed to connect VPN, continuing without VPN",
                error=str(e)
            )


def disconnect_vpn():
    """
    Disconnect VPN if connected.
    This can be called when scraping is complete.
    """
    global _vpn_instance
    
    if _vpn_instance:
        try:
            if _vpn_instance.is_connected():
                _vpn_instance.disconnect()
                logger.info("VPN disconnected")
        except Exception as e:
            logger.warning("Error disconnecting VPN", error=str(e))
    
    # Don't reset _vpn_instance - keep it for reuse


def get_vpn_status() -> dict:
    """
    Get VPN connection status.
    
    Returns:
        Dictionary with VPN status information
    """
    config = get_config()
    
    if not config.vpn_enabled:
        return {
            "enabled": False,
            "connected": False,
            "message": "VPN is disabled"
        }
    
    if not config.vpn_config_path:
        return {
            "enabled": True,
            "connected": False,
            "message": "VPN enabled but config path not set"
        }
    
    vpn = get_vpn_manager()
    if not vpn:
        return {
            "enabled": True,
            "connected": False,
            "message": "VPN manager not available (zola-vpn not installed?)"
        }
    
    try:
        is_connected = vpn.is_connected()
        status = vpn.get_status() if is_connected else {}
        
        return {
            "enabled": True,
            "connected": is_connected,
            "config_path": config.vpn_config_path,
            "current_ip": status.get("current_ip") if is_connected else None,
            **status
        }
    except Exception as e:
        return {
            "enabled": True,
            "connected": False,
            "error": str(e)
        }

