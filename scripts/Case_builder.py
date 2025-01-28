"""
Downloads files from the Supreme Court Database. 
Contains helper functions and the Case_builder class to build Case-level information for a given year, 
based on the information from the Scdb files and the information scraped from Oyez.
"""


from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from Case import Case
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List

import re
import requests
import pandas as pd
import json
import logging
import os
import shutil
import zipfile
import sys

chrome_options = Options()
chrome_options.add_argument("--headless")

# Configure logging
log_dir = "./logs"
log_path = os.path.join(log_dir, "Case_builder_log.log")

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

# CSV file that contains each justice's name(spelled both last-name first and first-name first), 
# Oyez/convokit speaker id, and numeric justice no. in the SCDB files.
# justice_info_filepath = 'justice_info.csv'

def get_case_soup(case: Case, driver, element_to_find: str, dropped_cases: List['Case'], timeout: int = 10) -> Optional[BeautifulSoup]:
    """
    Retrieve and parse the HTML content of a case page. Uses Selenium to access the case URL
    and BeautifulSoup to parse the page source.

    Args:
    - case (Case): The case object to retrieve the soup for.
    - driver: The Selenium driver to use while scraping.
    - element_to_find (str): The element that must be found before timeout.
    - dropped_cases (List['Case']): A list of case objects that will be considered dropped.
    - timeout (int): How long (in seconds) the driver will wait for elements to load.

    Returns:
    - Optional[BeautifulSoup]: Parsed HTML content if successful, otherwise None.
    """
    cache_dir = './cache/'
    cache_filename = f"{case.id}.html"
    cache_path = os.path.join(cache_dir, cache_filename)
    os.makedirs(cache_dir, exist_ok=True)

    try:
        # If the parsed content exists in cache, load from cache
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as file:
                page_content = file.read()
            logging.info(f"Loaded cached page for case: {case.id}")

        else:
            driver.get(f"{case.url}")

            try:
                # Wait for the page title to load
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//h1[@ng-if='title']"))
                )
                # If the page title doesn't load, decide that the Oyez case page does not exist and drop the case.
            except TimeoutException:
                logging.warning(f"Timeout while waiting for title element for case: {case.id}")
                logging.warning(f"Dropping case {case.id} due to missing Oyez page")
                if case not in dropped_cases:
                    dropped_cases.append(case)
                return None

            # Wait for the desired element to load
            if element_to_find == "citation":
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//a[@citation='case.citation']"))
                )
            elif element_to_find == "transcript":
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//a[@type='oral_argument_audio']"))
                )
            elif element_to_find == "advocate":
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@class='advocate ng-scope']"))
                )

            page_content = driver.page_source
            logging.info(f"Scraped page for case: {case.id}")

            with open(cache_path, 'w', encoding='utf-8') as file:
                file.write(page_content)
            logging.info(f"Cached page for case: {case.id}")
            
        soup = BeautifulSoup(page_content, 'html.parser')
        logging.debug(f"Retrieved soup for case: {case.id}")
        return soup
    except WebDriverException as e:
        logging.exception(f"WebDriver error accessing case page: {case.id}")
        return None
    except Exception as e:
        logging.exception(f"Unexpected error accessing case page: {case.id}: {e}")
        return None

