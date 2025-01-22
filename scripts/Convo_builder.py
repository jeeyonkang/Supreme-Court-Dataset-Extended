"""
The Convo_builder class builds Conversation-level information, 
for the year given in the Case_builder object(which is a parameter for the class).
"""

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from Case_builder import *
from Conversation import *
from Case import *

import json
import logging
import os
import pandas as pd
import shutil
import zipfile
import sys

# Configure logging
log_path = os.path.join(log_dir, "Convo_builder_log.log")

# Ensure the directory exists
os.makedirs(log_dir, exist_ok=True)

# Create the file if it doesn't exist
if not os.path.exists(log_path):
    with open(log_path, 'w') as file:
        pass

logging.basicConfig(
    filename=log_path,
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w',
    force=True
)

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")


class Convo_builder:
    """
    Class to build conversations related to specific cases, 
    whose information is built through a Case_builder object.
    """

    def __init__(self, case_builder: Case_builder):
        """
        Initializes the Convo_builder object.

        Args:
        - case_builder (Case_builder): An instance of a Case_builder object with attributes of year,
          all_cases, dropped_cases, and timeout.
        """
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.year = case_builder.year
            self.dropped_cases = case_builder.dropped_cases
            self.all_cases = case_builder.all_cases
            self.timeout = case_builder.timeout
            self.all_convos = []
            self.cache_dir = "./cache/"
            os.makedirs(self.cache_dir, exist_ok=True)
            logging.info("Initialized Convo_builder")
        except WebDriverException as e:
            logging.critical(f"WebDriver initialization failed for Convo_builder: {e}")
            raise e
        except Exception as e:
            logging.critical(f"Unexpected error during Convo_builder initialization: {e}")
            raise e

    def get_conversation_ids(self, case) -> list:
        """
        Retrieves conversation IDs for each oral argument associated with the case.

        Args:
        - case (Case): The case for which oral argument conversation IDs are to be retrieved.

        Returns:
        - list: A list of conversation IDs associated with the case.
        """
        conversation_ids = []
        # Extract conversation id's from the transcript 
        try:
            transcripts = case.transcripts
            for transcript_dict in transcripts:
                conversation_id = transcript_dict['id']
                if conversation_id:
                    conversation_ids.append(conversation_id)
                    logging.debug(f"Found convo ID: {conversation_id} for case {case.id}")
                else:
                    logging.warning(f"Oral argument without ID found in case {case.id}")
        except Exception as e:
            logging.exception(f"An error occurred while processing conversation_ids for case: {case.id}: {e}")
        return conversation_ids

    def build_convo_info(self) -> None:
        """
        Builds Conversation objects for each conversation ID and appends them to all_convos.
        """
        if not self.all_cases:
            logging.warning("No cases in all_cases list to build convos for")
            return

        for case in self.all_cases:
            try:
                conversation_id_list = self.get_conversation_ids(case)
                if not conversation_id_list:
                    logging.info(f"No conversations to build for case {case.id}")
                    continue

                convos_for_case = []
                for conversation_id in conversation_id_list:
                    try:
                        convo = Conversation()
                        convo.id = conversation_id
                        convo.case_id = case.id
                        convo.advocates = case.advocates
                        # convo.advocates = build_advocates(
                        #     case, self.driver, case.petitioner,
                        #     case.respondent, self.dropped_cases, timeout=self.timeout
                        # )
                        convo.votes_side = case.votes_side
                        convo.win_side = case.win_side
                        convos_for_case.append(convo)
                        self.all_convos.append(convo)
                        logging.info(f"Built Conversation ID: {conversation_id} for case {case.id}")
                    except Exception as e:
                        logging.exception(f"Error building Conversation {conversation_id} for case {case.id}: {e}")
                # Add conversation objects with completed information to the case object's convos variable
                case.convos = convos_for_case
            except Exception as e:
                logging.exception(f"Error in build_convo_info for case {case.id}: {e}")

    def make_convos_to_dicts(self) -> list:
        """
        Converts all Conversation objects to dictionaries.

        Returns:
        - list: A list of conversation dictionaries.
        """
        dict_list = []
        try:
            for convo in self.all_convos:
                try:
                    convo_dict = convo.make_dict()
                    dict_list.append(convo_dict)
                    logging.debug(f"Converted Conversation ID: {convo.id} to dict")
                except Exception as e:
                    logging.exception(f"Error converting Conversation ID {convo.id} to dict: {e}")
        except Exception as e:
            logging.exception(f"Error in make_convos_to_dicts: {e}")
        return dict_list

    def write_for_all_convos(self) -> None:
        """
        Writes information for all conversations to JSONL and CSV files.
        """
        output_directory = f"./output/{self.year}/"
        os.makedirs(output_directory, exist_ok=True)

        jsonl_filename = "convo_info.jsonl"
        csv_filename = "convo_info.csv"
        jsonl_path = os.path.join(output_directory, jsonl_filename)
        csv_path = os.path.join(output_directory, csv_filename)

        try:
            # Write information for each conversation in a dictionary, and dump to JSONL
            convos_list = [convo.make_dict() for convo in self.all_convos]

            with open(jsonl_path, 'w', encoding='utf-8') as f:
                for convo_dict in convos_list:
                    json.dump(convo_dict, f)
                    f.write('\n')
            logging.info(f"Successfully wrote JSONL for all convos to {jsonl_path}")
        except IOError as e:
            logging.exception(f"IOError while writing JSON for all convos: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing JSON for all convos: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing JSON for all convos: {e}")

        try:
            all_convos_df = pd.DataFrame(convos_list)
            all_convos_df.to_csv(csv_path, index=False, mode='w')
            logging.info(f"Successfully wrote CSV for all convos to {csv_path}")
        except IOError as e:
            logging.exception(f"IOError while writing CSV for all convos: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing CSV for all convos: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing CSV for all convos: {e}")

    def __del__(self):
        """
        Destructor to ensure the WebDriver is properly closed.
        """
        try:
            self.driver.quit()
            logging.info("Closed WebDriver for Convo_builder")
        except Exception as e:
            logging.warning(f"Error closing WebDriver for Convo_builder: {e}")


def convo_builder_main(case_builder: Case_builder):
    """
    Main function to build conversations from the input Case_builder's year.
    Writes information to JSONL and CSV files and returns a Convo_builder instance.

    Args:
    - case_builder (Case_builder): An instance of Case_builder containing case data.

    Returns:
    - Convo_builder: A completed Convo_builder instance with processed conversations.
    """
    try:
        convos_builder = Convo_builder(case_builder)
        clear_cache('./cache/')
        convos_builder.build_convo_info()

        # Write all convos to JSONL and CSV
        if convos_builder.all_convos:
            convos_builder.write_for_all_convos()
        else:
            logging.info("No conversations to write.")

        print(f"Built info for {len(convos_builder.all_convos)} convos")
        return convos_builder

    except Exception as e:
        logging.critical(f"Critical error in main execution: {e}")

if __name__ == "__main__":
    cases_builder = case_builder_main(year = 2019, justice_info_filepath = './justice_info.csv', timeout = 5)
    convo_builder_main(cases_builder)
