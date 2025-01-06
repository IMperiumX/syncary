import abc
import hashlib
import os
from datetime import datetime

from core.connectors.dropbox_connector import DropboxConnector
from core.connectors.file_sync_interface import (
    FileSynchronizationError,
    FileSyncInterface,
)
from core.connectors.local_file_connector import LocalFileConnector
from core.connectors.google_drive_connector import GoogleDriveConnector

class SyncTask(abc.ABC):
    def __init__(self, source, destination, task_type, options=None, schedule=None):
        self.source = source
        self.destination = destination
        self.task_type = task_type
        self.options = options or {}
        self.schedule = schedule or {}  # Add schedule attribute

    @abc.abstractmethod
    def execute(self):
        """Executes the sync task."""
        pass

    def to_dict(self):
        """Converts the task object to a dictionary for serialization."""
        return {
            "source": self.source,
            "destination": self.destination,
            "task_type": self.task_type,
            "options": self.options,
            "schedule": self.schedule,
        }

    @staticmethod
    @abc.abstractmethod
    def from_dict(task_dict):
        """Creates a task object from a dictionary."""
        pass


class TaskManager:
    _instance = None

    def __new__(cls, config_manager):
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance.config_manager = config_manager
            cls._instance.tasks = []
            cls._instance.task_types = {}  # Registry for task types
            cls._instance.load_tasks()
        return cls._instance

    def register_task_type(self, task_type_name, task_class):
        """Registers a task type for serialization/deserialization."""
        self.task_types[task_type_name] = task_class

    def add_task(self, task: SyncTask):
        """Adds a task to the task list."""
        self.tasks.append(task)
        self.save_tasks()

    def remove_task(self, task: SyncTask):
        """Removes a task from the task list."""
        self.tasks.remove(task)
        self.save_tasks()

    def list_tasks(self):
        """Returns a list of all tasks."""
        return self.tasks

    def execute_all_tasks(self):
        """Executes all tasks in the task list."""
        for task in self.tasks:
            task.execute()

    def create_connector(self, destination):
        """Creates a connector instance based on the destination URI."""
        if destination.startswith("dropbox://"):
            return DropboxConnector(self.config_manager)
        elif destination.startswith("googledrive://"):
            return GoogleDriveConnector(self.config_manager)
        else:
            # Default to local file connector
            return LocalFileConnector()

    def load_tasks(self):
        """Loads tasks from the configuration file."""
        tasks_data = self.config_manager.get_config("tasks", [])
        self.tasks = []
        for task_dict in tasks_data:
            try:
                task_type = task_dict["task_type"]
                if task_type in self.task_types:
                    task_class = self.task_types[task_type]
                    # get the connector
                    connector = self.create_connector(task_dict["destination"])
                    # Include schedule when creating tasks
                    task = task_class.from_dict(task_dict, connector)
                    self.tasks.append(task)
                else:
                    print(f"Warning: Unknown task type '{task_type}'")
            except (KeyError, ValueError) as e:
                print(f"Error loading task: {e}")

    def save_tasks(self):
        """Saves the tasks to the configuration file."""
        tasks_data = [task.to_dict() for task in self.tasks]
        self.config_manager.set_config("tasks", tasks_data)
        self.config_manager.save_config()


