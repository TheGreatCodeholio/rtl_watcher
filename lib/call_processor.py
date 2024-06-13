import logging
import os
import threading
import time

from lib.archive_handler import archive_files
from lib.audio_file_handler import create_json, get_audio_file_info, get_talkgroup_data, \
    audio_file_cleanup, compress_audio, save_call_data
from lib.broadcastify_calls_handler import upload_to_broadcastify_calls
from lib.config_handler import get_talkgroup_config
from lib.icad_alerting_handler import upload_to_icad_alert
from lib.icad_player_handler import upload_to_icad_player
from lib.icad_tone_detect_legacy_handler import upload_to_icad_legacy
from lib.openmhz_handler import upload_to_openmhz
from lib.rdio_handler import upload_to_rdio
from lib.tone_detect_handler import get_tones
from lib.transcribe_handler import upload_to_transcribe

module_logger = logging.getLogger('rtl_watcher.call_processing')


def log_time(action_name, start_time):
    end_time = time.time()
    elapsed_time = end_time - start_time
    module_logger.debug(f"{action_name} took {elapsed_time:.2f} seconds")
    return end_time


def process_call(system_config, mp3_file_path):
    threads = []
    start_time = time.time()
    module_logger.info(f"Processing File {mp3_file_path}")

    # create path variables for new files
    m4a_file_path = mp3_file_path.replace(".mp3", ".m4a")
    json_file_path = mp3_file_path.replace(".mp3", ".json")

    m4a_exists = False

    action_start = time.time()

    # Get System/Channel/Call Data from MP3 Filename
    system_short_name, epoch_timestamp, frequency, duration_sec = get_audio_file_info(mp3_file_path)
    if any(value is None for value in [system_short_name, epoch_timestamp, frequency, duration_sec]):
        module_logger.error(
            "<<Error>> while getting system short name, timestamp, frequency or duration from audio file name..")
        return

    # Validate System Configuration
    module_logger.debug(system_config)
    if not system_config or len(system_config) < 1:
        module_logger.error(f"<<Error>> while getting <<system>> <<configuration>> from config.json. Cannot Process")
        return

    # Get Talkgroup Data from CSV
    talkgroup_data = get_talkgroup_data(system_config.get("talkgroup_csv_path", ""), frequency)
    if not talkgroup_data:
        module_logger.error("<<Error>> while getting <<talkgroup>> <<data>> from CSV. Cannot Process")
        return

    # Generate Call Metadata and Save to disk from System/Channel/Call Data
    call_data = create_json(system_short_name, epoch_timestamp, frequency, duration_sec, talkgroup_data, json_file_path)
    if not call_data:
        module_logger.error("<<Error>> while creating <<Call>> <<Metadata>> Cannot Process")
        return

    talkgroup_decimal = call_data.get("talkgroup", 0)

    # Get talkgroup specific config from system configuration or use wild card * talkgroup config
    talkgroup_config = get_talkgroup_config(system_config.get("talkgroup_config", {}), call_data)
    if not talkgroup_config:
        module_logger.error("<<Talkgroup>> <<configuration>> not in config data. Cannot Process")
        return

    action_start = log_time("Initial audio processing.", action_start)

    # Convert audio to M4A
    if system_config.get("audio_compression", {}).get("enabled", 0) == 1:
        m4a_exists = compress_audio(system_config.get("audio_compression", {}), mp3_file_path)
        action_start = log_time("MP3 to M4A Convert", action_start)

    module_logger.debug(f"Timestamp from file - {epoch_timestamp}")
    module_logger.debug(f"Timestamp now - {time.time()}")
    module_logger.debug(f"File Duration - {duration_sec}")
    module_logger.debug(f"Skew Created to Now - {time.time() - epoch_timestamp}")
    module_logger.debug(f"Skew Created Minus Duration - {time.time() - epoch_timestamp + duration_sec}")

    # OpenMHZ upload task
    openmhz_thread = threading.Thread(target=upload_to_openmhz_task, args=(system_config, m4a_file_path, call_data))
    threads.append(openmhz_thread)

    # Broadcastify Calls upload task
    broadcastify_thread = threading.Thread(target=upload_to_broadcastify_calls_task, args=(
    system_config, m4a_file_path, call_data, epoch_timestamp, duration_sec))
    threads.append(broadcastify_thread)

    # RDIO upload tasks
    for rdio in system_config.get("rdio_systems", []):
        rdio_thread = threading.Thread(target=upload_to_rdio_task, args=(rdio, m4a_file_path, call_data))
        threads.append(rdio_thread)

    # start upload threads
    for thread in threads:
        thread.start()

    # Legacy Tone Detection
    for icad_detect in system_config.get("icad_tone_detect_legacy", []):
        if icad_detect.get("enabled", 0) == 1:
            try:
                icad_result = upload_to_icad_legacy(icad_detect, mp3_file_path, call_data)
                action_start = log_time("iCAD Legacy Upload", action_start)
                if icad_result:
                    module_logger.info(
                        f"<<Successfully>> uploaded to <<iCAD>> <<Tone>> <<Detect>> Legacy server: {icad_detect.get('icad_url')}")
                else:
                    raise Exception()

            except Exception as e:
                module_logger.error(
                    f"<<Failed>> to upload to <<iCAD>> <<Tone>> <<Detect>> Legacy server: {icad_detect.get('icad_url')}. Error: {str(e)}",
                    exc_info=True)
                continue
        else:
            module_logger.warning(f"<<iCAD>> <<Tone>> <<Detect>> Legacy is disabled: {icad_detect.get('icad_url')}")
            continue

    # Tone Detection
    if system_config.get("tone_detection", {}).get("enabled", 0) == 1:
        if talkgroup_decimal not in system_config.get("tone_detection", {}).get("allowed_talkgroups",
                                                                                []) and "*" not in system_config.get(
            "tone_detection", {}).get("allowed_talkgroups", []):
            module_logger.debug(
                f"<<Tone>> <<Detection>> Disabled for Talkgroup {call_data.get('talkgroup_tag') or call_data.get('talkgroup')}")
        else:
            tone_detect_result = get_tones(system_config.get("tone_detection", {}), mp3_file_path)
            action_start = log_time("Tone Detection", action_start)
            call_data["tones"] = tone_detect_result
            module_logger.info(f"<<Tone>> <<Detection>> Complete")
            module_logger.debug(call_data.get("tones"))

    # Transcribe Audio
    if system_config.get("transcribe", {}).get("enabled", 0) == 1:
        if talkgroup_decimal not in system_config.get("transcribe", {}).get("allowed_talkgroups",
                                                                            []) and "*" not in system_config.get(
            "transcribe", {}).get("allowed_talkgroups", []):
            module_logger.debug(
                f"<<iCAD>> <<Transcribe>> <<Disabled>> for Talkgroup {call_data.get('talkgroup_tag') or call_data.get('talkgroup')}")
        else:
            transcribe_result = upload_to_transcribe(system_config.get("transcribe", {}), mp3_file_path, call_data,
                                                     talkgroup_config=None)
            action_start = log_time("Transcribe", action_start)

            call_data["transcript"] = transcribe_result
            module_logger.debug(call_data.get("transcript"))

    # Resave JSON with new Transcript and Tone Data.
    try:
        save_call_data(json_file_path, call_data)
    except Exception as e:
        module_logger.warning(
            f"<<Unexpected>> <<error>> occurred saving new call data to <<temporary>> <<file>> {json_file_path}. {e}")

    # Archive Files
    if system_config.get("archive", {}).get("enabled", 0) == 1 and system_config.get("archive", {}).get("archive_days",
                                                                                                        0) >= 1:
        mp3_url, m4a_url, json_url = archive_files(system_config.get("archive", {}),
                                                   os.path.dirname(mp3_file_path), os.path.basename(mp3_file_path),
                                                   call_data,
                                                   system_short_name)
        if mp3_url:
            call_data["audio_mp3_url"] = mp3_url
        if m4a_url:
            call_data["audio_m4a_url"] = m4a_url

        action_start = log_time("Archive Files", action_start)

        if mp3_url is None and m4a_url is None and json_url is None:
            module_logger.error("No Files Uploaded to Archive")
        else:
            module_logger.info(f"Archive Complete")
            module_logger.debug(f"Url Paths:\n{call_data.get('audio_mp3_url')}\n{call_data.get('audio_m4a_url')}")

    # Send to Players

    # Upload to iCAD Player
    if call_data.get("audio_m4a_url", "") and system_config.get("icad_player", {}).get("enabled", 0) == 1:

        if talkgroup_decimal not in system_config.get("icad_player", {}).get("allowed_talkgroups",
                                                                             []) and "*" not in system_config.get(
            "icad_player", {}).get("allowed_talkgroups", []):
            module_logger.warning(
                f"iCAD Player Disabled for Talkgroup {call_data.get('talkgroup_tag') or call_data.get('talkgroup_decimal')}")
        else:
            icad_player_result = upload_to_icad_player(system_config.get("icad_player", {}), call_data)
            action_start = log_time("iCAD Player", action_start)
            if icad_player_result:
                module_logger.info(f"Upload to iCAD Player Complete")

    # Upload to Alerting
    if system_config.get("icad_alerting", {}).get("enabled", 0) == 1:
        if talkgroup_decimal not in system_config.get("icad_alerting", {}).get("allowed_talkgroups",
                                                                               []) and "*" not in system_config.get(
            "icad_alerting", {}).get("allowed_talkgroups", []):
            module_logger.warning(
                f"iCAD Alerting Disabled for Talkgroup {call_data.get('talkgroup_tag') or call_data.get('talkgroup_decimal')}")
        else:
            upload_to_icad_alert(system_config.get("icad_alerting", {}), call_data)
            action_start = log_time("iCAD Alerting", action_start)
            module_logger.info(f"Upload to iCAD Alert Complete")

    if not system_config.get("keep_files"):
        audio_file_cleanup(mp3_file_path)

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    total_time = time.time() - start_time
    module_logger.info(f"Processing Complete for {mp3_file_path} - Total time: {total_time:.2f} seconds.")


