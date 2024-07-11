
The script `main.py` processes PDF files, calls the [AWS Textract](https://aws.amazon.com/de/textract/) service for each page to apply OCR, and uses the PyMuPDF and Reportlab libraries to put the detected text into the PDF document (enabling selecting and searching for text). 

If necessary, PDF pages also rescaled, and images are cropped and/or converted from JPX to JPG.

## Installation

Example using a virtual environment and `pip install`:
```
python -m venv env
source env/bin/activate
pip install -r requirements.txt 
```

## Configuration examples

Environment variables are read from the file `.env`.

If an environment variable `OCR_PROFILE` is specified, then environment variables are additionally read from `.env.{OCR_PROFILE}`, with the values from this file potentially overriding the values from `.env`. 

For example, run the script as `OCR_PROFILE=assets python -m main` to use the environment variables from `.env.assets`.

### `.env.assets`

- Reads and writes asset files directly from/to S3.
- Applies OCR more defensively, only to pages without pre-existing visible digital text.
- Uses a higher confidence threshold (0.7), because for publication on assets.swissgeol.ch, we'd rather not put any OCR'd text in the document at all, rather than putting nonsense in the document.

```
AWS_TEXTRACT_PROFILE=default

OCR_INPUT_TYPE=S3
OCR_INPUT_AWS_PROFILE=s3-assets
OCR_INPUT_S3_BUCKET=swissgeol-assets-swisstopo
OCR_INPUT_S3_PREFIX=asset/asset_files/
OCR_INPUT_CLEANUP_TMP_FILES=TRUE
OCR_INPUT_IGNORE_EXISTING=TRUE

OCR_OUTPUT_TYPE=S3
OCR_OUTPUT_AWS_PROFILE=s3-assets
OCR_OUTPUT_S3_BUCKET=swissgeol-assets-swisstopo
OCR_OUTPUT_S3_PREFIX=asset/asset_files_new_ocr/
OCR_OUTPUT_CLEANUP_TMP_FILES=TRUE

CONFIDENCE_THRESHOLD=0.7
```

### `env.boreholes`

- Read and writes files from/to a local directory.
- Applies OCR more aggressively, also e.g. to images inside digitally-born PDF documents, as long as the newly detected text does not overlap with any pre-existing digital text.
- Uses a lower confidence threshold (0.45), as especially for extracting stratigraphy data, it is better to know all places where some text is located in the document, even when we are not so sure how to actually read the text.

```
AWS_TEXTRACT_PROFILE=default

OCR_INPUT_TYPE=path
OCR_INPUT_PATH=/home/stijn/bohrprofile-zurich/

OCR_OUTPUT_TYPE=path
OCR_OUTPUT_PATH=/home/stijn/bohrprofile-zurich/ocr/

CONFIDENCE_THRESHOLD=0.45
OCR_STRATEGY_AGGRESSIVE=TRUE
```
