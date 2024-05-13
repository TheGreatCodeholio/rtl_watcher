import requests
import logging

module_logger = logging.getLogger('icad_tr_uploader.icad_uploader')


def upload_to_icad_legacy(icad_data, mp3_audio_path, call_data):
    module_logger.info(f'Uploading to <<iCAD>> <<Tone>> <<Detect>> Legacy: {icad_data["icad_url"]}')

    if not call_data:
        module_logger.error('<<Failed>> uploading to <<iCAD>> <<Tone>> <<Detect>> Legacy: Empty call_data JSON')
        return False

    try:
        with open(mp3_audio_path, 'rb') as audio_file:
            files = {'file': (mp3_audio_path, audio_file, 'audio/mpeg')}
            response = requests.post(icad_data['icad_url'], files=files, data=call_data)
            response.raise_for_status()  # This will raise an error for 4xx and 5xx responses
            return True

    except FileNotFoundError:
        module_logger.error(f'<<iCAD>> <<Tone>> <<Detect>> Legacy - File not found : {mp3_audio_path}')
    except requests.exceptions.HTTPError as e:
        # This captures HTTP errors and logs them. `e.response` contains the response that caused this error.
        module_logger.error(f'<<HTTP>> <<error>> uploading to <<iCAD>> <<Tone>> <<Detect>> Legacy: {e.response.status_code}, {e.response.text}')
    except requests.exceptions.RequestException as e:
        # This captures other requests-related errors
        module_logger.error(f'<<Error>> <<uploading>> to <<iCAD>> <<Tone>> <<Detect>> Legacy: {e}')
    except IOError as e:
        # This captures general IO errors (broader than just FileNotFoundError)
        module_logger.error(f'<<IO>> <<error>> with file: {mp3_audio_path}, {e}')
    except Exception as e:
        module_logger.error(f'<<Unexpected>> <<Error>> while uploading to <<iCAD>> <<Tone>> <<Detect>> Legacy: {mp3_audio_path}, {e}')

    return False
