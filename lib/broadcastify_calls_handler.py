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
    module_logger.debug(f"Broadcastify Calls - Sending {method} request to {url} ({request_type_description}) with kwargs: {kwargs}")
    try:
        if method == "POST":
            response = requests.post(method, url, **kwargs)
        elif method == "PUT":
            response = requests.put(url, **kwargs)
        else:
            response = requests.get(url, **kwargs)

        if response.status_code != 200:
            module_logger.error(
                f"Broadcastify Calls - Error in {method} request to {url} ({request_type_description}): "
                f"Status {response.status_code}, Response: {response.text}")
            return None
        module_logger.debug(f"Broadcastify Calls - Received response: {response.status_code} - {response.text}")
        return response
    except requests.exceptions.RequestException as e:
        module_logger.error(f"Broadcastify Calls - Exception during {method} request to {url} ({request_type_description}): {e}")
        return None


def prepare_metadata(call_data, m4a_file_path):
    module_logger.debug("Broadcastify Calls - Preparing metadata")
    json_string = json.dumps(call_data)
    json_bytes = json_string.encode('utf-8')
    metadata_filename = os.path.basename(m4a_file_path.replace("m4a", "json"))
    return metadata_filename, json_bytes


def read_audio_file(m4a_file_path):
    module_logger.debug(f"Broadcastify Calls - Reading audio file from {m4a_file_path}")
    try:
        with open(m4a_file_path, 'rb') as audio_file:
            audio_bytes = audio_file.read()
            module_logger.debug(f"Broadcastify Calls - Read {len(audio_bytes)} bytes from audio file")
            return audio_bytes
    except IOError as e:
        module_logger.error(f"Broadcastify Calls - File error: {e}")
        return None


def post_metadata(broadcastify_url, metadata_filename, json_bytes, call_data, broadcastify_config):
    module_logger.debug("Broadcastify Calls - Posting metadata")
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
                module_logger.debug(f"Broadcastify Calls - Received upload URL: {upload_url}")
                return upload_url
            else:
                module_logger.error("Upload URL not found in the Broadcastify response.")
        except (ValueError, IndexError) as e:
            module_logger.error(f"Failed to parse response from Broadcastify: {e}")
    return None


def upload_audio_file(upload_url, audio_bytes):
    module_logger.debug(f"Uploading audio file to {upload_url}")
    headers = {
        "User-Agent": "TrunkRecorder1.0",
        "Expect": "",
        "Transfer-Encoding": "",
        "Content-Type": "audio/aac"
    }

    response = send_request('PUT', upload_url, headers=headers, data=audio_bytes)
    if response:
        module_logger.debug("Broadcastify Calls - Audio file uploaded successfully")
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
        module_logger.error("Broadcastify Calls - Failed to read audio file")
        return False

    upload_url = post_metadata(broadcastify_url, metadata_filename, json_bytes, call_data, broadcastify_config)
    if upload_url:
        return upload_audio_file(upload_url, audio_bytes)
    else:
        module_logger.error("Broadcastify Calls - Failed to get upload URL")
        return False
