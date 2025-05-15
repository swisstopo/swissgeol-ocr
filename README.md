# swissgeol.ch OCR service

Source code for the OCR scripts that are used at the Swiss [Federal Office of Topography swisstopo](
https://www.swisstopo.admin.ch/) for digitising geological documents for internal use as well as for publication on the 
[swissgeol.ch](https://www.swissgeol.ch/) platform, in particular to the  applications [assets.swissgeol.ch](
https://assets.swissgeol.ch/) ([GitHub Repo](https://github.com/swisstopo/swissgeol-assets-suite)) and [
boreholes.swissgeol.ch](https://boreholes.swissgeol.ch/) ([GitHub Repo](
https://github.com/swisstopo/swissgeol-boreholes-suite)). 

OCR processing is supported both in script form and as REST API.
To process PDF files, the [AWS Textract](https://aws.amazon.com/de/textract/) service is called for each page.
The detected text is then put into the PDF document by using the PyMuPDF and Reportlab libraries.
This enables selecting and searching for text in any PDF viewer.

The resulting functionality is similar to the [OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/) software,
but with AWS Textract as the underlying OCR model instead of [Tesseract](https://tesseract-ocr.github.io/).
Tesseract is open-source while AWS Textract is a commercial API.
However, AWS Textract is more scalable and gives better quality results on our inputs,
which is more important for our use cases.

Additional features:

- If necessary, PDF pages rescaled, and images are cropped and/or converted from JPX to JPG.
- PDF pages that are already "digitally born" are detected, and can be skipped when applying OCR.
- When a scanned PDF page already contains digital text from an older OCR run, this text can be removed, and the OCR can
  be re-applied.
- Pages with large dimensions are cut into smaller sections, that are sent separately to the AWS Textract service in
  multiple requests. Indeed, AWS Textract has
  certain [limits on file size and page dimensions](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html),
  and even within those limits, the quality of the results is better when the input dimensions are smaller.
- Adds metadata to the object after processing, currently containing:
  - `X-Amz-Meta-Pagecount`: The number of pages in the document if available, else the key is not set

## Installation

Python 3.12 is required.

Example using a virtual environment and `pip install`:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt 
```

## Usage
The script can be executed like any normal Python script file:
```bash
python main.py
```

To run the script while additionally appending all output to a log file, you can use the following command:

```bash
python -u main.py | tee output.log 
```

The API is built on [FastAPI](https://fastapi.tiangolo.com/) and can be run by its CLI:
```bash
fastapi run api.py
```

## Configuration

Environment variables are read from the file `.env`.

If an environment variable `OCR_PROFILE` is specified, then environment variables are additionally read
from `.env.{OCR_PROFILE}`, with the values from this file potentially overriding the values from `.env`.

For example, run the script as `OCR_PROFILE=assets python -m main` to use the environment variables from `.env.assets`.

> The API and Script require different configurations.
> Please ensure that you are using the correct environment variables depending on what you want to execute.

When setting the environment variable `INPUT_DEBUG_PAGE` to a particular page number, the pipeline will only process 
that page, and additional create a version of the page with only the OCR layer (with visible text).

### Script Configuration

AWS credentials can be provided using
a [credentials file](https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-files.html) (`~/.aws/credentials`). The
environment variable `AWS_TEXTRACT_PROFILE` in the configuration examples below refers to a profile in that file.

#### `.env.assets`

- Reads and writes asset files directly from/to S3.
- Applies OCR more defensively, only to pages without pre-existing visible digital text.
- Uses a higher confidence threshold (0.7), because for publication on assets.swissgeol.ch, we'd rather not put any OCR'
  d text in the document at all, rather than putting nonsense in the document.

```sh
AWS_TEXTRACT_PROFILE=default

INPUT_TYPE=S3
INPUT_AWS_PROFILE=s3-assets
INPUT_S3_BUCKET=swissgeol-assets-swisstopo
INPUT_S3_PREFIX=asset/asset_files/
INPUT_SKIP_EXISTING=TRUE

OUTPUT_TYPE=S3
OUTPUT_AWS_PROFILE=s3-assets
OUTPUT_S3_BUCKET=swissgeol-assets-swisstopo
OUTPUT_S3_PREFIX=asset/asset_files_new_ocr/

CONFIDENCE_THRESHOLD=0.7
CLEANUP_TMP_FILES=TRUE
```

#### `env.boreholes`

- Read and writes files from/to a local directory.
- Applies OCR more aggressively, also e.g. to images inside digitally-born PDF documents, as long as the newly detected
  text does not overlap with any pre-existing digital text.
- Uses a lower confidence threshold (0.45), as especially for extracting stratigraphy data, it is better to know all
  places where some text is located in the document, even when we are not so sure how to actually read the text.

```sh
AWS_TEXTRACT_PROFILE=default

INPUT_TYPE=path
INPUT_PATH=/home/stijn/bohrprofile-zurich/

OUTPUT_TYPE=path
OUTPUT_PATH=/home/stijn/bohrprofile-zurich/ocr/

CONFIDENCE_THRESHOLD=0.45
USE_AGGRESSIVE_STRATEGY=TRUE
```

### API Configuration

```sh
# The directory at which temporary files are to be stored.
TMP_PATH=tmp/

# The local AWS profile that will be used to access Textract.
#
# If left empty, the credentials will be read from the environment.
# This allows the use of service accounts when deploying to K8s.
AWS_PROFILE=swisstopo-ngm

# Alternatives to `AWS_PROFILE` to allow you to specify the access keys directly.
# AWS_ACCESS_KEY=
# AWS_SECRET_ACCESS_KEY=

# During local development, an S3-compatible service like MinIO (https://min.io/) can be used.
# In this case, the endpoint will look like `http://minio:9000`.
# Note that if MinIO is used, you still need to configure AWS_DEFAULT_REGION if none is set in your AWS credentials.
S3_INPUT_ENDPOINT=https://s3.eu-central-1.amazonaws.com
S3_INPUT_BUCKET=swissgeol-assets-swisstopo
S3_INPUT_FOLDER=asset_files/

S3_OUTPUT_ENDPOINT=https://s3.eu-central-1.amazonaws.com
S3_OUTPUT_BUCKET=swissgeol-assets-swisstopo
S3_OUTPUT_FOLDER=new_ocr_output/

CONFIDENCE_THRESHOLD=0.7
```

