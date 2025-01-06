from config.config_manager import ConfigurationManager
from core.task_manager import TaskManager, FileSyncTask
from core.scheduler import Scheduler
from core.connectors.local_file_connector import LocalFileConnector
import time
import os

if __name__ == "__main__":
    # Initialize Configuration Manager
    config_manager = ConfigurationManager("settings.json")

    # Initialize Task Manager
    task_manager = TaskManager(config_manager)

    # Create a LocalFileConnector
    local_connector = LocalFileConnector()

    # Register the FileSyncTask type
    task_manager.register_task_type("file_sync", FileSyncTask)

    # Define source and destination folders
    source_folder = "test_source"
    destination_folder = "test_destination"

    # Create source folder and files for testing
    os.makedirs(source_folder, exist_ok=True)
    with open(f"{source_folder}/file1.txt", "w") as f:
        f.write("Content of file 1")
    with open(f"{source_folder}/file2.txt", "w") as f:
        f.write("Content of file 2")
    os.makedirs(f"{source_folder}/subfolder", exist_ok=True)
    with open(f"{source_folder}/subfolder/file3.txt", "w") as f:
        f.write("Content of file 3")

    # Create and add a task (if there are none in the config)
    if not task_manager.list_tasks():
        # Pass the connector when creating the task
        task1 = FileSyncTask(
            source_folder,
            destination_folder,
            {
                "delete": True,
                "conflict_resolution": "prompt",
            },
            connector=local_connector,
        )
        task_manager.add_task(task1)
    # Initialize Scheduler
    scheduler = Scheduler(task_manager)

    # List tasks
    print("Tasks:")
    for task in task_manager.list_tasks():
        print(
            f"- {task.source} -> {task.destination} ({task.task_type}, options: {task.options})"
        )

    # Start the scheduler
    print("Starting scheduler...")
    scheduler.start()

    try:
        # Keep the main thread alive to allow the scheduler to run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping scheduler...")
        scheduler.stop()
        print("Exiting.")
