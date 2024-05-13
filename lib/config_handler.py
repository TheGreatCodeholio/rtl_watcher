import csv
import json
import logging

module_logger = logging.getLogger('rtl_watcher.config')

default_config = {
    "log_level": 1,
    "temp_file_path": "/dev/shm",
    "systems": {
        "example-system": {
            "keep_local_files": False,
            "watch_directory": "/home/example/example_recordings",
            "max_processing_threads": 5,
            "talkgroup_csv_path": "/home/example/rtl_config/example_county_channels.csv",
            "archive": {
                "enabled": 0,
                "archive_type": "scp",
                "archive_path": "",
                "archive_days": 0,
                "archive_extensions": [".mp3", ".m4a", ".json"],
                "google_cloud": {
                    "project_id": "",
                    "bucket_name": "",
                    "credentials_file": ""
                },
                "aws_s3": {
                    "access_key_id": "",
                    "secret_access_key": "",
                    "bucket_name": "",
                    "region": ""
                },
                "scp": {
                    "host": "",
                    "port": 22,
                    "user": "",
                    "password": "",
                    "private_key_path": "",
                    "base_url": "https://example.com/audio"
                },
                "local": {
                    "base_url": "https://example.com/audio"
                }
            },
            "audio_compression": {
                "enabled": 0,
                "sample_rate": 16000,
                "bitrate": 96
            },
            "icad_tone_detect_legacy": [
                {
                    "enabled": 0,
                    "talkgroups": ["*"],
                    "icad_url": "https://detect.example.com/tone_detect",
                    "icad_api_key": ""
                }
            ],
            "tone_detection": {
                "enabled": 0,
                "allowed_talkgroups": ["*"],
                "matching_threshold": 2,
                "time_resolution": 100,
                "tone_a_min_length": 0.8,
                "tone_b_min_length": 2.8,
                "long_tone_min_length": 2.0,
                "hi_low_interval": 0.2,
                "hi_low_min_alternations": 3
            },
            "transcribe": {
                "enabled": 0,
                "allowed_talkgroups": ["*"],
                "api_url": "",
                "api_key": ""
            },
            "openmhz": {
                "enabled": 0,
                "short_name": "example",
                "api_key": "example-api-key"
            },
            "broadcastify_calls": {
                "enabled": 0,
                "calls_slot": -1,
                "system_id": 0,
                "api_key": ""
            },
            "icad_player": {
                "enabled": 0,
                "allowed_talkgroups": ["*"],
                "api_url": "https://player.example.com/upload-audio",
                "api_key": ""
            },
            "rdio_systems": [
                {
                    "enabled": 0,
                    "system_id": 1111,
                    "rdio_url": "http://example.com:3000/api/trunk-recorder-call-upload",
                    "rdio_api_key": "example-api-key"
                }
            ],
            "talkgroup_config": {
                "*": {
                    "whisper": {
                        "language": "en",
                        "beam_size": 5,
                        "best_of": 5,
                        "initial_prompt": None,
                        "use_last_as_initial_prompt": False,
                        "word_timestamps": True,
                        "cut_tones": False,
                        "cut_pre_tone": 0.5,
                        "cut_post_tone": 0.5,
                        "amplify_audio": False,
                        "vad_filter": True,
                        "vad_parameters": {
                            "threshold": 0.3,
                            "min_speech_duration_ms": 250,
                            "max_speech_duration_s": 3600,
                            "min_silence_duration_ms": 400,
                            "window_size_samples": 1024,
                            "speech_pad_ms": 400
                        }
                    }
                }
            }
        }
    }
}


def generate_default_config():
    try:

        global default_config
        default_data = default_config.copy()

        return default_data

    except Exception as e:
        module_logger.error(f'Error generating default configuration: {e}')
        return None


def load_config_file(file_path):
    """
    Loads the configuration file.
    """

    # Attempt to load the configuration file
    try:
        with open(file_path, 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        # Config not found, create and load.
        module_logger.warning(f'Configuration file {file_path} not found. Creating default.')
        config_data = generate_default_config()
        if config_data:
            save_config_file(file_path, config_data)
            module_logger.warning(f'Created Default Configuration.')
            return config_data
    except json.JSONDecodeError:
        module_logger.error(f'Configuration file {file_path} is not in valid JSON format.')
        return None
    except Exception as e:
        module_logger.error(f'Unexpected Exception Loading file {file_path} - {e}')
        return None

    return config_data


def save_config_file(file_path, default_data):
    """Creates a configuration file with default data if it doesn't exist."""
    try:
        with open(file_path, "w") as outfile:
            outfile.write(json.dumps(default_data, indent=4))
        return True
    except Exception as e:
        module_logger.error(f'Unexpected Exception Saving file {file_path} - {e}')
        return None


def load_csv_channels(talkgroup_csv_path):
    csv_headers = ["talkgroup_decimal", "channel_frequency", "pl_tone", "talkgroup_alpha_tag", "talkgroup_name",
                   "talkgroup_service_type", "talkgroup_group", "channel_enable"]

    try:
        if talkgroup_csv_path == "" or not talkgroup_csv_path:
            module_logger.error("The path for the CSV file is missing or empty.")
            return None
        with open(talkgroup_csv_path, 'r') as csv_file:
            lines = csv_file.read().splitlines()
            reader = csv.DictReader(lines, fieldnames=csv_headers)
            first_row = next(reader, None)
            if first_row is not None and first_row[csv_headers[0]] != csv_headers[0] and first_row[csv_headers[1]] != \
                    csv_headers[1]:
                # The first two fields of the first row don't match the headers, so it's a data row.
                # Include it in the final data by creating a new list with it as the first element.
                talkgroup_data = [first_row] + [row for row in reader]
            else:
                # The first two fields of the first row match the headers, so it's a header row. Skip it.
                talkgroup_data = [row for row in reader]

        module_logger.debug(talkgroup_data)

        return talkgroup_data
    except KeyError:
        module_logger.error("Error: The 'talkgroup_csv_path' key is not present in system_config.")
        return None
    except FileNotFoundError:
        module_logger.error(f"Error: File not found at {talkgroup_csv_path}.")
        return None
    except csv.Error:
        module_logger.error("Error: There was an issue with the CSV file/format.")
        return None
    except Exception as e:
        module_logger.error(f"An unexpected error occurred: {e}")
        return None


def get_talkgroup_config(talkgroup_config, call_data):
    talkgroup_dec = call_data.get("talkgroup", 0)
    talkgroup_config_data = {}  # Initialize as an empty dict

    # Determine the appropriate talkgroup configuration
    if talkgroup_dec > 0 and talkgroup_config:
        talkgroup_dec_str = str(talkgroup_dec)
        talkgroup_config_data = talkgroup_config.get(talkgroup_dec_str) or talkgroup_config.get("*", {})

    return talkgroup_config_data
