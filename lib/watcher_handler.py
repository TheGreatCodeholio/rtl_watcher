import logging
import os
from concurrent.futures import ThreadPoolExecutor
import time
import traceback

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from lib.file_processing_handler import process_file

module_logger = logging.getLogger('rtl_watcher.watcher')


class FileEventHandler(FileSystemEventHandler):
    def __init__(self, executor, config_data):
        self.config_data = config_data
        self.executor = executor

    def on_moved(self, event):
        """
        Handle the 'moved' event.

        Args:
        event: The event object containing information about the move.
        """
        module_logger.debug(f"File or directory moved: {event.dest_path}")
        self._process_file_moved_created_event(event, event.dest_path)

    def on_created(self, event):
        """
        Handle the 'created' event.

        Args:
        event: The event object containing information about the creation.
        """
        module_logger.debug(f"File or directory created: {event.src_path}")
        self._process_file_moved_created_event(event, event.src_path)

    def on_opened(self, event):
        """
        Handle the 'opened' event.

        Args:
        event: The event object containing information about the opening.
        """
        module_logger.debug(f"File or directory opened: {event.src_path}")

    def on_deleted(self, event):
        """
        Handle the 'deleted' event.

        Args:
        event: The event object containing information about the deletion.
        """
        module_logger.debug(f"File or directory deleted: {event.src_path}")

    def on_modified(self, event):
        """
        Handle the 'modified' event.

        Args:
        event: The event object containing information about the modification.
        """
        module_logger.debug(f"File or directory modified: {event.src_path}")

    def _process_file_moved_created_event(self, event, event_path):
        """
        Process the file event based on the specified condition.

        Args:
        path (str): The path of the file or directory.
        """
        if not event.is_directory:
            _, file_extension = os.path.splitext(event_path)
            if file_extension.lower() in [".mp3", ".wav"]:
                module_logger.debug(f"Starting new thread for file: {event_path}")
                try:
                    self.executor.submit(process_file, self.config_data, event_path)
                except Exception as e:
                    module_logger.error(f"Error starting thread for file {event_path}: {e}")


class Watcher:
    def __init__(self, config_data):
        self.config_data = config_data
        self.directory_to_watch = self.config_data.get("watch_directory") or None
        self.observer = Observer()
        self.executor = ThreadPoolExecutor(max_workers=self.config_data.get("max_processing_threads", 5))

    def run(self):
        event_handler = FileEventHandler(self.executor, self.config_data)
        if self.directory_to_watch:
            self.observer.schedule(event_handler, self.directory_to_watch, recursive=True)
        else:
            module_logger.error("Watch Directory not set.")
            return

        self.observer.start()
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            self.observer.stop()
            module_logger.info("Observer Stopped")

        self.observer.join()
        self.executor.shutdown(wait=True)