class FileSyncTask(SyncTask):
    def __init__(
        self,
        source,
        destination,
        options=None,
        schedule=None,
        connector: FileSyncInterface = None,
    ):
        super().__init__(source, destination, "file_sync", options, schedule)
        self.connector = connector

    def execute(self):
        if self.connector is None:
            print("Error: FileSyncTask requires a connector.")
            return

        print(
            f"Syncing files from {self.source} to {self.destination} with options: {self.options}"
        )

        try:
            self._sync_recursive(self.source, self.destination, "")
        except FileSynchronizationError as e:
            print(f"Error during file sync: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def _calculate_checksum(self, file_path):
        """Calculates the SHA-256 checksum of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)  # Read in chunks
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _sync_recursive(self, source_root, destination_root, relative_path):
        """Recursively synchronizes files and folders.

        Args:
            source_root: The root directory of the source.
            destination_root: The root directory of the destination.
            relative_path: The path relative to the source and destination roots.
        """
        source_path = os.path.join(source_root, relative_path)
        destination_path = os.path.join(destination_root, relative_path)

        # Get lists of files and folders for source and destination
        source_entries = self.connector.get_file_list(source_path)
        try:
            destination_entries = self.connector.get_file_list(destination_path)
        except FileSynchronizationError:
            destination_entries = []

        # Create dictionaries for faster lookup
        source_files = {
            entry["name"]: {
                "type": entry["type"],
                "path": os.path.join(source_path, entry["name"]),
            }
            for entry in source_entries
        }
        destination_files = {
            entry["name"]: {
                "type": entry["type"],
                "path": os.path.join(destination_path, entry["name"]),
            }
            for entry in destination_entries
        }

        # Handle deletions if the "delete" option is True
        if self.options.get("delete", False):
            for name, dest_entry in destination_files.items():
                if name not in source_files:
                    if dest_entry["type"] == "file":
                        self.connector.delete_file(dest_entry["path"])
                        print(f"Deleted: {dest_entry['path']}")
                    elif dest_entry["type"] == "folder":
                        self.connector.delete_file(dest_entry["path"])
                        print(f"Deleted folder: {dest_entry['path']}")
        # Iterate through source entries and compare with destination
        for name, source_entry in source_files.items():
            source_entry_path = source_entry["path"]
            relative_entry_path = os.path.join(relative_path, name)
            destination_entry_path = os.path.join(destination_root, relative_entry_path)

            if source_entry["type"] == "file":
                if name not in destination_files:
                    # File doesn't exist in destination, upload it
                    self.connector.upload_file(
                        source_entry_path, destination_entry_path
                    )
                    print(f"Uploaded: {source_entry_path} -> {destination_entry_path}")
                else:
                    # File exists in destination, check for conflict
                    dest_entry = destination_files[name]
                    source_mtime = os.path.getmtime(source_entry_path)
                    dest_mtime = os.path.getmtime(dest_entry["path"])
                    source_checksum = self._calculate_checksum(source_entry_path)
                    dest_checksum = self._calculate_checksum(dest_entry["path"])

                    if source_checksum != dest_checksum:
                        # Conflict detected!
                        conflict_resolution = self.options.get(
                            "conflict_resolution", "prompt"
                        )

                        if conflict_resolution == "prompt":
                            choice = self._resolve_conflict_with_prompt(
                                source_entry_path, destination_entry_path
                            )
                            if choice == "source":
                                self.connector.upload_file(
                                    source_entry_path, destination_entry_path
                                )
                                print(
                                    f"Uploaded (source chosen): {source_entry_path} -> {destination_entry_path}"
                                )
                            elif choice == "destination":
                                print(
                                    f"Skipped (destination chosen): {source_entry_path}"
                                )
                            else:
                                print(f"Skipped (user canceled): {source_entry_path}")
                        elif conflict_resolution == "rename":
                            new_destination_entry_path = self._rename_conflicting_file(
                                destination_entry_path
                            )
                            self.connector.upload_file(
                                source_entry_path, new_destination_entry_path
                            )
                            print(
                                f"Uploaded (renamed destination): {source_entry_path} -> {new_destination_entry_path}"
                            )
                        else:
                            print(
                                f"Warning: Invalid conflict_resolution option: {conflict_resolution}"
                            )

                    elif source_mtime > dest_mtime:
                        # Source is newer but checksum are the same, upload it
                        self.connector.upload_file(
                            source_entry_path, destination_entry_path
                        )
                        print(
                            f"Updated: {source_entry_path} -> {destination_entry_path}"
                        )

            elif source_entry["type"] == "folder":
                if name not in destination_files:
                    # Folder doesn't exist in destination, create it
                    self.connector.create_folder(destination_entry_path)
                    print(f"Created folder: {destination_entry_path}")

                # Recursively sync the subfolder
                self._sync_recursive(source_root, destination_root, relative_entry_path)

    def _resolve_conflict_with_prompt(self, source_path, destination_path):
        """Prompts the user to choose between source and destination files."""
        while True:
            choice = input(
                f"Conflict detected: {source_path} vs {destination_path}\n"
                f"Choose an action:\n"
                f"  (s)ource: Keep source file\n"
                f"  (d)estination: Keep destination file\n"
                f"  (c)ancel: Skip\n"
                f"Enter your choice (s/d/c): "
            ).lower()
            if choice in ("s", "source"):
                return "source"
            elif choice in ("d", "destination"):
                return "destination"
            elif choice in ("c", "cancel"):
                return None
            else:
                print("Invalid choice. Please enter 's', 'd', or 'c'.")

    def _rename_conflicting_file(self, file_path):
        """Renames a file by appending a timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        base, ext = os.path.splitext(file_path)
        return f"{base}_conflict_{timestamp}{ext}"

    @staticmethod
    def from_dict(task_dict, connector):
        """Creates a FileSyncTask object from a dictionary."""
        return FileSyncTask(
            task_dict["source"],
            task_dict["destination"],
            task_dict.get("options"),
            task_dict.get("schedule"),
            connector,
        )
