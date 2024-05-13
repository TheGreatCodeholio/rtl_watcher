import json
import logging
import os
import shutil
import subprocess
from datetime import datetime

from mutagen.mp3 import MP3

from lib.config_handler import load_csv_channels

module_logger = logging.getLogger('rtl_watcher.audio_file_handler')


def save_temporary_json_file(tmp_path, json_file_path):
    try:
        # Ensure the directory exists
        os.makedirs(tmp_path, exist_ok=True)

        # Construct the target path for the WAV file
        json_path = os.path.join(tmp_path, os.path.basename(json_file_path))

        # Copy the WAV file to the target path
        shutil.copy(json_file_path, json_path)

        module_logger.debug(f"<<JSON>> <<file>> saved successfully at {json_path}")
    except Exception as e:
        module_logger.error(f"Failed to save <<JSON>> <<file>> at {json_path}: {e}")


def save_call_data(json_file_path, call_data):
    try:
        # Writing call data to JSON file
        with open(json_file_path, "w") as json_file:
            json.dump(call_data, json_file, indent=4)
        module_logger.debug(f"<<JSON>> file saved <<successfully>> at {json_file_path}")
        return True
    except Exception as e:
        module_logger.error(f"Failed to save <<JSON>> file at {json_file_path}: {e}")
        return False


def save_temporary_mp3_file(tmp_path, mp3_file_path):
    try:
        # Ensure the directory exists
        os.makedirs(tmp_path, exist_ok=True)

        # Construct the target path for the WAV file
        mp3_temp_path = os.path.join(tmp_path, os.path.basename(mp3_file_path))

        # Copy the WAV file to the target path
        shutil.copy(mp3_file_path, mp3_temp_path)

        module_logger.debug(f"<<MP3>> <<file>> saved <<successfully>> at {mp3_temp_path}")
    except Exception as e:
        module_logger.error(f"<<Failed>> to save <<MP3>> <<file>> to {mp3_temp_path}: {e}")


def load_call_json(json_file_path):
    try:
        with open(json_file_path, 'r') as f:
            call_data = json.load(f)
        module_logger.info(f"Loaded <<Call>> <<Metadata>> Successfully")
        return call_data
    except FileNotFoundError:
        # Call Metadata JSON not found.
        module_logger.warning(f'<<Call>> <<Metadata>> file {json_file_path} not found.')
        return None
    except json.JSONDecodeError:
        module_logger.error(f'<<Call>> <<Metadata>> file {json_file_path} is not in valid JSON format.')
        return None
    except Exception as e:
        module_logger.error(f"Unexpected <<Error>> while loading <<Call>> <<Metadata>> {json_file_path}: {e}")
        return None


def save_temporary_files(tmp_path, mp3_file_path):
    try:
        save_temporary_mp3_file(tmp_path, mp3_file_path)
        save_temporary_json_file(tmp_path, mp3_file_path.replace(".wav", ".json"))
        module_logger.info(f"<<Temporary>> <<Files>> Saved to {tmp_path}")
        return True
    except OSError as e:
        if e.errno == 28:
            module_logger.error(
                f"<<Failed>> to write temp files to {tmp_path}. <<No>> <<space>> <<left>> on device to write files")
        else:
            module_logger.error(f"<<Failed>> to write files to {tmp_path}. <<OS>> <<error>> occurred: {e}")
        return False
    except Exception as e:
        module_logger.error(
            f"An <<unexpected>> <<error>> occurred while <<writing>> <<temporary>> <<files>> to {tmp_path}: {e}")
        return False


def clean_temp_files(mp3_file_path, m4a_file_path, json_file_path):
    if os.path.isfile(mp3_file_path):
        os.remove(mp3_file_path)

    if os.path.isfile(m4a_file_path):
        os.remove(m4a_file_path)

    if os.path.isfile(json_file_path):
        os.remove(json_file_path)


def get_audio_file_info(mp3_file_path):
    if not os.path.isfile(mp3_file_path):
        module_logger.error("MP3 File Doesn't Exist")
        return None, None, None, None

    try:
        mp3_file_name = os.path.basename(mp3_file_path)
        parts = mp3_file_name.split("_")
        if len(parts) < 3:
            module_logger.error("Filename format error.")
            return None, None, None, None

        short_name = parts[0]

        # Attempt to parse the date and time
        date_time_str = parts[1] + parts[2]
        date_time_format = "%Y%m%d%H%M%S"
        parsed_date_time = datetime.strptime(date_time_str, date_time_format)
        epoch_timestamp = int(parsed_date_time.timestamp())

        # Extract the frequency part correctly
        frequency = parts[3].replace(".mp3", "")

        # Attempt to load the MP3 file and get its duration
        audio = MP3(mp3_file_path)
        duration_sec = audio.info.length

        return short_name, epoch_timestamp, frequency, duration_sec
    except ValueError as e:
        module_logger.error("Date parsing error.")
        return None, None, None, None
    except Exception as e:
        module_logger.error(f"Unexpected error: {str(e)}.")
        return None, None, None, None


