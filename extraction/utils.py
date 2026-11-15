import pandas as pd
import openpyxl
import numpy as np
import pandera.pandas as pa
from pandera.errors import SchemaErrors
from typing import Optional, Union
from dotenv import load_dotenv
import os
import uuid
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

from pipeline_constants.constants import (
        CREATE_QUERY,
        TOPIC, 
        INPUT_SCHEMA_FAILURE_MAPPING, 
        PROJECT_ROOT
        )

def import_excel_or_csv(URL: str, file_type: str, sheet=None) -> pd.DataFrame:
    """Function that imports the input file. Input must either be a csv or an excel file

        Args:
            URL (str): The location of the file of interest

            file_type (str): Accepts either Excel or CSV

            sheet (None, str): By default this is None, but if file_type is excel then this will be the sheet name you want to import

        Returns:

            pd.DataFrame: A Pandas Dataframe comprising the raw data from the CSV or Excel file.
    
    """

    if file_type == 'Excel':

        file = pd.read_excel(URL, sheet_name=sheet)

    elif file_type == 'csv':

        file = pd.read_csv(URL)

    return file 


#-------Clean Functions--------------

def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Function that does some basic cleaning of file including
    deduplication, removing whitespaces and removing any NULL values

    Args:
        df (pd.DataFrame): Input dataframe with file data

    Return:
        df (pd.DataFrame): Cleaned dataframe
    
    """

    #Deduplicate data
    df = df.drop_duplicates(keep='last')
    
    for column in df.columns:

    #Remove any white spaces
        
        df[column] = df[column].str.strip()
 
    #Fill blanks in topic with 'Other'

        if column == 'Topic':
            df[column] = df[column].fillna('Other')

    return df

def reorder_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Simple function that reorders the columns and 
    adds topic column as null if topic not added so that it fits with DB schema
    
    Args:
        df (pd.DataFrame): Input dataframe with wrongly ordered columns

    Return:
        df (pd.DataFrame): Dataframe with reordered columns
    """

    if 'Topic' not in df.columns:
        df['Topic'] = np.Nan
    
    #Get all columns excluding ID

    if 'id' in df.columns:

        df_columns_wo_ID = ['id'] + [c for c in df.columns if c != 'id']

        df = df[df_columns_wo_ID]

        return df
        
    else:
        raise('ID column missing.')
#------Create unique identifier----------

def get_uuid(df: pd.DataFrame) -> pd.DataFrame:

    """Create a deterministic uuid for each original word-translation-topic combination
    
        Args:
            df (pd.DataFrame): Input dataframe

        Return:
            df (pd.DataFrame): Dataframe with new id
    """

    
    df['id'] = df.apply(assign_id, axis=1)
    
    return df

def assign_id(row): 

    #Create unique id structure
    namespace = uuid.UUID("12345678-1234-5678-1234-567812345678")

    #Create the combined string
    if TOPIC:
        string_id =  'OriginalWord' + ':' + row['OriginalWord'] + ':' + 'Translation' + ':' + row['Translation'] + ':' + 'Topic' + ':' + row['Topic'] + ':' + 'language' + ':' + row['language']

    unique_id = str(uuid.uuid5(namespace, string_id))

    return unique_id


#------Validation Functions----------

def validate_input(df: pd.DataFrame) -> pd.DataFrame:

    #Check that there are at least 3 columns. Original word, translation and topic (optional)

    df = check_column_count(df)

    #Only keep those 2/3 columns and reorder them

    df = check_column_names_reorder(df)

    #do a schema check

    df, failed_rows = validate_input_schema(df)

    return df, failed_rows

def check_column_count(df: pd.DataFrame) -> pd.DataFrame: 

    """Check that input file has minimum amount of columns needed
    
        Args:
            df (pd.DataFrame): Input dataframe with raw data
            
        Return:
            df (pd.DataFrame): Only return df if there are at least 2 or 3 columns. If less then raise error"""

    no_columns = len(df.columns)

    if TOPIC and no_columns < 3:
        raise Exception('Validation Failed. Please ensure you have at least 3 columns (Original word, translation and topic)')
    elif not TOPIC and no_columns < 2:
        raise Exception('Validation Failed. Please ensure')
    else:
        print('Column number is adequate. Moving on.')
        return df

