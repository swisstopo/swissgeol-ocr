# Swissgeol.ch OCR service

Source code for the OCR scripts that are used at Swiss [
Federal Office of Topography swisstopo](https://www.swisstopo.admin.ch/) for digitising geological documents for internal use as well as for publication on the [swissgeol.ch](https://www.swissgeol.ch/) platform.

The script `main.py` processes PDF files, calls the [AWS Textract](https://aws.amazon.com/de/textract/) service for each page to apply OCR, and uses the PyMuPDF and Reportlab libraries to put the detected text into the PDF document (enabling selecting and searching for text in any PDF viewer).

The resulting functionality is similar to the [OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/) software, but with AWS Textract as the underlying OCR model instead of [Tesseract](https://tesseract-ocr.github.io/). Tesseract is open-source while AWS Textract is a commercial API. However, AWS Textract is more scalable and gives better quality results on our inputs, which is more important for our use cases.

Additional features:
- If necessary, PDF pages rescaled, and images are cropped and/or converted from JPX to JPG.
- PDF pages that are already "digitally born" are detected, and can be skipped when applying OCR.
- When a scanned PDF page already contains digital text from an older OCR run, this text can be removed, and the OCR can be re-applied.
- Pages with large dimensions are cut into smaller sections, that are sent separately to the AWS Textract service in multiple requests. Indeed, AWS Textract has certain [limits on file size and page dimensions](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html), and even within those limits, the quality of the results is better when the input dimensions are smaller.

### Roadmap

- Allow deploying this OCR script as a microservice (adding an API, logging and monitoring, configurability. etc.), that can be integrated into the applications [assets.swissgeol.ch](https://assets.swissgeol.ch/) ([Github Repo](https://github.com/swisstopo/swissgeol-assets-suite)) and [boreholes.swissgeol.ch](https://boreholes.swissgeol.ch/) ([Github Repo](https://github.com/swisstopo/swissgeol-boreholes-suite)).

## Installation

Example using a virtual environment and `pip install`:
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt 
```

## Configuration examples

Environment variables are read from the file `.env`.

If an environment variable `OCR_PROFILE` is specified, then environment variables are additionally read from `.env.{OCR_PROFILE}`, with the values from this file potentially overriding the values from `.env`. 

For example, run the script as `OCR_PROFILE=assets python -m main` to use the environment variables from `.env.assets`.

### AWS credentials

AWS credentials can be provided using a [credentials file](https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-files.html) (`~/.aws/credentials`). The environment variable `AWS_TEXTRACT_PROFILE` in the configuration examples below refers to a profile in that file.

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
