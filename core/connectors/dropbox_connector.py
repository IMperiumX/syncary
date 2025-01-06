import dropbox
from contextlib import contextmanager
from core.connectors.file_sync_interface import (
    FileSyncInterface,
    FileSynchronizationError,
)


class DropboxConnector(FileSyncInterface):
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.dropbox_app_key = self.config_manager.get_config("dropbox_app_key")
        self.dropbox_app_secret = self.config_manager.get_config("dropbox_app_secret")
        self.dropbox_access_token = self.config_manager.get_config(
            "dropbox_access_token"
        )

        if self.dropbox_app_key is None or self.dropbox_app_secret is None:
            raise FileSynchronizationError(
                "Dropbox App Key and App Secret must be configured."
            )

        self.dbx = (
            dropbox.Dropbox(self.dropbox_access_token)
            if self.dropbox_access_token
            else None
        )

    def _ensure_dropbox_client(self):
        """Ensure that the Dropbox client is initialized."""
        if self.dbx is None:
            self.dropbox_access_token = self._get_dropbox_access_token()
            self.dbx = dropbox.Dropbox(self.dropbox_access_token)

    def _get_dropbox_access_token(self):
        """Guide the user through Dropbox OAuth flow and get the access token."""
        flow = dropbox.DropboxOAuth2FlowNoRedirect(
            self.dropbox_app_key, self.dropbox_app_secret
        )
        authorize_url = flow.start()

        print(f"1. Go to: {authorize_url}")
        print("2. Click 'Allow' (you might need to log in first).")
        print("3. Copy the authorization code.")
        auth_code = input("Enter the authorization code here: ").strip()

        try:
            oauth_result = flow.finish(auth_code)
            self.config_manager.set_config(
                "dropbox_access_token", oauth_result.access_token
            )
            return oauth_result.access_token
        except Exception as e:
            raise FileSynchronizationError(f"Error during Dropbox OAuth flow: {e}")

    def _format_path(self, path):
        """Format the path for Dropbox API calls."""
        return path if path.startswith("/") else "/" + path

    @contextmanager
    def _handle_dropbox_errors(self, message="Dropbox API error"):
        """Handle common Dropbox API errors."""
        try:
            yield
        except dropbox.exceptions.AuthError as e:
            self.config_manager.delete_config("dropbox_access_token")
            self.dbx = None
            raise FileSynchronizationError(
                f"{message}: Dropbox authentication error: {e}"
            )
        except dropbox.exceptions.BadInputError as e:
            raise FileSynchronizationError(f"{message}: Dropbox bad input error: {e}")
        except dropbox.exceptions.ApiError as e:
            raise FileSynchronizationError(f"{message}: {e.error}")
        except Exception as e:
            raise FileSynchronizationError(f"{message}: {e}")

    def get_file_list(self, path):
        """Returns a list of files and folders at the given path."""
        self._ensure_dropbox_client()
        formatted_path = self._format_path(path)
        entries = []

        with self._handle_dropbox_errors("Error listing Dropbox path"):
            result = self.dbx.files_list_folder(formatted_path, recursive=False)
            for entry in result.entries:
                entry_type = (
                    "folder"
                    if isinstance(entry, dropbox.files.FolderMetadata)
                    else "file"
                )
                entries.append({"name": entry.name, "type": entry_type})

        return entries

    def download_file(self, remote_path, local_path):
        """Downloads a file from Dropbox to the local path."""
        self._ensure_dropbox_client()
        formatted_remote_path = self._format_path(remote_path)

        with self._handle_dropbox_errors(
            f"Error downloading file from Dropbox: {remote_path}"
        ):
            metadata, response = self.dbx.files_download(formatted_remote_path)
            with open(local_path, "wb") as f:
                f.write(response.content)

    def upload_file(self, local_path, remote_path):
        """Uploads a file from the local path to Dropbox."""
        self._ensure_dropbox_client()
        formatted_remote_path = self._format_path(remote_path)

        with self._handle_dropbox_errors(
            f"Error uploading file to Dropbox: {remote_path}"
        ):
            with open(local_path, "rb") as f:
                file_data = f.read()
                self.dbx.files_upload(
                    file_data,
                    formatted_remote_path,
                    mode=dropbox.files.WriteMode.overwrite,
                )

    def delete_file(self, path):
        """Deletes a file or folder from Dropbox."""
        self._ensure_dropbox_client()
        formatted_path = self._format_path(path)

        with self._handle_dropbox_errors(f"Error deleting from Dropbox: {path}"):
            self.dbx.files_delete_v2(formatted_path)

    def create_folder(self, path):
        """Creates a folder in Dropbox."""
        self._ensure_dropbox_client()
        formatted_path = self._format_path(path)

        with self._handle_dropbox_errors(f"Error creating folder in Dropbox: {path}"):
            self.dbx.files_create_folder_v2(formatted_path)