def check_column_names_reorder(df: pd.DataFrame) -> pd.DataFrame:

    """Check that the 2/3 key columns are present
    
        Args:
            df (pd.DataFrame): Input dataframe with raw data

        Return:
            df (pd.DataFrame): Only return df if the columns are correctly named    
    """

    if TOPIC:

        essential_columns = ['OriginalWord', 'Translation', 'Topic']

    else:

        essential_columns = ['OriginalWord', 'Translation']

    #Check if each column name appears in the dataframe, it not raise error
    missing_cols = []

    for col_name in essential_columns:
        if col_name in df.columns:
            print(f'{col_name} found')
            continue
        else:
            missing_cols.append(col_name)

    if len(missing_cols) == 0:
        print('All required columns are present. Continuing')

        #Only add the relevant columns going forward
        df = df[essential_columns]

        return df
    else:
        raise Exception(f'''There are {len(missing_cols)} columns names are either incorrect or missing. /n
                            These are {missing_cols}''')


def validate_input_schema(df: pd.DataFrame) -> pd.DataFrame:

    if TOPIC is False:

        schema = pa.DataFrameSchema(
            columns={
                "OriginalWord": pa.Column(str,
                                        checks=[
                                            pa.Check.str_length(min_value=1),
                                            pa.Check(lambda x: x.strip() != '', element_wise=True)
                                        ],
                                        nullable=False),
                "Translation": pa.Column(str,
                                        checks=[
                                            pa.Check.str_length(min_value=1),
                                            pa.Check(lambda x: x.strip() != '', element_wise=True)
                                            ],
                                            nullable=False)


            }
        )

    elif TOPIC:

           schema = pa.DataFrameSchema(
                    columns={
                        "OriginalWord": pa.Column(str,
                                                checks=[
                                                    pa.Check.str_length(min_value=1),
                                                    pa.Check(lambda x: x.strip() != '', element_wise=True)
                                                ],
                                                nullable=False),
                        "Translation": pa.Column(str,
                                                checks=[
                                                    pa.Check.str_length(min_value=1),
                                                    pa.Check(lambda x: x.strip() != '', element_wise=True)
                                                    ],
                                                    nullable=False),
                        "Topic": pa.Column(str, nullable=True)
        
        
                    }
                )
    
    try:
        validated_df = schema.validate(df, lazy=True)

        failure_rows_with_original_data = None


    except SchemaErrors as err:
        #Get list of rows that failed the validation, with reasons why
        failure_rows = err.failure_cases

        #replace error reasons with easier to read explanations
        failure_rows['check'] = failure_rows['check'].replace(INPUT_SCHEMA_FAILURE_MAPPING)

        
        #Only get columns of interest and rename them
        failure_rows = failure_rows[['index', 'column', 'failure_case', 'check']].rename(
            columns={'index': 'Row_Number',
                     'column': 'Column_with_Issue',
                     'failure_case': 'Failure_Example',
                     'check':'Cause_of_Failure'}
        )

        #Remove any rows without an index associated
        failure_rows = failure_rows[failure_rows['Row_Number'].notnull()].set_index('Row_Number')

        #Get information on orginal word, translation and topic from input df
        failure_rows_with_original_data = pd.merge(failure_rows, df, left_index=True, right_index=True).reset_index().rename(
            columns={
                'OriginalWord':'InputFile_OriginalWord',
                'Translation':'InputFile_Translation',
                'Topic':'InputFile_Topic'
            }
        ).sort_values(by='Row_Number')

        #Filter main df to remove invalid rows
        invalid_rows_to_remove = list(set(failure_rows_with_original_data['Row_Number'].tolist()))

        validated_df = df[~df.index.isin(invalid_rows_to_remove)]

        #Get actual Row number in source excel/csv/sheets file
        failure_rows_with_original_data['Row_Number'] = failure_rows_with_original_data['Row_Number'] + 1
        
        #Fill out nulls
        failure_rows_with_original_data['InputFile_Topic'] = failure_rows_with_original_data['InputFile_Topic'].fillna('No Topic')


    return validated_df, failure_rows_with_original_data

#--------------Import into SQL----------------------

def import_in_postgres(df,stage):

    #Connect to the table
    
    load_dotenv()

    DATABASE = os.getenv("DATABASE")
    USER_NAME = os.getenv("USERNAME")
    HOST = os.getenv("HOST")
    PASSWORD = os.getenv("PASSWORD")
    PORT = os.getenv("port")
    
    conn = psycopg2.connect(database=DATABASE,
                            user=USER_NAME,
                            host=HOST,
                            password=PASSWORD,
                            port=PORT)

    cur = conn.cursor()
    
    #Create table if not there already and get table name
    if stage == 'raw':
        cur.execute(CREATE_QUERY)
        table_name = 'words_raw'
        conn.commit()

        print('table made')

    
    #Insert data into the database
    values = [row for row in df.to_numpy()]

    #Get number of columns
    col_names = "(" + ','.join(df.columns.tolist()) +   ")"


    insert_statement = f"INSERT INTO {table_name}{col_names} VALUES %s"

    execute_values(cur, insert_statement, values)

    #Commit changes
    conn.commit()

    #Close connection
    cur.close()
    conn.close()

