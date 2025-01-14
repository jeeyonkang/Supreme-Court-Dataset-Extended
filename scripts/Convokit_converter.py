from tqdm import tqdm
from convokit import Corpus, Speaker, Utterance, Conversation

import pandas as pd
import json
import logging
import os
import shutil

# Configure logging
log_dir = "./logs"
log_path = os.path.join(log_dir, "Convokit_converter_log.log")

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

def make_data(txt_file_path: str) -> list:
    """
    Reads all lines from a text file and returns them as a list.
    
    Args:
    - txt_file_path (str): The path to the text file to be read.
    
    Returns:
    - list: A list of strings, each representing a line from the file.
    """
    with open(txt_file_path, "r", encoding='utf-8', errors='ignore') as f:
        data = f.readlines()
    return data


def make_txt_and_data(year: int, output_folder_path: str = './output/') -> dict:
    """
    Converts JSONL files to TXT files with a specific delimiter and reads the data.
    
    Args:
    - year (int): The year for which to process the data.
    - output_folder_path (str): The base path where output files are stored.
    
    Returns:
    - dict: A dictionary containing lists of speaker_data, convo_data, and utterance_data.
    """
    utt_jsonl_path = os.path.join(output_folder_path, f"{year}/utterance_info.jsonl")
    convo_jsonl_path = os.path.join(output_folder_path, f"{year}/convo_info.jsonl")
    speaker_jsonl_path = os.path.join(output_folder_path, f"{year}/speaker_info.jsonl")    

    utt_txt_path = os.path.join(output_folder_path, f"{year}/utterance_info.txt")
    convo_txt_path = os.path.join(output_folder_path, f"{year}/convo_info.txt")
    speaker_txt_path = os.path.join(output_folder_path, f"{year}/speaker_info.txt")

    jsonl_file_paths = [utt_jsonl_path, convo_jsonl_path, speaker_jsonl_path]
    txt_file_paths = [utt_txt_path, convo_txt_path, speaker_txt_path]
    file_paths = zip(jsonl_file_paths, txt_file_paths)

    for jsonl_path, txt_path in file_paths:
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as jsonl_file, open(txt_path, 'w', encoding='utf-8') as output_file:
                for line in jsonl_file:
                    row_data = json.loads(line)  # Parse each JSON line
                    row_values = [str(value) for value in row_data.values()]  # Convert each value to a string
                    output_file.write('+++$+++'.join(row_values) + '\n')
            logging.info(f"Converted {jsonl_path} to {txt_path}")
        except FileNotFoundError:
            logging.error(f"File not found: {jsonl_path}")
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in file {jsonl_path}: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error while converting {jsonl_path} to {txt_path}: {e}")

    speaker_data = make_data(speaker_txt_path)
    convo_data = make_data(convo_txt_path)
    utt_data = make_data(utt_txt_path)

    return {'speaker_data': speaker_data, 'convo_data': convo_data, 'utterance_data': utt_data}       


def make_corpus_speakers(year: int) -> dict:
    """
    Creates a dictionary of Speaker objects from speaker data for a given year.

    Args:
    - year (int): The year for which to create speakers.

    Returns:
    - dict: A dictionary mapping speaker IDs to Speaker objects.
    """
    data = make_txt_and_data(year)
    speaker_data = data['speaker_data']
    
    speaker_meta = {}
    for speaker in speaker_data:
        speaker_info = [info.strip() for info in speaker.split("+++$+++")]
        if len(speaker_info) >= 3:
            speaker_meta[speaker_info[0]] = {"name": speaker_info[1], "type": speaker_info[2]}
        else:
            logging.warning(f"Insufficient speaker information: {speaker_info}")

    corpus_speakers = {k: Speaker(id=k, meta=v) for k, v in speaker_meta.items()}

    return corpus_speakers


