import csv
import json
import logging

module_logger = logging.getLogger('rtl_watcher.config')


def load_config_file(file_path):
    """
    Loads the configuration file and encryption key.
    """

    try:
        with open(file_path, 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        module_logger.warning(f'Configuration file {file_path} not found.')
        return None
    except json.JSONDecodeError:
        module_logger.error(f'Configuration file {file_path} is not in valid JSON format.')
        return None
    except Exception as e:
        module_logger.error(f'Unexpected Exception Loading file {file_path} - {e}')
        return None

    return config_data


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
