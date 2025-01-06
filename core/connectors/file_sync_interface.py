import abc


class FileSynchronizationError(Exception):
    """A custom exception for file synchronization errors."""

    pass


class FileSyncInterface(abc.ABC):
    """Interface for file synchronization operations."""

    @abc.abstractmethod
    def get_file_list(self, path):
        """Returns a list of files and folders at the given path.

        Args:
            path: The path to list.

        Returns:
            A list of dictionaries, where each dictionary represents a file or folder
            and contains the keys "name" (str) and "type" ("file" or "folder").

        Raises:
            FileSynchronizationError: If there is an error listing the path.
        """
        pass

    @abc.abstractmethod
    def download_file(self, remote_path, local_path):
        """Downloads a file from the remote path to the local path.

        Args:
            remote_path: The path to the remote file.
            local_path: The path to save the local file.

        Raises:
            FileSynchronizationError: If there is an error downloading the file.
        """
        pass

    @abc.abstractmethod
    def upload_file(self, local_path, remote_path):
        """Uploads a file from the local path to the remote path.

        Args:
            local_path: The path to the local file.
            remote_path: The path to save the remote file.

        Raises:
            FileSynchronizationError: If there is an error uploading the file.
        """
        pass

    @abc.abstractmethod
    def delete_file(self, path):
        """Deletes a file at the given path.

        Args:
            path: The path to the file.

        Raises:
            FileSynchronizationError: If there is an error deleting the file.
        """
        pass

    @abc.abstractmethod
    def create_folder(self, path):
        """Creates a folder at the given path.

        Args:
            path: The path to the new folder.

        Raises:
            FileSynchronizationError: If there is an error creating the folder.
        """
        pass
