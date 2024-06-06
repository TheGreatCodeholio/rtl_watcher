import json
import logging
import os

import requests

module_logger = logging.getLogger('rtl_watcher.broadcastify_calls')


def send_request(method, url, request_type_description, **kwargs):
    """
    Send an HTTP request using the requests library and return the response object.
    Handles exceptions and logs errors with more context.
    """
    try:
        response = requests.request(method, url, **kwargs)
        if response.status_code != 200:
            module_logger.error(
                f"Error in {method} request to {url} ({request_type_description}): "
                f"Status {response.status_code}, Response: {response.text}")
            return None
        return response
    except requests.exceptions.RequestException as e:
        module_logger.error(f"Exception during {method} request to {url} ({request_type_description}): {e}")
        return None


def prepare_metadata(call_data, m4a_file_path):
    json_string = json.dumps(call_data)
    json_bytes = json_string.encode('utf-8')
    metadata_filename = os.path.basename(m4a_file_path.replace("m4a", "json"))
    return metadata_filename, json_bytes


def read_audio_file(m4a_file_path):
    try:
        with open(m4a_file_path, 'rb') as audio_file:
            return audio_file.read()
    except IOError as e:
        module_logger.error(f"File error: {e}")
        return None


def post_metadata(broadcastify_url, metadata_filename, json_bytes, call_data, broadcastify_config):
    files = {
        'metadata': (metadata_filename, json_bytes, 'application/json'),
        'filename': (None, os.path.basename(metadata_filename)),
        'callDuration': (None, str(call_data["call_length"])),
        'systemId': (None, str(broadcastify_config["system_id"])),
        'apiKey': (None, broadcastify_config["api_key"])
    }

    headers = {
        "User-Agent": "TrunkRecorder1.0",
        "Expect": ""
    }

    response = send_request('POST', broadcastify_url, headers=headers, files=files)
    if response:
        try:
            upload_url = response.text.split(" ")[1]
            if upload_url:
                return upload_url
            else:
                module_logger.error("Upload URL not found in the Broadcastify response.")
        except (ValueError, IndexError) as e:
            module_logger.error(f"Failed to parse response from Broadcastify: {e}")
    return None


def upload_audio_file(upload_url, audio_bytes):
    headers = {
        "User-Agent": "TrunkRecorder1.0",
        "Expect": "",
        "Transfer-Encoding": "",
        "Content-Type": "audio/aac"
    }

    response = send_request('PUT', upload_url, headers=headers, data=audio_bytes)
    if response:
        return True
    else:
        module_logger.error(f"Failed to post call to Broadcastify Calls AWS Failed.")
        return False


def upload_to_broadcastify_calls(broadcastify_config, m4a_file_path, call_data):
    module_logger.info("Uploading to Broadcastify Calls")

    broadcastify_url = "https://api.broadcastify.com/call-upload"
    metadata_filename, json_bytes = prepare_metadata(call_data, m4a_file_path)
    audio_bytes = read_audio_file(m4a_file_path)

    if audio_bytes is None:
        return False

    upload_url = post_metadata(broadcastify_url, metadata_filename, json_bytes, call_data, broadcastify_config)
    if upload_url:
        return upload_audio_file(upload_url, audio_bytes)
    else:
        return False
