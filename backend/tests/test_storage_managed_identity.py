"""Tests for Task C2a — Storage adapter Managed Identity support.

Covers the auth-mode branch logic in AzureBlobStorageService.__init__:

  - AZURE_STORAGE_ACCOUNT_URL set → DefaultAzureCredential path (MI).
  - AZURE_STORAGE_ACCOUNT_URL unset → connection-string fallback.
  - Neither set → RuntimeError on init.
  - URL takes precedence even when both are set (defense in depth).

The actual Azure SDK calls are mocked — we only verify the adapter picks
the right BlobServiceClient constructor and labels itself with the right
auth mode. End-to-end blob I/O is exercised on the live deployment after
terraform apply, not here.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.storage import azure_adapter as adapter_mod


@pytest.fixture
def patched_settings():
    """Patch the settings object the adapter imported so we can flip the
    auth-mode inputs per test. Restores the originals on teardown."""
    original = {
        "azure_storage_account_url": adapter_mod.settings.azure_storage_account_url,
        "azure_storage_connection_string": adapter_mod.settings.azure_storage_connection_string,
        "azure_storage_container": adapter_mod.settings.azure_storage_container,
    }

    def _set(**overrides):
        for k, v in overrides.items():
            setattr(adapter_mod.settings, k, v)

    yield _set

    for k, v in original.items():
        setattr(adapter_mod.settings, k, v)


class TestAuthModeSelection:
    def test_mi_path_when_account_url_set(self, patched_settings):
        patched_settings(
            azure_storage_account_url="https://example.blob.core.windows.net/",
            azure_storage_connection_string=None,
            azure_storage_container="art-images",
        )
        with patch.object(adapter_mod, "BlobServiceClient") as MockClient, \
             patch.object(adapter_mod, "DefaultAzureCredential") as MockCred:
            MockClient.return_value = MagicMock()
            MockCred.return_value = MagicMock(name="cred-instance")

            svc = adapter_mod.AzureBlobStorageService()

            # MI constructor was used, not from_connection_string.
            MockClient.assert_called_once()
            call_kwargs = MockClient.call_args.kwargs
            assert call_kwargs["account_url"] == "https://example.blob.core.windows.net/"
            assert call_kwargs["credential"] is MockCred.return_value
            MockClient.from_connection_string.assert_not_called()
            assert svc._auth_mode == "managed_identity"

    def test_connection_string_fallback_when_url_unset(self, patched_settings):
        patched_settings(
            azure_storage_account_url=None,
            azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x;AccountKey=k;EndpointSuffix=core.windows.net",
            azure_storage_container="art-images",
        )
        with patch.object(adapter_mod, "BlobServiceClient") as MockClient, \
             patch.object(adapter_mod, "DefaultAzureCredential") as MockCred:
            MockClient.from_connection_string.return_value = MagicMock()

            svc = adapter_mod.AzureBlobStorageService()

            # Connection-string constructor was used; MI was not.
            MockClient.from_connection_string.assert_called_once_with(
                "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=k;EndpointSuffix=core.windows.net"
            )
            MockClient.assert_not_called()
            MockCred.assert_not_called()
            assert svc._auth_mode == "connection_string"

    def test_url_wins_over_connection_string_when_both_set(self, patched_settings):
        """Defence in depth: if both are present, MI wins. Prevents accidental
        regression to shared-key auth after C2b removes the connection string."""
        patched_settings(
            azure_storage_account_url="https://example.blob.core.windows.net/",
            azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x;AccountKey=k;EndpointSuffix=core.windows.net",
            azure_storage_container="art-images",
        )
        with patch.object(adapter_mod, "BlobServiceClient") as MockClient, \
             patch.object(adapter_mod, "DefaultAzureCredential") as MockCred:
            MockClient.return_value = MagicMock()
            MockCred.return_value = MagicMock()

            svc = adapter_mod.AzureBlobStorageService()

            MockClient.assert_called_once()
            MockClient.from_connection_string.assert_not_called()
            assert svc._auth_mode == "managed_identity"

    def test_runtime_error_when_neither_set(self, patched_settings):
        patched_settings(
            azure_storage_account_url=None,
            azure_storage_connection_string=None,
            azure_storage_container="art-images",
        )
        with patch.object(adapter_mod, "BlobServiceClient"), \
             patch.object(adapter_mod, "DefaultAzureCredential"):
            with pytest.raises(RuntimeError, match="AZURE_STORAGE_ACCOUNT_URL"):
                adapter_mod.AzureBlobStorageService()


class TestSettingsField:
    """Lock down the new config field so a future edit can't silently rename
    it back to the connection-string-only world."""

    def test_azure_storage_account_url_field_exists(self):
        from app.config import Settings
        # Field is declared on the model, defaults to None.
        assert "azure_storage_account_url" in Settings.model_fields
        field = Settings.model_fields["azure_storage_account_url"]
        assert field.default is None

    def test_azure_storage_account_url_reads_env(self, monkeypatch):
        monkeypatch.setenv(
            "AZURE_STORAGE_ACCOUNT_URL",
            "https://example.blob.core.windows.net/",
        )
        from app.config import Settings
        s = Settings(_env_file=None)
        assert s.azure_storage_account_url == "https://example.blob.core.windows.net/"
