import os
import shutil
import hashlib
import logging

import dropbox
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class SyncManager:
    def __init__(self):
        self.tasks = []
        self.logger = logging.getLogger(__name__)

    def add_task(self, source: str, destination: str, sync_type: str):
        self.tasks.append(
            {"source": source, "destination": destination, "sync_type": sync_type}
        )

    def sync_all(self):
        for task in self.tasks:
            if task["sync_type"] == "files":
                self._sync_files(task["source"], task["destination"])
            # Add other sync types here in the future

    def _sync_files(self, source: str, destination: str):
        if source.startswith("local://") and destination.startswith("local://"):
            self._sync_local_to_local(source[8:], destination[8:])
        elif source.startswith("local://") and destination.startswith("dropbox://"):
            self._sync_local_to_dropbox(source[8:], destination[10:])
        elif source.startswith("local://") and destination.startswith("gdrive://"):
            self._sync_local_to_gdrive(source[8:], destination[9:])
        else:
            self.logger.error(
                f"Unsupported sync combination: {source} to {destination}"
            )

    def _sync_local_to_local(self, source: str, destination: str):
        for root, _, files in os.walk(source):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, source)
                dst_path = os.path.join(destination, rel_path)

                if not os.path.exists(dst_path) or self._files_differ(
                    src_path, dst_path
                ):
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    self.logger.info(f"Synced {src_path} to {dst_path}")

    def _sync_local_to_dropbox(self, local_path: str, dropbox_path: str):
        dbx = dropbox.Dropbox("YOUR_DROPBOX_ACCESS_TOKEN")

        for root, _, files in os.walk(local_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_file_path, local_path)
                dropbox_file_path = f"{dropbox_path}/{rel_path}".replace("\\", "/")

                with open(local_file_path, "rb") as f:
                    file_content = f.read()
                    dbx.files_upload(
                        file_content,
                        dropbox_file_path,
                        mode=dropbox.files.WriteMode.overwrite,
                    )
                    self.logger.info(
                        f"Synced {local_file_path} to Dropbox: {dropbox_file_path}"
                    )

    def _sync_local_to_gdrive(self, local_path: str, gdrive_path: str):
        creds = Credentials.from_authorized_user_file(
            "token.json", ["https://www.googleapis.com/auth/drive.file"]
        )
        service = build("drive", "v3", credentials=creds)

        for root, _, files in os.walk(local_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_file_path, local_path)
                gdrive_file_path = f"{gdrive_path}/{rel_path}".replace("\\", "/")

                file_metadata = {
                    "name": os.path.basename(local_file_path),
                    "parents": [
                        self._get_or_create_folder(
                            service, os.path.dirname(gdrive_file_path)
                        )
                    ],
                }
                media = MediaFileUpload(local_file_path)
                file = (
                    service.files()
                    .create(body=file_metadata, media_body=media, fields="id")
                    .execute()
                )
                self.logger.info(
                    f"Synced {local_file_path} to Google Drive: {file.get('id')}"
                )

    def _files_differ(self, file1: str, file2: str) -> bool:
        return self._get_file_hash(file1) != self._get_file_hash(file2)

    def _get_file_hash(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5()
            chunk = f.read(8192)
            while chunk:
                file_hash.update(chunk)
                chunk = f.read(8192)
        return file_hash.hexdigest()

    def _get_or_create_folder(self, service, folder_path: str) -> str:
        # TODO: Implement logic to get or create a folder in Google Drive
        # Return the folder ID
        dropbox_path = folder_path
        return dropbox_path


# Usage example
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sync_manager = SyncManager()

    sync_manager.add_task(
        source="local:///home/USERNAME/Documents/SyncFolder",
        destination="local:///home/USERNAME/Backup/SyncFolder",
        sync_type="files",
    )

    sync_manager.add_task(
        source="local:///home/USERNAME/Documents/DropboxSync",
        destination="dropbox:///SyncFolder",
        sync_type="files",
    )

    sync_manager.add_task(
        source="local:///home/USERNAME/Documents/GoogleDriveSync",
        destination="gdrive:///SyncFolder",
        sync_type="files",
    )

    sync_manager.sync_all()
