import logging

from lib.audio_file_handler import convert_mp3_m4a, create_json, get_audio_file_info, get_talkgroup_data, \
    audio_file_cleanup
from lib.openmhz_handler import upload_to_openmhz
from lib.rdio_handler import upload_to_rdio

module_logger = logging.getLogger('rtl_watcher.file_processing')


def process_file(system_config_data, file_path):
    module_logger.info(f"Processing {file_path}")

    short_name, epoch_timestamp, frequency, duration_sec = get_audio_file_info(file_path)
    if any(value is None for value in [short_name, epoch_timestamp, frequency, duration_sec]):
        module_logger.error("Unable to get short name, timestamp, frequency or duration.")
        return

    module_logger.debug(system_config_data)
    if not system_config_data or len(system_config_data) < 1:
        module_logger.error(f"System config for {short_name} not found.")
        return

    talkgroup_data = get_talkgroup_data(system_config_data.get("talkgroup_csv_path", ""), frequency)
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

    if system_config_data.get("openmhz", {}).get("enabled", 0) == 1:
        upload_to_openmhz(system_config_data.get("openmhz", {}), file_path.replace(".mp3", ".m4a"), call_data)

    # Upload to RDIO
    for rdio in system_config_data.get("rdio_systems", []):
        if rdio.get("enabled", 0) == 1:
            try:
                upload_to_rdio(rdio, file_path.replace(".mp3", ".m4a"), call_data)
                module_logger.info(f"Successfully uploaded to RDIO server: {rdio.get('rdio_url')}")
            except Exception as e:
                module_logger.error(f"Failed to upload to RDIO server: {rdio.get('rdio_url')}. Error: {str(e)}", exc_info=True)
                continue
        else:
            module_logger.warning(f"RDIO system is disabled: {rdio.get('rdio_url')}")
            continue

    if system_config_data.get("keep_files", 0) == 0:
        audio_file_cleanup(file_path)

    module_logger.info(f"Processing Complete for {file_path}")
