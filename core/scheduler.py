import schedule
import time
import threading
from core.task_manager import TaskManager


class Scheduler:
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self.scheduler_thread = None
        self.stop_event = threading.Event()

    def run_pending_tasks(self):
        """Runs all pending tasks."""
        schedule.run_pending()

    def schedule_tasks(self):
        """Configures the schedule for all tasks."""
        for task in self.task_manager.list_tasks():
            if task.schedule:
                interval = task.schedule.get("interval")
                at_time = task.schedule.get("at")

                if interval:
                    if at_time:
                        schedule.every(interval).seconds.at(at_time).do(task.execute)
                    else:
                        schedule.every(interval).seconds.do(task.execute)
                elif at_time:
                    schedule.every().day.at(at_time).do(task.execute)
                else:
                    print(
                        f"Warning: Invalid schedule for task: {task.source} -> {task.destination}"
                    )

    def start(self):
        """Starts the scheduler in a separate thread."""
        self.schedule_tasks()  # Set up the schedule
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = (
            True  # Allow program to exit when only this thread is running
        )
        self.scheduler_thread.start()

    def stop(self):
        """Stops the scheduler thread."""
        if self.scheduler_thread:
            self.stop_event.set()
            self.scheduler_thread.join()
            self.scheduler_thread = None
            print("Scheduler stopped.")

    def _run_scheduler(self):
        """The main loop of the scheduler thread."""
        while not self.stop_event.is_set():
            self.run_pending_tasks()
            time.sleep(1)  # Check every second