def build_transcript_info(case: Case, driver, dropped_cases: List['Case'], timeout: int = 10) -> Optional[list]:
    """
    Build transcript information for a case object's "transcript" variable, extracting oral argument
    details and compiling them into a list of dictionaries.

    Args:
    - case (Case): The case object to build transcripts for.
    - driver: The Selenium driver to use while scraping.
    - dropped_cases (List['Case']): A list of case objects that will be considered dropped.
    - timeout (int): How long (in seconds) the driver will wait for elements to load.

    Returns:
    - Optional[list]: A list of transcript dictionaries containing name, url, id, and case_id,
      or None if transcript data is unavailable.
    """
    try:
        if case in dropped_cases:
            logging.exception(f"Case {case.id} in dropped cases, passing transcript info building")
            return None

        case_id = case.id
        soup = get_case_soup(case, driver, "transcript", dropped_cases, timeout)
        if not soup:
            logging.warning(f"Passing transcript info building, transcript not found for case {case.id}")
            return None

        # There may be multiple oral arguments because some cases have oral rearguments
        oral_args = soup.find_all('a', {'type': 'oral_argument_audio'})
        result = []
        # The url, name, and transcript(conversation) id are in this element
        for oral_arg in oral_args:
            try:
                # Url for the transcript page
                url = oral_arg.get("iframe-url", "")
                # Name of the oral argument: Usually in the format of "Oral Argument - {Month Day, Year}"
                name = oral_arg.text.strip()
                # Transcript(conversation) id
                id_ = oral_arg.get("id", "")
                result.append({"name": name, "url": url, "id": id_, "case_id": case_id})
                logging.debug(f"Added transcript for oral argument ID: {id_}")
            except Exception as e:
                logging.exception(f"Error processing oral argument for case {case_id}: {e}")
        return result

    except Exception as e:
        logging.exception(f"An error occurred while processing transcripts for case: {case.id}: {e}")
        return []

def build_advocates(case: Case, driver, petitioner: str, respondent: str, dropped_cases: List['Case'], timeout: int = 10) -> Optional[dict]:
    """
    Build a dictionary of advocates for a case, extracting details from the case page
    such as name, role, and side.

    Args:
    - case (Case): The case object to build advocates for.
    - driver: The Selenium driver to use when scraping.
    - petitioner (str): The name of the petitioner.
    - respondent (str): The name of the respondent.
    - dropped_cases (List['Case']): A list of case objects that will be considered dropped.
    - timeout (int): How long (in seconds) the driver will wait for elements to load.

    Returns:
    - Optional[dict]: A dictionary of advocates keyed by name, or None if advocates are unavailable.
    """
    advocate_dict = {}
    try:
        if case in dropped_cases:
            logging.warning(f"Case {case.id} in dropped cases, passing advocate info building")
            return None

        soup = get_case_soup(case, driver, "advocate", dropped_cases, timeout)
        if not soup:
            logging.warning(f"Passing advocate building, advocates not found for case {case.id}")
            return None

        divs = soup.find_all(class_='advocate ng-scope')
        # For each advocate
        for div in divs:
            try:
                name_tag = div.find('a', class_='ng-binding')
                name = name_tag.get_text(strip=True) if name_tag else ""
                if not name:
                    logging.warning(f"No name found for advocate in case {case.id}")

                # Whether the advocate is for the respondent, petitioner, etc.
                role_tag = div.find('span', class_='description ng-binding')
                role = role_tag.get_text(strip=True) if role_tag else ""
                if not role:
                    logging.warning(f"No role found for advocate '{name}' in case {case.id}")

                speaker_id = convert_name(name) # The advocate's Oyez id
                # side: '0' for respondent, '1' for petitioner, '2' for amicus curiae or U.S., and '3' for unknown.
                side = get_advocate_side(role, petitioner=petitioner, respondent=respondent)
                advocate_dict[name] = {"id": speaker_id, "name": name, "role": role, "side": side}
                logging.debug(f"Added advocate: {name}")
            except Exception as e:
                logging.exception(f"Error processing advocate in case {case.id}: {e}")
        return advocate_dict
    except Exception as e:
        logging.exception(f"An error occurred while building advocates for case {case.id}: {e}")
        return advocate_dict

def convert_name(name: str) -> str:
    """
    Convert a name to a standardized ID format by lowercasing, removing punctuation,
    and replacing whitespace with underscores.

    Args:
    - name (str): The original name string.

    Returns:
    - str: The converted name in ID format, or an empty string on error.
    """
    try:
        name = name.lower()
        name = name.replace('.', '')
        name = name.replace(',', '')
        name = re.sub(r'\s+', '_', name)
        return name
    except Exception as e:
        logging.exception(f"Error converting name '{name}': {e}")
        return ""

