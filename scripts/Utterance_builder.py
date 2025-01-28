"""
The Utterance_builder class builds Utterance-level, as well as Speaker-level information, 
for the year given in the Convo_builder object(which is a parameter for the class).
"""

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from Case import *
from Conversation import *
from Speaker import *
from Utterance import *
from Case_builder import *
from Convo_builder import *

from bs4 import BeautifulSoup
import json
import logging
import os
import pandas as pd
import shutil

# Configure logging
log_dir = "./logs"
log_path = os.path.join(log_dir, "Utterance_builder_log.log")

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


class Utterance_builder:
    """
    Class to build utterances related to specific conversations within cases,
    whose information is built through a Convo_builder object.
    This class also builds Speaker objects across the cases, then writes 
    JSONL and CSV files with the compiled list of Speakers.
    """

    def __init__(self, convo_builder: Convo_builder):
        """
        Initializes the Utterance_builder object related to specific conversations, 
        whose information is built through a Convo_builder object.

        Args:
        - convo_builder (Convo_builder): An instance of a Convo_builder object with attributes of year,
          all_cases, all_convos, dropped_cases, and timeout.
        """
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.all_cases = convo_builder.all_cases
            self.all_convos = convo_builder.all_convos
            self.year = convo_builder.year
            self.timeout = convo_builder.timeout
            self.dropped_cases = convo_builder.dropped_cases

            self.all_utterances = []
            self.cache_dir = "./cache/"
            self.all_speakers = []
            self.all_speaker_names = []
            os.makedirs(self.cache_dir, exist_ok=True)
            logging.info("Initialized Utterance_builder")
        except WebDriverException as e:
            logging.critical(f"WebDriver initialization failed for Utterance_builder: {e}")
            raise e
        except Exception as e:
            logging.critical(f"Unexpected error during Utterance_builder initialization: {e}")
            raise e

    def get_transcript_soup(self, case: Case, convo: Conversation) -> Optional[BeautifulSoup]:
        """
        Retrieves and parses the HTML content of the transcript page within an iframe.

        Args:
        - case (Case): An instance of the Case class.
        - convo (Conversation): An instance of the Conversation class. 
          This conversation is an oral argument from the given case.

        Returns:
        - Optional[BeautifulSoup]: A BeautifulSoup object of the transcript page if successful, otherwise None.
        """
        cache_filename = f"{case.id}.{convo.id}.html"
        cache_path = os.path.join(self.cache_dir, cache_filename)
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as file:
                    page_content = file.read()
                logging.info(f"Loaded cached transcript page for case: {case.id}")
            else:
                soup = get_case_soup(case, self.driver, "transcript", self.dropped_cases, self.timeout)
                if not soup:
                    logging.warning(f"Unable to retrieve soup for case {case.id}")
                    return None
                
                #find the oral argument element through the conversation id
                oral_arg = soup.find('a', {'id': convo.id})
                if not oral_arg:
                    logging.warning(f"No oral argument found with ID {convo.id} for case {case.id}")
                    return None
                transcript_url = oral_arg.get("iframe-url", "")

                if not transcript_url:
                    logging.warning(f"No iframe URL found for conversation {convo.id} in case {case.id}")
                    return None

                self.driver.get(transcript_url)

                WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//section[@class='transcript-section ng-scope']"))
                )
                WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//section[@class='transcript-turn ng-scope']"))
                )
                WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//h4[@class='ng-binding']"))
                )

                page_content = self.driver.page_source

                with open(cache_path, 'w', encoding='utf-8') as file:
                    file.write(page_content)
                logging.info(f"Cached transcript page for case: {case.id} and convo: {convo.id}")

            transcript_soup = BeautifulSoup(page_content, 'html.parser')
            logging.info(f"Scraped and cached transcript page for case: {case.id} convo: {convo.id}")
            return transcript_soup

        except AttributeError as e:
            logging.exception(f"Attribute error while locating transcript {case.id}, convo {convo.id}: {e}")
            return None
        except Exception as e:
            logging.exception(f"Unexpected error accessing transcript for case {case.id}, convo {convo.id}: {e}")
            return None

    def build_all_utterance_info(self) -> None:
        """
        Iterates through all cases and their associated conversations to build utterance information.
        """
        if not self.all_cases:
            logging.warning("No cases available to build utterances.")
            return

        for case in self.all_cases:
            convos_for_case = self.get_convos_for_case(case)
            if not convos_for_case:
                logging.warning(f"No conversations found for case {case.id}.")
                continue
            for convo in convos_for_case:
                self.build_utterance_info_for_convo(case, convo)

    def get_convos_for_case(self, case: Case) -> list:
        """
        Retrieves the list of conversations for a given case.

        Args:
        - case (Case): An instance of the Case class.

        Returns:
        - list: A list of Conversation instances associated with the case.
        """
        try:
            return case.convos
        except AttributeError as e:
            logging.error(f"The case object does not have a 'convos' attribute: {e}")
            return []

    def build_utterance_info_for_convo(self, case: Case, convo: Conversation) -> None:
        """
        Processes a single conversation within a case to extract and build utterances.

        Args:
        - case (Case): An instance of the Case class.
        - convo (Conversation): An instance of the Conversation class.
        """
        transcript_soup = self.get_transcript_soup(case, convo)
        if not transcript_soup:
            logging.warning(f"No transcript soup available for case {case.id}, convo {convo.id}")
            return

        # each section is separated by a bar in the transcript, and is a separate element in the html
        sections = transcript_soup.find_all(class_='transcript-section ng-scope')
        if not sections:
            logging.warning(f"No transcript sections found for case {case.id}, convo {convo.id}")
            return
        else:
            logging.info(f"Transcript sections found for case {case.id}, convo {convo.id}")

        for section_no, section in enumerate(sections, start=1):
            self.process_section(section, case, convo, section_no)

    def process_section(self, section: BeautifulSoup, case: Case, convo: Conversation, section_no: int) -> None:
        """
        Processes a single transcript section to extract utterances.

        Args:
        - section (BeautifulSoup): A BeautifulSoup object representing a transcript section.
        - case (Case): An instance of the Case class.
        - convo (Conversation): An instance of the Conversation class.
        - section_no (int): The section number within the transcript.
        """
        utterances = section.find_all(class_='transcript-turn ng-scope')
        if not utterances:
            logging.warning(f"No utterances found in section {section_no} for case {case.id}, convo {convo.id}")
            return

        logging.info(f"Processing section {section_no} for case {case.id}, convo {convo.id}")

        previous_id = ''
        for utterance_no, u in enumerate(utterances, start=1):
            convo = self.process_utterance(u, case, convo, section_no, utterance_no, previous_id)

    def process_utterance(self, u: BeautifulSoup, case: Case, convo: Conversation, section_no: int, utterance_no: int, previous_id: str) -> Conversation:
        """
        Processes a single utterance element to create and store an Utterance object.

        Args:
        - u (BeautifulSoup): A BeautifulSoup object representing a single utterance.
        - case (Case): An instance of the Case class.
        - convo (Conversation): An instance of the Conversation class.
        - section_no (int): The section number within the transcript.
        - utterance_no (int): The utterance number within the section.
        - previous_id (str): The ID of the previous utterance for reply tracking.

        Returns:
        - Conversation: The updated Conversation object with the convo.utterances attribute updated.
        """
        try:
            utter = Utterance()
            utter.case_id = case.id
            utter.conversation_id = convo.id
            utter.id = f"{convo.id}__{section_no}_{str(utterance_no).zfill(3)}"

            # Extract speaker name
            speaker_tag = u.find(class_='ng-binding')
            speaker_name = speaker_tag.get_text(strip=True) if speaker_tag else "Unknown Speaker"
            utter.speaker = speaker_name

            # Get or create Speaker object
            speaker_obj = self.get_or_create_speaker(speaker_name, case)
            utter.speaker_type = speaker_obj.type

            # Assign side based on speaker type
            if utter.speaker_type == 'A':
                utter.side = self.get_advocate_side(speaker_name, case)
            else:
                utter.side = ''

            # Assign reply_to
            utter.reply_to = previous_id

            # Extract utterance text and timestamps
            text, start_times, stop_times = self.extract_text_and_timestamps(u)
            utter.text = text
            utter.start_times = start_times
            utter.stop_times = stop_times

            # Assign timestamp
            utter.timestamp = start_times[0] if start_times else ""

            convo.utterances.append(utter.id)
            self.all_utterances.append(utter)
            logging.debug(f"Added Utterance ID: {utter.id} for case {case.id}, convo {convo.id}")

            # Update previous_id for the next utterance
            previous_id = utter.id
            return convo
        except Exception as e:
            logging.exception(f"Error processing utterance in section {section_no} for case {case.id}, convo {convo.id}: {e}")
            return convo

    def get_or_create_speaker(self, speaker_name: str, case: Case) -> Speaker:
        """
        Retrieves an existing Speaker object or creates a new one if it doesn't exist.

        Args:
        - speaker_name (str): The name of the speaker.
        - case (Case): An instance of the Case class.

        Returns:
        - Speaker: A Speaker object.
        """
        if speaker_name in self.all_speaker_names:
            # Retrieve existing speaker
            index = self.all_speaker_names.index(speaker_name)
            return self.all_speakers[index]
        else:
            # Create a new speaker object
            speaker_obj = self.make_speaker_obj(speaker_name, case)
            logging.info(f"Created Speaker instance for speaker '{speaker_name}' with type '{speaker_obj.type}'")

            if speaker_obj not in self.all_speakers:
                # Add to speakers list
                self.all_speakers.append(speaker_obj)
                self.all_speaker_names.append(speaker_name)

            return speaker_obj

    def make_speaker_obj(self, speaker_name: str, case: Case) -> Speaker:
        """
        Helper function to match the speaker_name to their type and id,
        and return a Speaker object.

        Args:
        - speaker_name (str): Name of the speaker.
        - case (Case): The case for which to check if the speaker is an advocate or not.

        Returns:
        - Speaker: An instance of the Speaker class, with the speaker's id, name, and type.
        """
        try:
            df = pd.read_csv('justice_info.csv')
        except FileNotFoundError:
            logging.exception("Justice names conversion file 'justice_info.csv' not found.")
            return Speaker(id="", name=speaker_name, type="")
        except pd.errors.ParserError as e:
            logging.exception(f"Error parsing 'justice_info.csv': {e}")
            return Speaker(id="", name=speaker_name, type="")
        except Exception as e:
            logging.exception(f"Unexpected error reading 'justice_info.csv': {e}")
            return Speaker(id="", name=speaker_name, type="")

        try:
            # If the speaker is in the justice_info.csv, they are a justice
            if speaker_name in df['justice_first_name_first'].values:
                speaker_type = "J"
                id_ = df.loc[df['justice_first_name_first'] == speaker_name, 'justice_id'].values[0]
            # If the speaker is in the case's advocate list, they are an advocate
            elif speaker_name in case.advocates:
                speaker_type = "A"
                id_ = convert_name(speaker_name)
            # Otherwise, the speaker's type is unknown
            else:
                speaker_type = "U"
                id_ = convert_name(speaker_name)
                logging.warning(f"No speaker type found for speaker '{speaker_name}' in case {case.id}")

            speaker_object = Speaker(id=id_, name=speaker_name, type=speaker_type)
            logging.debug(f"Created Speaker object: {speaker_object}")
            return speaker_object
        except IndexError:
            logging.warning(f"No justice_id found for speaker '{speaker_name}' in case {case.id}")
            return Speaker(id="", name=speaker_name, type="")
        except Exception as e:
            logging.exception(f"Error creating Speaker object for '{speaker_name}' in case {case.id}: {e}")
            return Speaker(id="", name=speaker_name, type="")

    def extract_text_and_timestamps(self, utterance_element: BeautifulSoup) -> tuple:
        """
        Extracts the text and timestamps from a single utterance element.

        Args:
        - utterance_element (BeautifulSoup): A BeautifulSoup object representing a single utterance.

        Returns:
        - tuple: A tuple containing concatenated text, list of start times, and list of stop times.
        """
        text = ""
        start_times = []
        stop_times = []

        for sentence in utterance_element.find_all('p'):
            text += sentence.get_text(strip=True) + " "
            start_time = sentence.get('start-time')
            stop_time = sentence.get('stop-time')
            if start_time:
                start_times.append(float(start_time))
            if stop_time:
                stop_times.append(float(stop_time))

        return text.strip(), start_times, stop_times

    def get_case_id(self, case: Case) -> str:
        """
        Retrieves the ID of the given case.

        Args:
        - case (Case): An instance of the Case class.

        Returns:
        - str: The ID of the case.
        """
        return case.id

    def get_conversation_id(self, convo: Conversation) -> str:
        """
        Retrieves the ID of the given conversation.

        Args:
        - convo (Conversation): An instance of the Conversation class.

        Returns:
        - str: The ID of the conversation.
        """
        return convo.id

    def get_advocate_side(self, speaker_name: str, case: Case) -> str:
        """
        Retrieves the side associated with an advocate.

        Args:
        - speaker_name (str): The name of the advocate.
        - case (Case): An instance of the Case class. Assumes the speaker is in case.advocates.

        Returns:
        - str: The side of the advocate.
        """
        try:
            return case.advocates[speaker_name]['side']
        except KeyError:
            logging.warning(f"Speaker '{speaker_name}' not found in case advocates for case {case.id}")
            return ''

    def make_utterances_to_dicts(self) -> list:
        """
        Converts all Utterance objects to dictionaries.

        Returns:
        - list: A list of all the utterance dictionaries.
        """
        dict_list = []
        try:
            for utterance in self.all_utterances:
                try:
                    utterance_dict = utterance.make_dict()
                    dict_list.append(utterance_dict)
                    logging.debug(f"Converted Utterance ID: {utterance.id} to dict for case {utterance.case_id}")
                except Exception as e:
                    logging.exception(f"Error converting Utterance ID {utterance.id} to dict for case {utterance.case_id}: {e}")
            return dict_list
        except Exception as e:
            logging.exception(f"Error in make_utterances_to_dicts: {e}")
            return []

    def write_for_all_utterances(self) -> None:
        """
        Writes information for all utterances to JSONL and CSV files.
        """
        output_directory = f"./output/{self.year}/"
        os.makedirs(output_directory, exist_ok=True)

        jsonl_filename = "utterance_info.jsonl"
        csv_filename = "utterance_info.csv"
        jsonl_path = os.path.join(output_directory, jsonl_filename)
        csv_path = os.path.join(output_directory, csv_filename)

        try:
            # Write information for each utterance in a dictionary, and dump to JSONL
            utterance_dict_list = self.make_utterances_to_dicts()

            with open(jsonl_path, 'w', encoding='utf-8') as f:
                for utterance_dict in utterance_dict_list:
                    json.dump(utterance_dict, f)
                    f.write('\n')
            logging.info(f"Successfully wrote JSONL for all utterances to {jsonl_path}")
        except IOError as e:
            logging.exception(f"IOError while writing JSONL for all utterances: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing JSONL for all utterances: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing JSONL for all utterances: {e}")

        try:
            all_utterances_df = pd.DataFrame(utterance_dict_list)
            all_utterances_df.to_csv(csv_path, index=False, mode='w')
            logging.info(f"Successfully wrote CSV for all utterances to {csv_path}")
        except IOError as e:
            logging.exception(f"IOError while writing CSV for all utterances: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing CSV for all utterances: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing CSV for all utterances: {e}")

    def write_for_all_speakers(self) -> None:
        """
        Writes information for all speakers to JSONL and CSV files.
        """
        output_directory = f"./output/{self.year}/"
        os.makedirs(output_directory, exist_ok=True)

        jsonl_filename = "speaker_info.jsonl"
        csv_filename = "speaker_info.csv"
        jsonl_path = os.path.join(output_directory, jsonl_filename)
        csv_path = os.path.join(output_directory, csv_filename)

        try:
            # Write information for each speaker in a dictionary, and dump to JSONL
            speaker_dict_list = [speaker.make_dict() for speaker in self.all_speakers]

            with open(jsonl_path, 'w', encoding='utf-8') as f:
                for speaker_dict in speaker_dict_list:
                    json.dump(speaker_dict, f)
                    f.write('\n')
            logging.info(f"Successfully wrote JSONL for all speakers to {jsonl_path}")
        except IOError as e:
            logging.exception(f"IOError while writing JSON for all speakers: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing JSON for all speakers: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing JSON for all speakers: {e}")

        try:
            all_speakers_df = pd.DataFrame(speaker_dict_list)
            all_speakers_df.to_csv(csv_path, index=False, mode='w')
            logging.info(f"Successfully wrote CSV for all speakers to {csv_path}")
        except IOError as e:
            logging.exception(f"IOError while writing CSV for all speakers: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing CSV for all speakers: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing CSV for all speakers: {e}")

    def clear_cache(self) -> None:
        """
        Clears all cached HTML files by removing and recreating the cache directory.
        """
        try:
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            logging.info("Cleared all cached HTML files.")
        except Exception as e:
            logging.exception(f"Error clearing cache: {e}")

    def __del__(self):
        """
        Destructor to ensure the WebDriver is properly closed.
        """
        try:
            self.driver.quit()
            logging.info("Closed WebDriver")
        except Exception as e:
            logging.warning(f"Error closing WebDriver: {e}")


def utterance_builder_main(convo_builder: Convo_builder):
    """
    Main function to build utterances and speakers from the input Convo_builder's year.
    Writes information to JSONL and CSV files and returns a Utterance_builder instance.

    Args:
    - convo_builder (Convo_builder): An instance of Convo_builder containing conversation data.

    Returns:
    - Utterance_builder: A completed Utterance_builder instance with processed utterances and speakers.
    """
    try:
        utterance_builder = Utterance_builder(convo_builder)
        utterance_builder.build_all_utterance_info()

        if utterance_builder.all_utterances:
            utterance_builder.write_for_all_utterances()
            utterance_builder.write_for_all_speakers()
            print(f"Built info for {len(utterance_builder.all_utterances)} utterances")
        else:
            logging.warning("No utterances to write.")

        return utterance_builder

    except Exception as e:
        logging.critical(f"Critical error in main execution: {e}")
