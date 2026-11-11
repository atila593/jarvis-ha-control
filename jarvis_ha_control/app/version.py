"""
Version management for Jarvis HA Control.
Provides version information and update notifications.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UpdateStatus(Enum):
    """Update status."""
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    UPDATE_REQUIRED = "update_required"
    ERROR = "error"


@dataclass
class VersionInfo:
    """Version information."""
    version: str
    build_date: str
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    is_dev: bool = False
    changelog: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "build_date": self.build_date,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "is_dev": self.is_dev,
            "changelog": self.changelog,
            "features": self.features
        }
    
    def __str__(self) -> str:
        """String representation."""
        return f"Jarvis HA Control v{self.version} ({self.build_date})"


@dataclass
class UpdateInfo:
    """Update information."""
    current_version: str
    latest_version: str
    status: UpdateStatus
    changelog: List[str] = field(default_factory=list)
    download_url: Optional[str] = None
    release_date: Optional[str] = None
    is_major: bool = False
    is_minor: bool = False
    is_patch: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "status": self.status.value,
            "changelog": self.changelog,
            "download_url": self.download_url,
            "release_date": self.release_date,
            "is_major": self.is_major,
            "is_minor": self.is_minor,
            "is_patch": self.is_patch
        }


class VersionManager:
    """
    Manages version information and update checking.
    """
    
    VERSION_FILE = "version.json"
    GITHUB_REPO = "atila593/jarvis-ha-control"
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    
    def __init__(self):
        """Initialize version manager."""
        self._version_info: Optional[VersionInfo] = None
        self._update_info: Optional[UpdateInfo] = None
    
    def get_version(self) -> VersionInfo:
        """
        Get current version information.
        
        Returns:
            VersionInfo with current version details
        """
        if self._version_info is None:
            self._version_info = self._load_version_info()
        return self._version_info
    
    def _load_version_info(self) -> VersionInfo:
        """
        Load version information from file or environment.
        
        Returns:
            VersionInfo instance
        """
        # Try to load from version.json
        version_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            self.VERSION_FILE
        )
        
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                return VersionInfo(
                    version=data.get("version", "unknown"),
                    build_date=data.get("build_date", datetime.now().isoformat()),
                    git_commit=data.get("git_commit"),
                    git_branch=data.get("git_branch"),
                    is_dev=data.get("is_dev", False),
                    changelog=data.get("changelog", []),
                    features=data.get("features", [])
                )
            except Exception as e:
                logger.warning(f"Failed to load version from file: {e}")
        
        # Fallback to environment variables
        version = os.getenv("JARVIS_VERSION", "3.8.0")
        build_date = os.getenv("JARVIS_BUILD_DATE", datetime.now().isoformat())
        git_commit = os.getenv("JARVIS_GIT_COMMIT")
        git_branch = os.getenv("JARVIS_GIT_BRANCH")
        is_dev = os.getenv("JARVIS_DEV", "false").lower() == "true"
        
        return VersionInfo(
            version=version,
            build_date=build_date,
            git_commit=git_commit,
            git_branch=git_branch,
            is_dev=is_dev
        )
    
    async def check_for_updates(self) -> UpdateInfo:
        """
        Check for updates from GitHub.
        
        Returns:
            UpdateInfo with update status
        """
        current_version = self.get_version()
        
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get latest release from GitHub
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Jarvis-HA-Control"
                }
                
                response = await client.get(self.GITHUB_API_URL, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    latest_version = data.get("tag_name", "").lstrip("v")
                    
                    if not latest_version:
                        latest_version = data.get("name", "unknown")
                    
                    # Compare versions
                    status, is_major, is_minor, is_patch = self._compare_versions(
                        current_version.version,
                        latest_version
                    )
                    
                    changelog = data.get("body", "").split("\n")[:5]
                    release_date = data.get("published_at")
                    download_url = data.get("assets", [{}])[0].get("browser_download_url")
                    
                    self._update_info = UpdateInfo(
                        current_version=current_version.version,
                        latest_version=latest_version,
                        status=status,
                        changelog=changelog,
                        download_url=download_url,
                        release_date=release_date,
                        is_major=is_major,
                        is_minor=is_minor,
                        is_patch=is_patch
                    )
                    
                    return self._update_info
                else:
                    logger.warning(f"Failed to check updates: HTTP {response.status_code}")
                    return UpdateInfo(
                        current_version=current_version.version,
                        latest_version=current_version.version,
                        status=UpdateStatus.ERROR
                    )
        
        except Exception as e:
            logger.warning(f"Failed to check updates: {e}")
            return UpdateInfo(
                current_version=current_version.version,
                latest_version=current_version.version,
                status=UpdateStatus.ERROR
            )
    
    def _compare_versions(
        self,
        current: str,
        latest: str
    ) -> tuple[UpdateStatus, bool, bool, bool]:
        """
        Compare two version strings.
        
        Args:
            current: Current version
            latest: Latest version
            
        Returns:
            Tuple of (status, is_major, is_minor, is_patch)
        """
        try:
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]
            
            # Pad with zeros if needed
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(latest_parts) < 3:
                latest_parts.append(0)
            
            if latest_parts > current_parts:
                is_major = latest_parts[0] > current_parts[0]
                is_minor = not is_major and latest_parts[1] > current_parts[1]
                is_patch = not is_major and not is_minor and latest_parts[2] > current_parts[2]
                
                if is_major:
                    return UpdateStatus.UPDATE_REQUIRED, is_major, is_minor, is_patch
                else:
                    return UpdateStatus.UPDATE_AVAILABLE, is_major, is_minor, is_patch
            else:
                return UpdateStatus.UP_TO_DATE, False, False, False
        
        except Exception:
            return UpdateStatus.ERROR, False, False, False
    
    def get_update_info(self) -> Optional[UpdateInfo]:
        """
        Get cached update information.
        
        Returns:
            UpdateInfo or None if not checked yet
        """
        return self._update_info
    
    def generate_update_notification(self) -> Optional[str]:
        """
        Generate a notification message for available updates.
        
        Returns:
            Notification message or None if up to date
        """
        if self._update_info is None:
            return None
        
        if self._update_info.status == UpdateStatus.UP_TO_DATE:
            return None
        
        if self._update_info.status == UpdateStatus.ERROR:
            return "Erreur lors de la vérification des mises à jour"
        
        update_type = "MAJEURE" if self._update_info.is_major else \
                     "MINEURE" if self._update_info.is_minor else "CORRECTIVE"
        
        message = f"Nouvelle version {self._update_info.latest_version} disponible ({update_type})\n"
        
        if self._update_info.changelog:
            message += "Changements:\n"
            for change in self._update_info.changelog[:3]:
                message += f"- {change}\n"
        
        return message
    
    def create_version_file(self, version: str, build_date: str) -> None:
        """
        Create version.json file.
        
        Args:
            version: Version string
            build_date: Build date
        """
        version_data = {
            "version": version,
            "build_date": build_date,
            "git_commit": os.getenv("JARVIS_GIT_COMMIT"),
            "git_branch": os.getenv("JARVIS_GIT_BRANCH"),
            "is_dev": os.getenv("JARVIS_DEV", "false").lower() == "true",
            "changelog": [],
            "features": []
        }
        
        version_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            self.VERSION_FILE
        )
        
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)


# Global version manager instance
version_manager = VersionManager()


def get_version() -> str:
    """
    Get current version string.
    
    Returns:
        Version string
    """
    return version_manager.get_version().version


def get_version_info() -> VersionInfo:
    """
    Get complete version information.
    
    Returns:
        VersionInfo instance
    """
    return version_manager.get_version()


async def check_for_updates() -> Optional[UpdateInfo]:
    """
    Check for updates.
    
    Returns:
        UpdateInfo or None
    """
    return await version_manager.check_for_updates()