def upload_to_openmhz_task(system_config, m4a_file_path, call_data):
    try:
        if system_config.get("openmhz", {}).get("enabled", 0) == 1:
            if m4a_file_path:
                result = upload_to_openmhz(system_config.get("openmhz", {}), m4a_file_path, call_data)
                log_time("OpenMHZ Upload", time.time())
                return result
            else:
                module_logger.warning(f"No M4A file can't send to OpenMHZ")
    except Exception as e:
        module_logger.error(f"Error uploading to OpenMHZ: {e}")


def upload_to_broadcastify_calls_task(system_config, m4a_file_path, call_data, epoch_timestamp, duration_sec):
    try:
        if system_config.get("broadcastify_calls", {}).get("enabled", 0) == 1:
            if m4a_file_path:
                current_time = time.time()
                module_logger.debug(f"Timestamp from file - {epoch_timestamp}")
                module_logger.debug(f"Timestamp now - {current_time}")
                module_logger.debug(f"File Duration - {duration_sec}")
                module_logger.debug(f"Skew Created to Now - {current_time - epoch_timestamp}")
                module_logger.debug(f"Skew Created Minus Duration - {current_time - epoch_timestamp + duration_sec}")

                result = upload_to_broadcastify_calls(system_config.get("broadcastify_calls", {}),
                                                      m4a_file_path, call_data)
                log_time("Broadcastify Calls", time.time())
                return result
            else:
                module_logger.warning(f"No M4A file can't send to Broadcastify Calls")
    except Exception as e:
        module_logger.error(f"Broadcastify Calls Upload to Broadcastify Failed: {e}")


def upload_to_rdio_task(rdio, m4a_file_path, call_data):
    try:
        if rdio.get("enabled", 0) == 1:
            if m4a_file_path:
                result = upload_to_rdio(rdio, m4a_file_path, call_data)
                log_time(f"RDIO Upload {rdio.get('rdio_url')}", time.time())
                return result
            else:
                module_logger.warning(f"No M4A file can't send to RDIO")
    except Exception as e:
        module_logger.error(f"Error uploading to RDIO {rdio.get('rdio_url')}: {e}")