def get_advocate_side(case: Case, role: str, petitioner: str, respondent: str) -> str:
    """
    Determine the side of the advocate based on the provided role. Returns '0' for respondent,
    '1' for petitioner, '2' for amicus curiae or U.S., and '3' for unknown.

    Args:
    - role (str): The role of the advocate (respondent, petitioner, amicus, etc.).
    - petitioner (str): The name of the petitioner.
    - respondent (str): The name of the respondent.

    Returns:
    - str: A single-digit string indicating the advocate side.
    """
    try:
        if f'respondent in {case.id}' in role.lower():
            return '0'
        elif f'petitioner in {case.id}' in role.lower():
            return '1'
        elif 'respondent' in role.lower() or respondent.lower() in role.lower() \
           or 'appellee' in role.lower() or 'defendant' in role.lower():
            return '0'
        elif 'petitioner' in role.lower() or petitioner.lower() in role.lower() \
             or 'appellant' in role.lower() or 'plaintiff' in role.lower() or 'applicant' in role.lower():
            return '1'
        elif 'amicus curiae' in role.lower() or 'united states' in role.lower() or 'u.s.' in role.lower():
            return '2'
        else:
            logging.warning(f"No side found for advocate with role: '{role}'")
            return '3'
    except Exception as e:
        logging.exception(f"Error determining side from role '{role}': {e}")
        return ''

def clear_cache(cache_dir: str) -> None:
    """
    Clear all cached HTML files by removing and recreating the specified directory.

    Args:
    - cache_dir (str): The path of the cache directory to clear.
    """
    try:
        shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        logging.info("Cleared all cached HTML files.")
    except Exception as e:
        logging.exception(f"Error clearing cache: {e}")

def download_scdb_files(current_year: int, save_path: str) -> Optional[int]:
    """
    Attempt to download the latest versions of SCDB files (by case and by justice), starting
    from the given current_year down to 2024.

    Args:
    - current_year (int): The current year to start checking for SCDB files.
    - save_path (str): The path where downloaded zip files will be saved.

    Returns:
    - Optional[int]: The publishing year for which the file was downloaded, or None if download failed.
    """
    try:
        for i in range(current_year - 2023):
            year = current_year - i
            if download_scdb_file_helper(year, save_path, "by case"):
                final_year = year
                break
            else:
                continue
    except Exception as e:
        logging.exception(f"Unexpected error downloading the Scdb file by case:", e)

    try:
        for i in range(current_year - 2023):
            year = current_year - i
            if download_scdb_file_helper(year, save_path, "by justice"):
                final_year = year
                break
            else:
                continue
    except Exception as e:
        logging.exception(f"Unexpected error downloading the Scdb file by justice:", e)

    return final_year

def download_scdb_file_helper(year: int, save_path: str, organized_by: str) -> bool:
    """
    Download a specific SCDB file (by case or by justice) published in a given year and extract it.

    Args:
    - year (int): The year to download data for.
    - save_path (str): The path where the downloaded zip file will be saved.
    - organized_by (str): Indicates whether the file is 'by case' or 'by justice'.

    Returns:
    - bool: True if download and extraction succeeded, False otherwise.
    """
    try:
        if organized_by == "by case":
            url = f"http://scdb.wustl.edu/_brickFiles/{year}_01/SCDB_{year}_01_caseCentered_Docket.csv.zip"
        if organized_by == "by justice":
            url = f"http://scdb.wustl.edu/_brickFiles/{year}_01/SCDB_{year}_01_justiceCentered_Docket.csv.zip"
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            # Write the downloaded zip file to save_path
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            # Unzip the zip file
            with zipfile.ZipFile(save_path, 'r') as zip_ref:
                zip_ref.extractall("./")
        logging.info(f"Scdb file {organized_by} downloaded successfully, saved to {save_path}")
        return True
    except requests.exceptions.RequestException as e:
        logging.exception("Note: Request errors downloading Scdb files for recent years are normal.\
            If file not found for recent years, we try again with an older year.\
            Request Error downloading the Scdb file %s: %s", organized_by, e)
        return False

