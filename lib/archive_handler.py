import logging
import os
from datetime import datetime

from lib.remote_storage_handler import get_archive_class

module_logger = logging.getLogger('rtl_watcher.archive')


def archive_files(archive_config, source_path, mp3_file_name, call_data, system_short_name):
    mp3_url_path = None
    m4a_url_path = None
    json_url_path = None

    if not archive_config.get("archive_path", "") and archive_config.get('archive_type', '') not in ["google_cloud", "aws_s3"]:
        module_logger.warning("<<Archive>> <<error>> No Archive Path Set")
        return mp3_url_path, m4a_url_path, json_url_path

    if not archive_config.get('archive_type', '') or archive_config.get('archive_type', '') not in ["google_cloud", "aws_s3", "scp", "local"]:
        module_logger.warning(f"<<Archive>> <<error>> Archive Type Not Set or Invalid. {archive_config.get('archive_type', '')}")
        return mp3_url_path, m4a_url_path, json_url_path

    archive_class = get_archive_class(archive_config)
    if not archive_class:
        module_logger.warning(f"<<Archive>> <<error>> Can not start the Archive Class for {archive_config.get('archive_type', '')}")
        return mp3_url_path, m4a_url_path, json_url_path

    # Convert the epoch timestamp to a datetime object in UTC
    call_date = datetime.utcfromtimestamp(call_data['start_time'])

    generated_folder_path = os.path.join(system_short_name, str(call_date.year),
                               str(call_date.month), str(call_date.day))

    # Create folder structure using current date
    folder_path = os.path.join(archive_config.get("archive_path"), generated_folder_path)

    m4a_filename = mp3_file_name.replace(".mp3", ".m4a")
    json_filename = mp3_file_name.replace(".mp3", ".json")

    source_wav_path = os.path.join(source_path, mp3_file_name)
    destination_wav_path = os.path.join(folder_path, mp3_file_name)

    source_m4a_path = os.path.join(source_path, m4a_filename)
    destination_m4a_path = os.path.join(folder_path, m4a_filename)

    source_json_path = os.path.join(source_path, json_filename)
    destination_json_path = os.path.join(folder_path, json_filename)

    module_logger.info(f"Archiving {' '.join(archive_config.get('archive_extensions', []))} files via {archive_config.get('archive_type', '')} to: {folder_path}")

    for extension in archive_config.get('archive_extensions', []):
        if extension == ".mp3":
            upload_response = archive_class.upload_file(source_wav_path, destination_wav_path, generated_folder_path)
            if upload_response:
                mp3_url_path = upload_response
        elif extension == ".m4a":
            upload_response = archive_class.upload_file(source_m4a_path, destination_m4a_path, generated_folder_path)
            if upload_response:
                m4a_url_path = upload_response
        elif extension == ".json":
            upload_response = archive_class.upload_file(source_json_path, destination_json_path, generated_folder_path)
            if upload_response:
                json_url_path = upload_response
        else:
            module_logger.warning("<<Archive>> <<error>> Unknown Archive Extension")

    if archive_config.get("archive_days", 0) >= 1:
        archive_class.clean_files(os.path.join(archive_config.get("archive_path"), system_short_name), archive_config.get("archive_days", 1))

    return mp3_url_path, m4a_url_path, json_url_path
