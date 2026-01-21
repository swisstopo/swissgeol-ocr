
# Configuration

The configuration of the OCR pipeline, including where the input documents are read from and where the output files are written to, is controlled by environment variables.

## `.env` file

Environment variables are read from the file `.env`, if such a file exists.

If an environment variable `OCR_PROFILE` is specified, then environment variables are additionally read
from `.env.{OCR_PROFILE}`, with the values from this file potentially overriding the values from `.env`.

For example, run the script as `OCR_PROFILE=assets python -m main` to use the environment variables from `.env.assets`.

## AWS credentials

AWS credentials can be provided using a [credentials file](https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-files.html) (`~/.aws/credentials`). The environment variables `AWS_TEXTRACT_PROFILE`, `INPUT_AWS_PROFILE` and `OUTPUT_AWS_PROFILE` refer to profiles in that file.

## Variables

### Running as Python script

#### General

- `TEXTRACT_AWS_PROFILE` (**required**)
  - The name of the AWS credentials profile that will be used for calling the Textract service.
- `TMP_PATH` (**required**)
  - Absolute or relative path to a directory where temporary files will be written to.
- `CONFIDENCE_THRESHOLD` (**required**)
  - Number between 0 and 1 that controls the minimal confidence the OCR model needs to have, before text is included in the new, searchable PDF. A value of 0.7 is usually a good starting point.
- `USE_AGGRESSIVE_STRATEGY` (defaults to `FALSE`)
  - Set to `TRUE` to also apply OCR to images on digitally-born PDF pages. The default behaviour completely skips OCR on pages that are identified as digitally-born.

#### Input

- `INPUT_TYPE` (**required**)
  - Must be either `path` (for reading from a local file or directory) or `s3` (for reading from an S3 bucket).
- `INPUT_AWS_PROFILE`, `INPUT_S3_PREFIX`, `INPUT_S3_PREFIX` (**required if** `INPUT_TYPE` equals `s3`)
  - All objects in the specified S3 bucket whose key starts with the given prefix will be processed. The given AWS credentials profile will be used to access the S3 bucket.
- `INPUT_PATH` (**required if** `INPUT_TYPE` equals `path`)
  - If the path points to a single file, then this file will be processed. If the path points to a directory, then all PDF file is this directory (but not in any subdirectories) will be processed.
- `INPUT_DEBUG_PAGE`
  - When set to a particular page number, the pipeline will only process that page, and additional create a version of the page with only the OCR layer (with visible text).
- `INPUT_SKIP_EXISTING` (**required**)
  - Set to `TRUE` to skip processing files that aready exist in the output destination. Set to `FALSE` to process all files from the input source and potentially override existing files in the output destination.

#### Output

- `OUTPUT_TYPE` (**required**)
  - Must be either `path` (for writing to a local file or directory) or `s3` (for writing to an S3 bucket).
- `OUTPUT_AWS_PROFILE`, `OUTPUT_S3_PREFIX`, `OUTPUT_S3_PREFIX` (**required if** `OUTPUT_TYPE` equals `s3`)
  - Output files will be written to the specific S3 bucket, and the specified prefix will be prepended to the filename of the input file to create the new object key. The given AWS credentials profile will be used to access the S3 bucket.
- `OUTPUT_PATH` (**required if** `OUTPUT_TYPE` equals `path`)
  - Path of a directory where all the output files will be written to. The filename of each output file will be identical to the filename of the corresponding input file.

### Running as an API

#### General

- `TMP_PATH` (**required**
- `TEXTRACT_AWS_PROFILE` (**required**)
  - The name of the AWS credentials profile that will be used for calling the Textract service.)
  - Absolute or relative path to a directory where temporary files will be written to.
- `CONFIDENCE_THRESHOLD` (**required**)
  - Number between 0 and 1 that controls the minimal confidence the OCR model needs to have, before text is included in the new, searchable PDF. A value of 0.7 is usually a good starting point.
- `TEXTRACT_AWS_PROFILE`
  - The name of an AWS credentials profile that will be used for calling the Textract service.
- `AWS_PROFILE`
  - The name of an AWS credentials profile that will be used for accessing the S3 buckets.
- `SKIP_PROCESSING` (defaults to `FALSE`)
  - Set to `TRUE` to run the API in test mode, returning successful API responses without actually calling the OCR model.

#### Input

- `S3_INPUT_ENDPOINT` (**required**)
  - An S3 endpoint URL such as `https://s3.eu-central-1.amazonaws.com`.  
  - During local development, an S3-compatible service like MinIO (https://min.io/) can be used. In this case, the endpoint will look like `http://minio:9000`. 
  - Note that if MinIO is used, you still need to configure `AWS_DEFAULT_REGION` if none is set in your AWS credentials.
- `S3_INPUT_BUCKET` (**required**)
  - S3 Bucket where the input files will be read from.
- `S3_INPUT_FOLDER` (**required**)
  - Prefix that will be prepended to the requested filename to obtain the object key for the file that will be processed.

#### Output

- `S3_INPUT_ENDPOINT` (**required**)
  - An S3 endpoint URL such as `https://s3.eu-central-1.amazonaws.com`.  
  - During local development, an S3-compatible service like MinIO (https://min.io/) can be used. In this case, the endpoint will look like `http://minio:9000`. 
  - Note that if MinIO is used, you still need to configure `AWS_DEFAULT_REGION` if none is set in your AWS credentials.
- `S3_INPUT_BUCKET` (**required**)
  - S3 Bucket where the output files will be written to.
- `S3_OUTPUT_FOLDER` (**required**)
  - Prefix that will be prepended to the filename of the processed PDF to obtain the object key for the output file.

## Example configurations

### Processing geological assets on S3

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

### Processing boreholes profiles in a local directory

- Read and writes files from/to a local directory.
- Applies OCR more aggressively, also e.g. to images inside digitally-born PDF documents, as long as the newly detected
  text does not overlap with any pre-existing digital text.
- Uses a lower confidence threshold (0.45), as especially for extracting stratigraphy data, it is better to know all
  places where some text is located in the document, even when we are not so sure how to actually read the text.

```sh
AWS_TEXTRACT_PROFILE=default

INPUT_TYPE=path
INPUT_PATH=~/bohrprofile/

OUTPUT_TYPE=path
OUTPUT_PATH=~/bohrprofile/ocr/

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

