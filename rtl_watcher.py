import os
import threading
import time
import traceback

from lib.config_handler import load_config_file
from lib.logging_handler import CustomLogger
from lib.watcher_handler import Watcher

app_name = "rtl_watcher"
__version__ = "1.0"

root_path = os.getcwd()
config_file_name = "config.json"

log_file_name = f"{app_name}.log"

log_path = os.path.join(root_path, 'log')

if not os.path.exists(log_path):
    os.makedirs(log_path)

config_path = os.path.join(root_path, 'etc')

logging_instance = CustomLogger(1, f'{app_name}',
                                os.path.join(log_path, log_file_name))

try:
    config_data = load_config_file(os.path.join(config_path, config_file_name))
    logging_instance.set_log_level(config_data.get("log_level", 1))
    logger = logging_instance.logger
    logger.info("Loaded Config File")
except Exception as e:
    traceback.print_exc()
    logging_instance.logger.error(f'Error while <<loading>> configuration : {e}')
    time.sleep(5)
    exit(1)


def main():
    watcher_threads = []

    for system in config_data.get("systems"):
        watcher = Watcher(config_data["systems"][system], config_data.get("temp_file_path", "/dev/shm"))
        logger.info(f"Starting Folder Watcher For: {system}")
        t = threading.Thread(target=watcher.run)
        t.start()
        watcher_threads.append(t)

    for t in watcher_threads:
        t.join()


if __name__ == "__main__":
    main()
