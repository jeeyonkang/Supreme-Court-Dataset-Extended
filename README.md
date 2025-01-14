## Supreme-Court-Dataset-Extended

### Convokit Supreme Court Oral Arguments dataset, years 2019-

The code in this repository extends the [Convokit Supreme Court Oral Arguments dataset](https://convokit.cornell.edu/documentation/supreme.html), whose information is based on the [Supreme Court database](http://scdb.wustl.edu/) and [Oyez](https://www.oyez.org/).

### Environment

This repository requires [convokit](https://convokit.cornell.edu/documentation/install.html), [selenium](https://www.selenium.dev/), and [beautifulsoup4](https://beautiful-soup-4.readthedocs.io/en/latest/) packages.

```
git clone https://github.com/jeeyonkang/Supreme-Court-Dataset-Extended.git
cd Supreme-Court-Dataset-Extended
conda env create -f environment.yml
conda activate scEnv
```

### Running the code

To run the code, run the following:

```
cd scripts
python script.py --start_year {start year} --end_year {end year} --timeout {timeout}
```

The `--start_year`, `--end_year`, `--timeout` fields are optional.

`--start_year` indicates the year for which to start building corpora(**inclusive**, defaults to 2019), `--end_year` indicates the for which to end building corpora(**inclusive**, defaults to the year in which the code is being run). `--timeout` indicates the timeout duration for selenium waits, in seconds(defaults to 10).

### Notes on the data

The script sequentially builds information for cases, conversations, and utterances and speakers for a given year. Each case, conversation, utterance, and speaker has a unique id, which is structured as such:

```
case_id : {year}_{docket_no} (*both year and docket_no are indicated in the SCDB file organized by case.)
  - convo_id : indicated in the transcript element of the Oyez page
  - convo_id : indicated in the transcript element of the Oyez page
    - utterance_id : {convo_id}__{section_no}_{utterance_no} (*section_no refers to the sections separated by bars in the Oyez transcript page, utterance_no refers to the number of the utterance in a certain section.
```

For example, the first utterance in the second section of a conversation with a convo_id of `12345` would be `12345__2_001`.

The speaker_id follows the Oyez format for converting between names listed in transcripts and IDs (i.e., replacing spaces with underscores and lowercasing).

**Case-level information**

- The script reads in the latest SCDB files, organized by both case and justices. It drops cases according to the criteria below. It then builds information for all the cases of a certain year.

- Dropped cases: Cases are dropped when either
  a) oral arguments do not exist, as indicated on the SCDB(the 'dateArgument' field is empty) or
  b) the Oyez page for the case does not exist.

The following are changes to the information of certain fields, compared to the pre-existing Convokit dataset:

- adv-side-inferred: This field is set to False for all cases in the current version of the script, due to the lack of information on how sides are inferred. Convokit documentation mentions that documentation on the heuristics is forthcoming.

- votes-side: If the win-side of a case is 2.0, we assume the vote was equally divided and we cannot infer which side the justice voted for. We provide -1.0 in this case.

- Though they are in the sample .jsonl file provided in the "Case information" section of the Convokit documentation, the "is_eq_divided" and "known_respondent_adv" fields are no longer provided in this script. This is per the most recent Convokit documentation.

**Speaker-level information**

The following are changes to the information of certain fields, compared to the pre-existing Convokit dataset:

- type: If the speaker's role is unknown, the type is marked as U.
  Though the original Convokit corpus' speaker dataframe marks unknown speaker roles as empty values, following the most recent documentation, this script marks them as U.

- role: Per the most recent documentation of Convokit, the 'role' of the speaker is no longer provided.

**Conversation-level information**

The following are changes to the information of certain fields, compared to the pre-existing Convokit dataset:

- advocates:

  - side: Convokit documentation states that "if no role is listed in Oyez, this is inferred via some heuristics (documentation forthcoming)." The current version of the script in this repository does not infer advocate sides and provides 3 for all advocates whose side is unclear.

### Testing

The following tests were performed to ensure the integrity of the corpus:

- Comparison between the 2019 corpus, as extracted by the script in this repository, and the pre-existing 2019 corpus in the Convokit dataset.

- Manual inspection of the 2020 corpus extracted by the script in this repository.

The testing is documented in more detail in the testing/compare.ipynb file.

### Additional notes

- `justice_info.csv` contains information about each justice's full name, their corresponding Oyez id(see Convokit documentation), and [scdb justice id](http://scdb.wustl.edu/documentation.php?var=justice#norms). When new justices are appointed to the Supreme Court, the file has to be updated with the new justice's information. The filepath to this file can be edited in the script.py file.

- As mentioned above, information on Oyez, including conversation ids, is constantly updated. To obtain accurate information, we recommend re-running the script every few months or years so that the most recent updates to Oyez are reflected in the data.

- The script does not parse the data, as some previous Convokit corpora do.
