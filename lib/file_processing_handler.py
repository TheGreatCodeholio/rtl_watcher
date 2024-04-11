import logging

from lib.audio_file_handler import convert_mp3_m4a, create_json, get_audio_file_info, get_talkgroup_data, \
    audio_file_cleanup
from lib.openmhz_handler import upload_to_openmhz

module_logger = logging.getLogger('rtl_watcher.file_processing')


def process_file(config_data, file_path):
    module_logger.info(f"Processing {file_path}")

    short_name, epoch_timestamp, frequency, duration_sec = get_audio_file_info(file_path)
    if any(value is None for value in [short_name, epoch_timestamp, frequency, duration_sec]):
        module_logger.error("Unable to get short name, timestamp, frequency or duration.")
        return

    system_config = config_data.get("systems", {}).get(short_name, {})
    module_logger.debug(system_config)
    if not system_config or len(system_config) < 1:
        module_logger.error(f"System config for {short_name} not found.")
        return

    talkgroup_data = get_talkgroup_data(system_config.get("talkgroup_csv_path", ""), frequency)
    if not talkgroup_data:
        module_logger.error("Talkgroup Data Empty")
        return

    convert_result = convert_mp3_m4a(file_path)
    if not convert_result:
        module_logger.error("Convert M4A not complete")
        return

    call_data = create_json(short_name, epoch_timestamp, frequency, duration_sec, talkgroup_data)
    if not call_data:
        module_logger.error("Call Data Empty")
        return

    if system_config.get("openmhz", {}).get("enabled", 0) == 1:
        upload_to_openmhz(system_config.get("openmhz", {}), file_path.replace(".mp3", ".m4a"), call_data)

    if config_data.get("archive_files", 0) == 0:
        audio_file_cleanup(file_path)

    module_logger.info(f"Processing Complete for {file_path}")