def make_corpus_utterances(year: int) -> dict:
    """
    Creates a dictionary of Utterance objects from utterance data for a given year.

    Args:
    - year (int): The year for which to create utterances.

    Returns:
    - dict: A dictionary mapping utterance IDs to Utterance objects.
    """
    utterance_corpus = {}
    data = make_txt_and_data(year)
    utterance_data = data['utterance_data']
    corpus_speakers = make_corpus_speakers(year)

    speaker_data = [
        {"speaker_id": speaker_id, **speaker.meta}  # Unpack meta into individual columns
        for speaker_id, speaker in corpus_speakers.items()
    ]
    
    df_speakers = pd.DataFrame(speaker_data)

    for utterance in tqdm(utterance_data, desc="Processing Utterances"):
        
        utterance_info = [info.strip() for info in utterance.split("+++$+++")]
        
        if len(utterance_info) < 11:
            logging.warning(f"Incomplete utterance information: {utterance_info}")
            continue
        
        try:
            id, text, speaker_name, conversation_id, case_id, speaker_type, side, start_times, stop_times, timestamp, reply_to \
                = utterance_info[0], utterance_info[1], utterance_info[2], utterance_info[3], utterance_info[4], \
                    utterance_info[5], utterance_info[6], utterance_info[7], utterance_info[8], utterance_info[9], utterance_info[10]
        except IndexError:
            logging.warning(f"Error unpacking utterance information: {utterance_info}")
            continue
        
        meta = {
            'id': id,
            'text': text,
            'speaker': speaker_name,
            'convo_id': conversation_id, 
            'case_id': case_id,
            'speaker_type': speaker_type,
            'side': side,
            'start_times': start_times, 
            'stop_times': stop_times,
            'timestamp':  timestamp,
            'reply_to': reply_to
        }

        matching_ids = df_speakers[df_speakers['name'] == speaker_name]['speaker_id'].tolist()
        if matching_ids:
            speaker_id = matching_ids[0]
        else:
            logging.warning(f"No matching speaker ID found for speaker '{speaker_name}' in utterance '{id}'")
            continue
        
        utterance_corpus[id] = Utterance(
            id=id,
            speaker=corpus_speakers[speaker_id], 
            conversation_id=conversation_id,
            reply_to=reply_to,
            timestamp=timestamp,
            text=text,
            meta=meta
        )

    print("Total number of utterances = {}".format(len(utterance_corpus)))
    return utterance_corpus


def make_corpus_conversations(year: int, corpus: Corpus) -> None:
    """
    Adds Conversation objects to the corpus based on conversation data for a given year.

    Args:
    - year (int): The year for which to create conversations.
    - corpus (Corpus): The Convokit Corpus object to which conversations will be added.
    """
    data = make_txt_and_data(year)
    convo_data = data['convo_data']

    for info in tqdm(convo_data, desc="Processing Conversations"):
        parts = info.split("+++$+++")
        if len(parts) < 6:
            logging.warning(f"Incomplete conversation information: {parts}")
            continue
        conversation_id, case_id, advocates, votes_side, win_side, utterances = parts
        meta = {
            'id': conversation_id,
            'case_id': case_id,
            'advocates': advocates,
            'votes_side': votes_side,
            'win_side': win_side
        }
        try:
            convo = Conversation(
                owner=corpus,
                id=conversation_id,
                utterances=utterances.split(','),  # Assuming utterances are comma-separated
                meta=meta
            )
            corpus.add_conversation(convo)
            logging.info(f"Added Conversation ID: {conversation_id} for case {case_id}")
        except Exception as e:
            logging.exception(f"Error adding Conversation {conversation_id} to corpus: {e}")


def create_new_corpus(year: int) -> Corpus:
    """
    Creates a new Convokit Corpus object with utterances and conversations for a given year.

    Args:
    - year (int): The year for which to create the corpus.

    Returns:
    - Corpus: A Convokit Corpus object containing the utterances and conversations.
    """
    utterance_corpus = make_corpus_utterances(year)
    utterance_list = list(utterance_corpus.values())
    new_corpus = Corpus(utterances=utterance_list)
    make_corpus_conversations(year, new_corpus)
    return new_corpus


def save_corpus(new_corpus: Corpus, name_of_corpus: str) -> None:
    """
    Saves the Convokit Corpus object to disk with the specified name.

    Args:
    - new_corpus (Corpus): The Convokit Corpus object to be saved.
    - name_of_corpus (str): The desired name for the saved corpus.
    """
    try:
        new_corpus.dump(name_of_corpus)
        logging.info(f"Successfully saved corpus as {name_of_corpus}")
    except Exception as e:
        logging.exception(f"Error saving corpus {name_of_corpus}: {e}")


def make_corpus_main(year: int, name_of_corpus: str) -> None:
    """
    Main function to create and save a Convokit Corpus for a specified year.

    Args:
    - year (int): The year for which to create the corpus.
    - name_of_corpus (str): The desired name for the saved corpus.
    """
    try:
        new_corpus = create_new_corpus(year)
        save_corpus(new_corpus, name_of_corpus)
        logging.info(f"Corpus creation and saving completed for year {year} as {name_of_corpus}")
    except Exception as e:
        logging.critical(f"Critical error in make_corpus_main execution: {e}")

# if __name__=="__main__":
#     make_corpus_main(2019, "new_corpus_2019")
