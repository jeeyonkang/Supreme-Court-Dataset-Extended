from Case_builder import case_builder_main
from Convo_builder import convo_builder_main
from Utterance_builder import utterance_builder_main
from Convokit_converter import make_corpus_main
from datetime import datetime

import argparse
import logging
import os
import shutil

# Configure logging
log_dir = "./logs"
log_path = os.path.join(log_dir, "script_log.log")

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

current_date = datetime.now()
current_year = current_date.year

justice_info_filepath = './justice_info.csv'

def main() -> None:
    """
    Executes the main process for building and saving Convokit corpora across a range of years.

    This function parses command-line arguments to determine the start and end years
    and the timeout duration. It then iterates through each year in the specified range,
    invoking the case_builder_main, convo_builder_main, utterance_builder_main, and
    make_corpus_main functions sequentially to build and save the corpus data.
    """
    parser = argparse.ArgumentParser(description="Build and save Convokit corpora for Supreme Court cases.")
    parser.add_argument(
        "--start_year",
        dest="start_year",
        type=int,
        default=2019,
        help="The starting year for building the corpus (inclusive). Default is 1955."
    )
    parser.add_argument(
        "--end_year",
        dest="end_year",
        type=int,
        default=current_year,
        help=f"The ending year for building the corpus (inclusive). Default is the current year {current_year}."
    )
    parser.add_argument(
        "--timeout",
        dest="timeout",
        type=int,
        default=10,
        help="The timeout duration (in seconds) for web scraping operations. Default is 10 seconds."
    )

    args = parser.parse_args()

    start_year = args.start_year
    end_year = args.end_year
    timeout = args.timeout

    logging.info(f"Starting corpus building from year {start_year} to {end_year} with timeout {timeout} seconds.")

    for year in range(start_year, end_year + 1):
        logging.info(f"Processing year: {year}")
        try:
            case_builder = case_builder_main(year, justice_info_filepath, timeout)
            logging.info(f"Completed case_builder_main for year {year}")
        except Exception as e:
            logging.exception(f"Failed to build cases for year {year}: {e}")
            continue

        try:
            convo_builder = convo_builder_main(case_builder)
            logging.info(f"Completed convo_builder_main for year {year}")
        except Exception as e:
            logging.exception(f"Failed to build conversations for year {year}: {e}")
            continue

        try:
            utterance_builder = utterance_builder_main(convo_builder)
            logging.info(f"Completed utterance_builder_main for year {year}")
        except Exception as e:
            logging.exception(f"Failed to build utterances for year {year}: {e}")
            continue

        try:
            make_corpus_main(year, f"supreme-{year}")
            logging.info(f"Completed make_corpus_main for year {year}")
        except Exception as e:
            logging.exception(f"Failed to create corpus for year {year}: {e}")
            continue

    logging.info("Completed corpus building for all specified years.")


if __name__ == "__main__":
    main()
