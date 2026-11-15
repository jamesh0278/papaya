import pandas as pd
import logging
import openpyxl
from typing import Optional

from pipeline_constants.constants import (
    INPUT_LANGUAGE,
    INPUT_FILE_TYPE,
    INPUT_SHEET_NAME,
    INPUT_EXCEL_URL
)

from extraction.utils import (
    clean_df,
    get_uuid,
    import_excel_or_csv, 
    import_in_postgres,
    reorder_cols,
    validate_input
)

LANGUAGE = INPUT_LANGUAGE

FILE_TYPE = INPUT_FILE_TYPE

SHEET_NAME = INPUT_SHEET_NAME

EXCEL_URL = INPUT_EXCEL_URL

#import data
if FILE_TYPE == 'Excel':

    import_file = import_excel_or_csv(EXCEL_URL, FILE_TYPE, SHEET_NAME)

elif FILE_TYPE == 'CSV':

    import_file = import_excel_or_csv(EXCEL_URL, FILE_TYPE)

#Check correct schema 

import_file, invalid_rows = validate_input(import_file)

#clean up data

import_file = clean_df(import_file)

import_file['language'] = LANGUAGE

print(import_file)

#Create deterministic id
import_file = get_uuid(import_file)

#Reorder columns
import_file = reorder_cols(import_file)

#load into postgresql 
import_in_postgres(import_file, 'raw')