"""
Unit tests for version management module.
Tests version information, update checking, and notifications.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_ha_control.app.version import (
    UpdateInfo,
    UpdateStatus,
    VersionInfo,
    VersionManager,
    get_version,
    get_version_info,
    check_for_updates,
)


# ============================================================================
# VersionInfo Tests
# ============================================================================


class TestVersionInfo:
    """Tests for VersionInfo."""
    
    def test_version_info_creation(self):
        """Test VersionInfo creation."""
        version_info = VersionInfo(
            version="3.8.0",
            build_date="2026-11-11T15:00:00Z",
            git_commit="abc123",
            git_branch="main",
            is_dev=False,
            changelog=["Feature 1", "Feature 2"],
            features=["Feature A", "Feature B"]
        )
        
        assert version_info.version == "3.8.0"
        assert version_info.build_date == "2026-11-11T15:00:00Z"
        assert version_info.git_commit == "abc123"
        assert version_info.git_branch == "main"
        assert not version_info.is_dev
    
    def test_version_info_to_dict(self):
        """Test VersionInfo to_dict method."""
        version_info = VersionInfo(
            version="3.8.0",
            build_date="2026-11-11T15:00:00Z"
        )
        
        result = version_info.to_dict()
        
        assert result["version"] == "3.8.0"
        assert result["build_date"] == "2026-11-11T15:00:00Z"
    
    def test_version_info_str(self):
        """Test VersionInfo string representation."""
        version_info = VersionInfo(
            version="3.8.0",
            build_date="2026-11-11T15:00:00Z"
        )
        
        result = str(version_info)
        
        assert "3.8.0" in result
        assert "2026-11-11T15:00:00Z" in result


# ============================================================================
# UpdateInfo Tests
# ============================================================================


class TestUpdateInfo:
    """Tests for UpdateInfo."""
    
    def test_update_info_creation(self):
        """Test UpdateInfo creation."""
        update_info = UpdateInfo(
            current_version="3.7.0",
            latest_version="3.8.0",
            status=UpdateStatus.UPDATE_AVAILABLE,
            changelog=["New feature"],
            download_url="https://example.com/download",
            release_date="2026-11-11",
            is_major=False,
            is_minor=True,
            is_patch=False
        )
        
        assert update_info.current_version == "3.7.0"
        assert update_info.latest_version == "3.8.0"
        assert update_info.status == UpdateStatus.UPDATE_AVAILABLE
        assert update_info.is_minor
    
    def test_update_info_to_dict(self):
        """Test UpdateInfo to_dict method."""
        update_info = UpdateInfo(
            current_version="3.7.0",
            latest_version="3.8.0",
            status=UpdateStatus.UPDATE_AVAILABLE
        )
        
        result = update_info.to_dict()
        
        assert result["current_version"] == "3.7.0"
        assert result["latest_version"] == "3.8.0"
        assert result["status"] == "update_available"


# ============================================================================
# VersionManager Tests
# ============================================================================


class TestVersionManager:
    """Tests for VersionManager."""
    
    def test_get_version_from_file(self):
        """Test loading version from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "version": "3.8.0",
                "build_date": "2026-11-11T15:00:00Z",
                "git_commit": "abc123",
                "git_branch": "main",
                "is_dev": False
            }, f)
            temp_file = f.name
        
        try:
            manager = VersionManager()
            manager.VERSION_FILE = temp_file
            
            version_info = manager._load_version_info()
            
            assert version_info.version == "3.8.0"
            assert version_info.build_date == "2026-11-11T15:00:00Z"
        finally:
            os.unlink(temp_file)
    
    def test_get_version_from_env(self):
        """Test loading version from environment variables."""
        with patch.dict(os.environ, {
            "JARVIS_VERSION": "3.8.0",
            "JARVIS_BUILD_DATE": "2026-11-11T15:00:00Z",
            "JARVIS_GIT_COMMIT": "abc123",
            "JARVIS_GIT_BRANCH": "main",
            "JARVIS_DEV": "false"
        }):
            manager = VersionManager()
            manager.VERSION_FILE = "nonexistent.json"
            
            version_info = manager._load_version_info()
            
            assert version_info.version == "3.8.0"
            assert version_info.build_date == "2026-11-11T15:00:00Z"
    
    def test_compare_versions_major_update(self):
        """Test version comparison for major update."""
        manager = VersionManager()
        
        status, is_major, is_minor, is_patch = manager._compare_versions(
            "3.7.0",
            "4.0.0"
        )
        
        assert status == UpdateStatus.UPDATE_REQUIRED
        assert is_major
        assert not is_minor
        assert not is_patch
    
    def test_compare_versions_minor_update(self):
        """Test version comparison for minor update."""
        manager = VersionManager()
        
        status, is_major, is_minor, is_patch = manager._compare_versions(
            "3.7.0",
            "3.8.0"
        )
        
        assert status == UpdateStatus.UPDATE_AVAILABLE
        assert not is_major
        assert is_minor
        assert not is_patch
    
    def test_compare_versions_patch_update(self):
        """Test version comparison for patch update."""
        manager = VersionManager()
        
        status, is_major, is_minor, is_patch = manager._compare_versions(
            "3.7.0",
            "3.7.1"
        )
        
        assert status == UpdateStatus.UPDATE_AVAILABLE
        assert not is_major
        assert not is_minor
        assert is_patch
    
    def test_compare_versions_up_to_date(self):
        """Test version comparison when up to date."""
        manager = VersionManager()
        
        status, is_major, is_minor, is_patch = manager._compare_versions(
            "3.8.0",
            "3.8.0"
        )
        
        assert status == UpdateStatus.UP_TO_DATE
        assert not is_major
        assert not is_minor
        assert not is_patch
    
    def test_compare_versions_error(self):
        """Test version comparison with invalid versions."""
        manager = VersionManager()
        
        status, is_major, is_minor, is_patch = manager._compare_versions(
            "invalid",
            "3.8.0"
        )
        
        assert status == UpdateStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_check_for_updates_success(self):
        """Test update checking with successful response."""
        manager = VersionManager()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v3.8.0",
            "name": "3.8.0",
            "body": "New features\nBug fixes",
            "published_at": "2026-11-11T15:00:00Z",
            "assets": [{"browser_download_url": "https://example.com/download"}]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            update_info = await manager.check_for_updates()
            
            assert update_info is not None
            assert update_info.latest_version == "3.8.0"
    
    @pytest.mark.asyncio
    async def test_check_for_updates_error(self):
        """Test update checking with error response."""
        manager = VersionManager()
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            update_info = await manager.check_for_updates()
            
            assert update_info.status == UpdateStatus.ERROR
    
    def test_generate_update_notification_major(self):
        """Test update notification for major update."""
        manager = VersionManager()
        manager._update_info = UpdateInfo(
            current_version="3.7.0",
            latest_version="4.0.0",
            status=UpdateStatus.UPDATE_REQUIRED,
            changelog=["Feature 1", "Feature 2"],
            is_major=True
        )
        
        notification = manager.generate_update_notification()
        
        assert notification is not None
        assert "4.0.0" in notification
        assert "MAJEURE" in notification
    
    def test_generate_update_notification_up_to_date(self):
        """Test update notification when up to date."""
        manager = VersionManager()
        manager._update_info = UpdateInfo(
            current_version="3.8.0",
            latest_version="3.8.0",
            status=UpdateStatus.UP_TO_DATE
        )
        
        notification = manager.generate_update_notification()
        
        assert notification is None
    
    def test_create_version_file(self):
        """Test creating version file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = VersionManager()
            manager.VERSION_FILE = os.path.join(temp_dir, "version.json")
            
            manager.create_version_file("3.8.0", "2026-11-11T15:00:00Z")
            
            version_file = os.path.join(temp_dir, "version.json")
            assert os.path.exists(version_file)
            
            with open(version_file, 'r') as f:
                data = json.load(f)
            
            assert data["version"] == "3.8.0"
            assert data["build_date"] == "2026-11-11T15:00:00Z"


# ============================================================================
# Global Function Tests
# ============================================================================


class TestGlobalFunctions:
    """Tests for global version functions."""
    
    def test_get_version(self):
        """Test get_version function."""
        version = get_version()
        
        assert isinstance(version, str)
        assert len(version) > 0
    
    def test_get_version_info(self):
        """Test get_version_info function."""
        version_info = get_version_info()
        
        assert isinstance(version_info, VersionInfo)
        assert version_info.version is not None
    
    @pytest.mark.asyncio
    async def test_check_for_updates(self):
        """Test check_for_updates function."""
        update_info = await check_for_updates()
        
        # This may return None or an UpdateInfo depending on network
        assert update_info is None or isinstance(update_info, UpdateInfo)
