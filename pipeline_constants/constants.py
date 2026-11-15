import os
import sys

#---------Project Credentials----------
PROJECT_ROOT = sys.path[0]

TOPIC = True

#-------Import variables----------
INPUT_LANGUAGE = os.getenv('language')

INPUT_FILE_TYPE = os.getenv('input_file_type')

INPUT_SHEET_NAME = os.getenv('input_sheet_name')

INPUT_EXCEL_URL = os.getenv('input_excel_url')

#-------Schema validation----------

INPUT_SCHEMA_FAILURE_MAPPING = {
    'not_nullable':'No value found',
    "dtype('string[python]')":'Non-text such as number entered, please enter text only',
    'str_length(1, None)':'Text length was less than 1. Please enter something.'
}

#-----------Postgres queries----------------

CREATE_QUERY = """
                CREATE TABLE IF NOT EXISTS words_raw (
                id UUID PRIMARY KEY,
                OriginalWord VARCHAR(500) NOT NULL,
                Translation VARCHAR(500) NOT NULL,
                Topic VARCHAR(200),
                language VARCHAR(100) NOT NULL
                )"""
