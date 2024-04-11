import logging
import os
import subprocess
from datetime import datetime

from mutagen.mp3 import MP3

from lib.config_handler import load_csv_channels

module_logger = logging.getLogger('rtl_watcher.audio_file_handler')


def convert_mp3_m4a(mp3_file_path):
    # Check if the MP3 file exists
    if not os.path.isfile(mp3_file_path):
        module_logger.error(f"MP3 file does not exist: {mp3_file_path}")
        return False

    module_logger.info(f'Converting MP3 to Mono M4A at 8k')

    # Construct the ffmpeg command
    m4a_file_path = mp3_file_path.replace('.mp3', '.m4a')
    command = ["ffmpeg", "-y", "-i", mp3_file_path, "-af", "aresample=resampler=soxr", "-ar", "8000", "-c:a", "aac", "-ac", "1", "-b:a", "8k", m4a_file_path]

    try:
        # Execute the ffmpeg command
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        module_logger.debug(f"ffmpeg output: {result.stdout}")
        module_logger.info(f"Successfully converted MP3 to M4A for file: {mp3_file_path}")
        return True
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to convert MP3 to M4A for file {mp3_file_path}. Error: {e}"
        module_logger.error(error_message)
        return False
    except Exception as e:
        error_message = f"An unexpected error occurred during conversion of {mp3_file_path}: {e}"
        module_logger.error(error_message)
        return False



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


def create_json(short_name, epoch_timestamp, frequency, duration_sec, talkgroup_data):
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