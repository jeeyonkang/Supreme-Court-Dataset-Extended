## Supreme-Court-Dataset-Extended

### Contact

Contact Jeeyon Kang (jk26@williams.edu) or Katie Keith (kak5@williams.edu) for questions or concerns.

### Convokit Supreme Court Oral Arguments dataset

The code in this repository extends the [Convokit Supreme Court Oral Arguments dataset](https://convokit.cornell.edu/documentation/supreme.html), by scraping data from [Oyez](https://www.oyez.org/). We also supplement data with the [Supreme Court database](http://scdb.wustl.edu/) (SCDB).

### Environment

This repository requires [convokit](https://convokit.cornell.edu/documentation/install.html), [selenium](https://www.selenium.dev/), and [beautifulsoup4](https://beautiful-soup-4.readthedocs.io/en/latest/) packages.

```
git clone git@github.com:jeeyonkang/Supreme-Court-Dataset-Extended.git
cd Supreme-Court-Dataset-Extended
conda env create -f environment.yml
conda activate scEnv
```

### Running the code

To scrape a particular time period of Supreme Court oral arguments (from Oyez), run the following:

```
cd scripts
python script.py --start_year {start year} --end_year {end year} --timeout {timeout}
```

Optional arguments:

- `--start_year` indicates the year for which to start building corpora(**inclusive**, defaults to 2019)
- `--end_year` indicates the for which to end building corpora(**inclusive**, defaults to the year in which the code is being run)
- `--timeout` indicates the timeout duration for selenium waits, in seconds (defaults to 10).

For example, to scrape data from the full year of 2020 run the following:

```
cd scripts
python script.py --start_year 2020 --end_year 2020
```

### Location of output

The generated corpora are saved in `~/.convokit/saved-corpora`.
Upon running the script, the `output` directory is created within the `script` directory. Within each `year` directory, there is case-level, conversation-level, utterance-level, and speaker-level meta data in `.jsonl` and `.csv` format(This is not the corpus).
**_For case-level meta data, look at the `case-info.jsonl` or `case-info.csv` files for each year within this `output` directory._**

### Notes on the data

The script sequentially builds information for cases, conversations, and utterances and speakers for a given year. Each case, conversation, utterance, and speaker has a unique id, which is structured as such:

```
- case_id : {year}_{docket_no} (*both year and docket_no are indicated in the SCDB file organized by case.)
- convo_id : indicated in the transcript element of the Oyez page
- utterance_id : {convo_id}__{section_no}_{utterance_no} (*section_no refers to the sections separated by bars in the Oyez transcript page, utterance_no refers to the number of the utterance in a certain section.
```

For example, the first utterance in the second section of a conversation with a convo_id of `12345` would be `12345__2_001`.

The `speaker_id` follows the Oyez format for converting between names listed in transcripts and IDs (i.e. replacing spaces with underscores and lowercasing).

**Case-level information**

- The script reads in the latest SCDB files, organized by both case and justices. It drops cases according to the criteria below. It then builds information for all the cases of a certain year.

- Dropped cases: Cases are dropped when either
  - a) oral arguments do not exist, as indicated on the SCDB(the 'dateArgument' field is empty) or
  - b) the Oyez page for the case does not exist.

The following are changes to the information of certain fields, compared to the pre-existing Convokit dataset:

- `adv-side-inferred`: This field is set to `False` for all cases in the current version of the script, due to the lack of information on how sides are inferred. Convokit documentation mentions that documentation on the heuristics is forthcoming.

- `votes-side`: Per the convokit documentation, this dictionary denotes whether each justice voted for the petitioning party. This is derived from the `win_side` and `votes_detail` information. If the `win_side` of a case is 2.0(according to the [Scdb documentation](http://scdb.wustl.edu/documentation.php?var=partyWinning), this means that a justice's "favorable disposition for petitioning party (is) unclear"), we assume the vote was equally divided and we cannot infer which side the justice voted for. We provide -1.0 in this case.

- Though they are in the `sample.jsonl` file provided in the "Case information" section of the Convokit documentation, the `"is_eq_divided"` and `"known_respondent_adv"` fields are no longer provided in this script. This is per the most recent Convokit documentation.

**Speaker-level information**

The following are changes to the information of certain fields, compared to the pre-existing Convokit dataset:

- `type:` If the speaker's role is unknown, the type is marked as `U`.
  Though the original Convokit corpus' speaker dataframe marks unknown speaker roles as empty values, following the most recent documentation, this script marks them as U.

- `role`: Per the most recent documentation of Convokit, the 'role' of the speaker is no longer provided.

### Testing

The script `testing/usable_with_convokit.ipynb` shows that our scripts, once downloaded, successfully create data (locally) that can be integrated with convokit.

The following tests were performed in `testing/compare.ipynb` to ensure the integrity of the corpus

- We compared our scraped 2019 corpus (as extracted by the script in this repository) and the pre-existing 2019 corpus from the Convokit dataset.

- We manually inspect the 2020 corpus extracted by the script in this repository.

### Additional notes

- `justice_info.csv` contains information about each justice's full name, their corresponding Oyez id(see Convokit documentation), and [scdb justice id](http://scdb.wustl.edu/documentation.php?var=justice#norms). **_This file has been manually created by searching information on Wikipedia. When new justices are appointed to the Supreme Court, the file has to be updated with the new justice's information._** The filepath to this file can be edited in the script.py file.

- As mentioned above, information on Oyez, including conversation ids, is constantly updated. To obtain accurate information, we recommend re-running the script every few months or years so that the most recent updates to Oyez are reflected in the data.

- The script does not parse the data (e.g., depenendency parsing), as some previous Convokit corpora do.