def get_talkgroup_data(talkgroup_csv_path, frequency):
    channel_data = load_csv_channels(talkgroup_csv_path)

    if channel_data is None:
        return None

    # Search for the frequency in the loaded data
    try:
        frequency = int(frequency)  # Ensure frequency is an integer
        talkgroup_data = next((tg for tg in channel_data if int(tg.get("channel_frequency", 0)) == frequency), None)

        if talkgroup_data is None:
            module_logger.warning("Frequency not Found in Channel Data")
            return None
        else:
            return talkgroup_data
    except ValueError:
        module_logger.error("Error: Invalid frequency format.")
        return None
    except KeyError:
        module_logger.error("Error: 'channel_frequency' field missing in CSV.")
        return None


def create_json(short_name, epoch_timestamp, frequency, duration_sec, talkgroup_data, json_file_path):
    # Initialize with default values
    call_data = {
        "freq": 0,
        "start_time": 0,
        "stop_time": 0,
        "emergency": 0,
        "encrypted": 0,
        "call_length": 0,
        "talkgroup": 0,
        "talkgroup_tag": "",
        "talkgroup_description": "",
        "talkgroup_group_tag": "",
        "talkgroup_group": "",
        "audio_type": "analog",
        "short_name": short_name,
        "freqList": [],
        "srcList": []
    }

    if not isinstance(talkgroup_data, dict):
        module_logger.error("Error: talkgroup_data must be a dictionary.")
        return None

    try:
        call_data["freq"] = int(frequency)
        call_data["start_time"] = int(epoch_timestamp)
        call_data["call_length"] = duration_sec
        call_data["talkgroup"] = int(talkgroup_data.get("talkgroup_decimal", 0))
        call_data["talkgroup_tag"] = talkgroup_data.get("talkgroup_alpha_tag", "")
        call_data["talkgroup_description"] = talkgroup_data.get("talkgroup_name", "")
        call_data["talkgroup_group"] = talkgroup_data.get("talkgroup_group", "")
        call_data["talkgroup_group_tag"] = talkgroup_data.get("talkgroup_service_type", "")
        call_data["tones"] = {}
        call_data["transcript"] = []
        call_data["freqList"].append({
            "freq": int(frequency),
            "time": int(epoch_timestamp),
            "pos": 0.00,
            "len": duration_sec,
            "error_count": "0",
            "spike_count": "0"
        })
        call_data["srcList"].append({
            "src": -1,
            "time": int(epoch_timestamp),
            "pos": 0.00,
            "emergency": 0,
            "signal_system": "",
            "tag": ""
        })

        save_result = save_call_data(json_file_path, call_data)
        if not save_result:
            module_logger.error(f"Unexpected error saving <<Call>> <<Metadata>> to {json_file_path}")
            return None
    except ValueError as ve:
        module_logger.error(f"Value error: {ve}")
        return None
    except TypeError as te:
        module_logger.error(f"Type error: {te}")
        return None
    except Exception as e:
        module_logger.error(f"Unexpected error: {e}")
        return None

    return call_data


def compress_audio(compression_config, input_audio_file_path):
    # Check if the audio input file exists
    if not os.path.isfile(input_audio_file_path):
        module_logger.error(f"Input Audio file does not exist: {input_audio_file_path}")
        return False

    _, file_extension = os.path.splitext(input_audio_file_path)

    module_logger.info(
        f'Converting {file_extension} to M4A at {compression_config.get("sample_rate")}@{compression_config.get("bitrate", 96)}')

    # Construct the ffmpeg command
    m4a_file_path = input_audio_file_path.replace('.wav', '.m4a')
    command = ["ffmpeg", "-y", "-i", input_audio_file_path, "-af", "aresample=resampler=soxr", "-ar",
               f"{compression_config.get('sample_rate', 16000)}", "-c:a", "aac",
               "-ac", "1", "-b:a", f"{compression_config.get('bitrate', 96)}k", m4a_file_path]

    try:
        # Execute the ffmpeg command
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        module_logger.debug(f"ffmpeg output: {result.stdout}")
        module_logger.info(f"Successfully converted WAV to M4A for file: {input_audio_file_path}")
        return True
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to convert {file_extension} to M4A for file {input_audio_file_path}. Error: {e}"
        module_logger.error(error_message)
        return False
    except Exception as e:
        error_message = f"An unexpected error occurred during conversion of {input_audio_file_path} to M4A: {e}"
        module_logger.error(error_message)
        return False


def audio_file_cleanup(mp3_file_path):
    # Remove the MP3 and M4A file if they exist
    for ext in ['.mp3', '.m4a', '.json']:
        file_path = mp3_file_path if ext == '.mp3' else mp3_file_path.replace('.mp3', ext)
        if os.path.exists(file_path):
            module_logger.debug(f"Removing file {file_path}")
            os.remove(file_path)
