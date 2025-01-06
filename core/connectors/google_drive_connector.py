import os
import io
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from core.connectors.file_sync_interface import FileSyncInterface, FileSynchronizationError

SCOPES = ["https://www.googleapis.com/auth/drive"]

class GoogleDriveConnector(FileSyncInterface):
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.credentials = self._load_credentials()
        self.service = build("drive", "v3", credentials=self.credentials)

    def _load_credentials(self):
        """Loads credentials from the config file or initiates the OAuth flow."""
        credentials = None
        token_path = "token.pickle"  # Store token in a local file

        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                credentials = flow.run_local_server(port=0)

            with open(token_path, "wb") as token:
                pickle.dump(credentials, token)

        return credentials

    def _get_folder_id_by_path(self, path):
        """Gets the Google Drive folder ID from a path.

        Args:
            path: The path to the folder (e.g., "My Drive/Folder/Subfolder").

        Returns:
            The folder ID (str) or None if not found.
        """
        folder_id = "root"  # Start at the root
        path_parts = path.split("/")

        for part in path_parts:
            if not part:
                continue  # Skip empty parts

            query = (
                f"name = '{part}' and '{folder_id}' in parents and "
                "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            )
            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=10,
                    fields="nextPageToken, files(id, name)",
                )
                .execute()
            )
            items = results.get("files", [])

            if not items:
                return None  # Folder not found

            folder_id = items[0]["id"]

        return folder_id

    def get_file_list(self, path):
        """Returns a list of files and folders at the given path."""
        folder_id = self._get_folder_id_by_path(path)
        if folder_id is None:
            raise FileSynchronizationError(f"Google Drive path not found: {path}")

        results = (
            self.service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType)",
            )
            .execute()
        )
        items = results.get("files", [])

        entries = []
        for item in items:
            entry_type = (
                "folder"
                if item["mimeType"] == "application/vnd.google-apps.folder"
                else "file"
            )
            entries.append({"name": item["name"], "type": entry_type, "id": item["id"]})

        return entries

    def download_file(self, remote_path, local_path):
        """Downloads a file from Google Drive to the local path."""
        file_id = self._get_file_id_by_path(remote_path)
        if file_id is None:
            raise FileSynchronizationError(f"File not found in Google Drive: {remote_path}")

        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

        with open(local_path, "wb") as f:
            f.write(fh.getvalue())

    def upload_file(self, local_path, remote_path):
        """Uploads a file from the local path to Google Drive."""
        folder_path, file_name = os.path.split(remote_path)
        folder_id = self._get_folder_id_by_path(folder_path)

        if folder_id is None:
            raise FileSynchronizationError(f"Destination folder not found in Google Drive: {folder_path}")

        file_metadata = {"name": file_name, "parents": [folder_id]}
        media = MediaFileUpload(local_path)

        try:
            file = self.service.files().create(body=file_metadata, media_body=media, fields="id").execute()
            print(f"Uploaded file with ID: {file.get('id')}")
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise FileSynchronizationError(f"Error uploading file to Google Drive: {error}")

    def delete_file(self, path):
        """Deletes a file or folder from Google Drive."""
        file_id = self._get_file_id_by_path(path)
        if file_id is None:
            raise FileSynchronizationError(f"File or folder not found in Google Drive: {path}")

        try:
            self.service.files().delete(fileId=file_id).execute()
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise FileSynchronizationError(f"Error deleting from Google Drive: {error}")

    def create_folder(self, path):
        """Creates a folder in Google Drive."""
        parent_path, folder_name = os.path.split(path)
        parent_id = self._get_folder_id_by_path(parent_path)

        if parent_id is None:
            raise FileSynchronizationError(f"Parent folder not found in Google Drive: {parent_path}")

        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }

        try:
            file = self.service.files().create(body=file_metadata, fields="id").execute()
            print(f"Created folder with ID: {file.get('id')}")
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise FileSynchronizationError(f"Error creating folder in Google Drive: {error}")

    def _get_file_id_by_path(self, path):
        """Gets the Google Drive file ID from a path.

        Args:
            path: The path to the file (e.g., "My Drive/Folder/file.txt").

        Returns:
            The file ID (str) or None if not found.
        """
        parent_folder, file_name = os.path.split(path)
        folder_id = self._get_folder_id_by_path(parent_folder)

        if folder_id is None:
            return None  # Folder not found

        query = f"name = '{file_name}' and '{folder_id}' in parents and trashed = false"
        results = (
            self.service.files()
            .list(
                q=query,
                pageSize=10,
                fields="nextPageToken, files(id, name)",
            )
            .execute()
        )
        items = results.get("files", [])

        if not items:
            return None  # File not found

        return items[0]["id"]
