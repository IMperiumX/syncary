import os
import shutil
from core.connectors.file_sync_interface import (
    FileSyncInterface,
    FileSynchronizationError,
)


class LocalFileConnector(FileSyncInterface):
    """Implementation of FileSyncInterface for local file system."""

    def get_file_list(self, path):
        """Returns a list of files and folders at the given path."""
        try:
            entries = []
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                entry_type = "folder" if os.path.isdir(full_path) else "file"
                entries.append({"name": entry, "type": entry_type})
            return entries
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise FileSynchronizationError(f"Error listing path '{path}': {e}")

    def download_file(self, remote_path, local_path):
        """Downloads a file (in this case, copies it)."""
        try:
            shutil.copy2(remote_path, local_path)
        except (FileNotFoundError, PermissionError, IsADirectoryError, OSError) as e:
            raise FileSynchronizationError(
                f"Error downloading from '{remote_path}' to '{local_path}': {e}"
            )

    def upload_file(self, local_path, remote_path):
        """Uploads a file (in this case, copies it)."""
        try:
            shutil.copy2(local_path, remote_path)
        except (FileNotFoundError, PermissionError, IsADirectoryError, OSError) as e:
            raise FileSynchronizationError(
                f"Error uploading from '{local_path}' to '{remote_path}': {e}"
            )

    def delete_file(self, path):
        """Deletes a file."""
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)  # Remove directory recursively
            else:
                os.remove(path)
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise FileSynchronizationError(f"Error deleting path '{path}': {e}")

    def create_folder(self, path):
        """Creates a folder."""
        try:
            os.makedirs(path, exist_ok=True)  # Create directory recursively if needed
        except (FileExistsError, PermissionError, OSError) as e:
            raise FileSynchronizationError(f"Error creating folder '{path}': {e}")