class Case_builder:
    """
    Build case information by reading SCDB and Oyez data, then writing
    JSONL and CSV files with the compiled information.
    """

    def __init__(self, year: int, justice_info_filepath: str, timeout: int = 10):
        """
        Initialize the Case_builder with a specified year and timeout. Sets up the Selenium
        WebDriver, assigns SCDB file paths to empty strings, and prepares a list of cases.

        Args:
        - year (int): The year of the cases to build information for.
        - timeout (int): The timeout (in seconds) for Selenium waits.
        """
        try:
            current_date = datetime.now()
            self.current_year = current_date.year
            self.scdb_file_by_case = ""
            self.scdb_file_by_justice = ""
            self.year = year
            self.timeout = timeout
            self.justice_info_filepath = justice_info_filepath
            self.dropped_cases = []
            self.all_cases = []
            self.driver = webdriver.Chrome(options=chrome_options)
            logging.info("Initialized Case_builder with WebDriver and cache directory.")
        except WebDriverException as e:
            logging.exception("WebDriver initialization failed.")
            raise e
        except Exception as e:
            logging.exception(f"Unexpected error during initialization: {e}")
            raise e

    def get_scdb_files(self) -> None:
        """
        Retrieve SCDB file paths for the latest updated year by calling the download function.
        Sets internal attributes for case-centered and justice-centered CSV file paths.
        """
        latest_updated_year = download_scdb_files(self.current_year, 'scdb_files.zip')
        self.scdb_file_by_case = f"./SCDB_{latest_updated_year}_01_caseCentered_Docket.csv"
        self.scdb_file_by_justice = f"./SCDB_{latest_updated_year}_01_justiceCentered_Docket.csv"

    def read_scdb_by_case(self) -> None:
        """
        Read SCDB data organized by docket number, filter for arguments, and build Case instances
        with basic metadata (docket_no, year, petitioner/respondent, etc.).
        """
        try:
            raw_df = pd.read_csv(self.scdb_file_by_case, encoding='ISO-8859-1')
            df = raw_df.dropna(subset=['dateArgument'])  # Skip cases with no oral arguments
        except FileNotFoundError:
            logging.exception(f"SCDB case file not found: {self.scdb_file_by_case}")
            return
        except pd.errors.ParserError as e:
            logging.exception(f"Error parsing SCDB case file: {e}")
            return
        except Exception as e:
            logging.exception(f"Unexpected error reading SCDB by case: {e}")
            return
        
        try:
            # Subset the SCDB file(by case) by the desired year
            start_index = df[df['term'] == self.year].index[0]
            end_index = df[df['term'] == self.year].index[-1]
            df = df.loc[start_index:end_index]
        except Exception as e:
            logging.exception(f"Error subsetting SCDB case file by year: {e}")
            sys.exit("Error subsetting SCDB files by year, exiting program.")

        for index, row in df.iterrows():
            try:
                case = Case()
                year = row['term']
                docket_no = row['docket']

                case.id = f"{year}_{docket_no}"
                case.year = year
                case.title = self.convert_title(row['caseName'])

                petitioner_respondent = case.title.split(' v. ', 1)
                if len(petitioner_respondent) == 2:
                    case.petitioner = petitioner_respondent[0]
                    case.respondent = petitioner_respondent[1]
                else:
                    logging.warning(f"Unexpected caseName format: '{row['caseName']}'")
                    case.petitioner = petitioner_respondent[0]
                    case.respondent = ""

                case.docket_no = docket_no
                case.scdb_docket_id = row['docketId']
                temp_date = row['dateDecision']
                case.decided_date = self.convert_date(temp_date)
                case.url = f"https://www.oyez.org/cases/{year}/{docket_no}"
                case.court = f"{row['chief']} Court"
                case.win_side = row['partyWinning'] if row['partyWinning'] else -1.0
                case.win_side_detail = row['caseDisposition'] if row['caseDisposition'] else -1.0

                self.all_cases.append(case)
                logging.debug(f"Added case: {case.id}")
            except KeyError as e:
                logging.exception(f"Missing expected column in SCDB data: {e}")
            except Exception as e:
                logging.exception(f"Error processing row {index} in SCDB by docket: {e}")

    def read_scdb_by_justice(self) -> None:
        """
        Read SCDB data organized by justices and update the votes for each case. Must be
        called after read_scdb_by_case(). Iterates through self.all_cases and appends
        justice votes if found.
        """
        if not self.scdb_file_by_justice:
            logging.warning("No justice-centered SCDB file provided.")
            return

        try:
            raw_df = pd.read_csv(self.scdb_file_by_justice, encoding='ISO-8859-1')
            df = raw_df.dropna(subset=['dateArgument'])
        except FileNotFoundError:
            logging.exception(f"SCDB justice file not found: {self.scdb_file_by_justice}")
            return
        except pd.errors.ParserError as e:
            logging.exception(f"Error parsing SCDB justice file: {e}")
            return
        except Exception as e:
            logging.exception(f"Unexpected error reading SCDB by justice: {e}")
            return

        for case in self.all_cases:
            try:
                docket_no = case.docket_no
                filtered_df = df.loc[df['docket'] == docket_no]

                votes = {}
                votes_detail = {}

                for index, row in filtered_df.iterrows():
                    justice_name = self.convert_justices(self.justice_info_filepath, row['justice'])
                    votes[justice_name] = row['majority'] if row['majority'] else -1.0
                    votes_detail[justice_name] = row['vote'] if row['vote'] else -1.0

                case.votes = votes
                case.votes_detail = votes_detail
                case.votes_side = self.build_votes_side(case.win_side, case.votes)
                logging.debug(f"Updated votes for case: {case.id}")
            except KeyError as e:
                logging.exception(f"Missing expected column in justice SCDB data: {e}")
            except Exception as e:
                logging.exception(f"Error processing case {case.id} in SCDB by justice: {e}")

    def build_votes_side(self, win_side: float, votes: dict) -> dict:
        """
        Build a dictionary mapping each justice to whether they voted for the petitioning party,
        based on the overall win_side and the majority (2) vs. minority (1) assignment.

        Args:
        - win_side (float): Indicator of which side won (1.0 or 0.0, sometimes -1.0 if unknown).
        - votes (dict): Dictionary of justices to their majority votes.

        Returns:
        - dict: Maps each justice to an int (1 for yes, 0 for no, -1 for unknown).
        """
        votes_side = {}
        try:
            for justice, vote in votes.items():
                if (win_side == 1.0 and vote == 2.0) or (win_side == 0.0 and vote == 1.0):
                    vote_side = 1  # Voted for petitioning party
                elif (win_side == 1.0 and vote == 1.0) or (win_side == 0.0 and vote == 2.0):
                    vote_side = 0  # Did not vote for petitioning party
                else:
                    vote_side = -1  # Unknown
                votes_side[justice] = vote_side
            logging.debug("Inferred votes_side for justices.")
        except Exception as e:
            logging.exception(f"Error inferring vote sides: {e}")
        return votes_side

    def convert_title(self, title: str) -> str:
        """
        Convert a case title from SCDB (often in uppercase) to a more readable format,
        capitalizing only the first letter of each name and keeping certain words lowercase.

        Args:
        - title (str): The original case title (e.g., 'HOWELL v. HOWELL').

        Returns:
        - str: The reformatted title (e.g., 'Howell v. Howell').
        """
        lowercase_words = {
            'v', 'of', 'and', 'the', 'in', 'on', 'at', 'for', 'from', 'by', 'with',
            'about', 'against', 'between', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'to', 'up', 'down', 'out', 'over', 'under'
        }

        title_lower = title.lower()
        pattern = re.compile(r'\b\w+[.]?[,]?')

        def capitalize_match(match):
            word = match.group(0)
            stripped_word = re.sub(r'[.,]$', '', word)
            if stripped_word in lowercase_words:
                return stripped_word + word[len(stripped_word):]  # Keep punctuation
            else:
                return word.capitalize()

        formatted_title = pattern.sub(capitalize_match, title_lower)
        return formatted_title

    def convert_justices(self, justice_info_filepath, justice_no: int) -> str:
        """
        Convert a numeric justice ID from SCDB into a string ID (speaker ID), using
        a separate CSV file for mapping.

        Args:
        - justice_no (int): The numeric justice ID from SCDB.

        Returns:
        - str: The string justice ID, or an empty string if not found.
        """
        try:
            df = pd.read_csv(justice_info_filepath)
            justice_id = df.loc[df['justice_no'] == justice_no, 'justice_id'].values[0]
            return justice_id
        except FileNotFoundError:
            logging.exception("Justice names conversion file 'justice_info.csv' not found.")
            return ""
        except IndexError:
            logging.warning(f"No justice_id found for justice_no: {justice_no}")
            return ""
        except Exception as e:
            logging.exception(f"Error converting justice_no '{justice_no}' to initials: {e}")
            return ""

    def convert_date(self, date_str: str) -> str:
        """
        Convert a date string from the format 'MM/DD/YYYY' to 'Month Day, Year' format.
        Returns an empty string if conversion fails.

        Args:
        - date_str (str): The date in 'MM/DD/YYYY' format.

        Returns:
        - str: The date in 'Month DD, YYYY' format, or empty string if invalid.
        """
        try:
            date_obj = datetime.strptime(date_str, '%m/%d/%Y')
            return date_obj.strftime('%B %d, %Y')
        except ValueError as e:
            logging.exception("Error converting date to 'Month Date, Year' format")
            return ""

    def clean_citation_string(self, citation_str: str) -> str:
        """
        Remove non-breaking spaces and strip trailing '(YYYY)' from a citation string,
        returning the cleaned result.

        Args:
        - citation_str (str): The original citation containing non-breaking spaces and trailing info.

        Returns:
        - str: The cleaned citation string.
        """
        temp_str = citation_str.replace('\u00a0', ' ')
        cleaned_str = temp_str.rsplit(' (', 1)[0]  # remove trailing " (YYYY)"
        return cleaned_str

    def read_citation_oyez(self, case: Case) -> Optional[str]:
        """
        Retrieve the citation from an Oyez case page by parsing the relevant HTML element.
        Returns None if the case is dropped or the citation is unavailable.

        Args:
        - case (Case): The case object to retrieve the citation for.

        Returns:
        - Optional[str]: The citation string if found, otherwise None.
        """
        try:
            if case in self.dropped_cases:
                logging.warning(f"Case {case.id} in dropped cases, passing citation building")
                return None

            soup = get_case_soup(case, self.driver, "citation", self.dropped_cases, self.timeout)
            if not soup:
                logging.warning(f"Passing citation building, citation not found for case {case.id}")
                return None

            citation_element = soup.find('a', {'citation': "case.citation"})
            if citation_element:
                citation_inner_element = citation_element.find('span')
                citation_text = citation_inner_element.text.strip()
                return self.clean_citation_string(citation_text) if citation_text else ""
            else:
                logging.warning(f"No citation found for case {case.id}")
                return None
        except NoSuchElementException:
            logging.warning(f"No citation element found for case {case.id}")
            return None
        except Exception as e:
            logging.exception(f"An error occurred while retrieving the citation for case {case.id}: {e}")
            return None

    def remove_dropped_cases(self) -> None:
        """
        Remove any cases that have been dropped from self.all_cases. This is based on
        matching the unique IDs of dropped cases.
        """
        dropped_ids = set(case.id for case in self.dropped_cases)
        original_count = len(self.all_cases)
        self.all_cases = [case for case in self.all_cases if case.id not in dropped_ids]
        removed_count = original_count - len(self.all_cases)
        if removed_count > 0:
            logging.info(f"Removed {removed_count} dropped cases from all_cases.")
            logging.info(f"Dropped case IDs: {dropped_ids}")

    def build_other_info(self) -> None:
        """
        Compile additional information for each case, including transcripts, citations,
        and advocates. Then remove any dropped cases from the global list.
        """
        for case in self.all_cases:
            try:
                transcripts = build_transcript_info(case, self.driver, self.dropped_cases, self.timeout)
                citation = self.read_citation_oyez(case)
                advocates = build_advocates(
                    case, self.driver,
                    petitioner=case.petitioner,
                    respondent=case.respondent,
                    dropped_cases=self.dropped_cases,
                    timeout=self.timeout
                )
                case.transcripts = transcripts
                case.citation = citation
                case.advocates = advocates
                logging.debug(f"Built transcript, citation, advocate info for case: {case.id}")
            except Exception as e:
                logging.exception(f"Error building transcript, citation, advocate info for case {case.id}: {e}")
        self.remove_dropped_cases()

    def build_all_info(self) -> None:
        """
        Orchestrate the entire build process for all cases: fetching SCDB files,
        reading SCDB by docket and by justice, then building additional information.
        """
        try:
            self.get_scdb_files()
            self.read_scdb_by_case()
            self.read_scdb_by_justice()
            self.build_other_info()
            logging.info("Completed building all case information.")
        except Exception as e:
            logging.exception(f"Error building all info: {e}")

    def write_for_all_cases(self) -> None:
        """
        Write the compiled case information to a JSONL file and a CSV file in
        the output directory for the specified year.
        """
        output_directory = f"./output/{self.year}/"
        os.makedirs(output_directory, exist_ok=True)

        jsonl_filename = "case_info.jsonl"
        csv_filename = "case_info.csv"
        jsonl_path = os.path.join(output_directory, jsonl_filename)
        csv_path = os.path.join(output_directory, csv_filename)

        try:
            # Write information for each case in a dictionary, and dump to JSONL
            cases_list = [case.make_dict() for case in self.all_cases]

            with open(jsonl_path, 'w', encoding='utf-8') as f:
                for case_dict in cases_list:
                    json.dump(case_dict, f)
                    f.write('\n')
            logging.info(f"Successfully wrote JSONL for all cases to {jsonl_path}")
        except IOError as e:
            logging.exception(f"IOError while writing JSONL for all cases: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing JSONL for all cases: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing JSONL for all cases: {e}")
        
        try:
            all_cases_df = pd.DataFrame(cases_list)
            all_cases_df.to_csv(csv_path, index=False)
        except IOError as e:
            logging.exception(f"IOError while writing csv for all cases: {e}")
        except TypeError as e:
            logging.exception(f"TypeError while serializing csv for all cases: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while writing csv for all cases: {e}")

    def __del__(self):
        """
        Destructor ensures the WebDriver is properly closed when the Case_builder
        instance is destroyed.
        """
        try:
            self.driver.quit()
            logging.info("Closed WebDriver")
        except Exception as e:
            logging.warning(f"Error closing WebDriver: {e}")

def case_builder_main(year: int, justice_info_filepath: str, timeout: int):
    """
    Main function that drives the case-building process for a given year, including
    clearing the cache, building all case info, and writing outputs to disk.

    Args:
    - year (int): The term/year of the Supreme Court cases to build.
    - timeout (int): The timeout (in seconds) for Selenium waits.

    Returns:
    - Case_builder: A completed Case_builder instance with processed cases.
    """
    try:
        cases_builder = Case_builder(year, justice_info_filepath, timeout)
        clear_cache('./cache/')
        cases_builder.build_all_info()

        try:
            cases_builder.write_for_all_cases()
            logging.info("Completed writing a JSONL file with all cases info.")
        except Exception as e:
            logging.exception(f"An unexpected exception occurred writing all cases to JSON and CSV: {e}")
        print(f"Built info for {len(cases_builder.all_cases)} cases")
        return cases_builder
            
    except Exception as e:
        logging.critical(f"Critical error in main execution: {e}")
