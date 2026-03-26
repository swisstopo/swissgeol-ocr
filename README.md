# swissgeol.ch OCR pipeline

An end-to-end OCR pipeline (from raw scanned PDF file to searchable PDF file) based on the [AWS Textract](https://aws.amazon.com/de/textract/) cloud service.

This pipeline was developed by the Swiss [Federal Office of Topography swisstopo](https://www.swisstopo.admin.ch/). At swisstopo, it is used to digitize geological documents for internal use as well as for publication on the [swissgeol.ch](https://www.swissgeol.ch/) platform. In particular, the OCR pipeline has been integrated into the web applications [assets.swissgeol.ch](https://assets.swissgeol.ch/) ([GitHub Repo](https://github.com/swisstopo/swissgeol-assets-suite)) and [boreholes.swissgeol.ch](https://boreholes.swissgeol.ch/) ([GitHub Repo](https://github.com/swisstopo/swissgeol-boreholes-suite)).

The pipeline can be run as a Python script (processing either local files or objects in an S3 bucket) or deployed as an API (processing objects in an S3 bucket).

The overall functionality of the pipeline is similar to that of the [OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/) software, but with AWS Textract as the underlying OCR model instead of [Tesseract](https://tesseract-ocr.github.io/). If you have strict requirements regarding data protection, data sovereignty or model transparency, then an open-source OCR model such as Tesseract might be preferable. On the other hand, a commercial API such as AWS Textract offers advantages such as scalability and high OCR quality at a relatively low price per page. Swisstopo's motivation for using AWS Textract and developing an OCR pipeline in this way is documented in more details on the page [docs/**Motivation.md**](docs/Motivation.md).

Features:
- Creates a new PDF file in which the text detected by the AWS Textract OCR model can be selected and searched for text in any PDF viewer.
- "Digitally born" PDF pages are detected and skipped when applying OCR.
- PDF files that were previously processed by a different OCR pipeline have their existing hidden text removed, and OCR is reapplied to ensure consistent OCR quality.
- Useful preprocessing steps are applied, such as scaling of PDF pages with incorrect dimensions, cropping of images, and converting JPX images to JPG.
- Pages with large dimensions are cut into smaller sections, to respect AWS Textract's [limits on file size and page dimensions](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html) without compromising on quality.
- After processing, metadata is added to an S3 object:
  - `X-Amz-Meta-Pagecount`: The number of pages in the document.

## Usage

### 1. Installation

Python 3.12 is required.

Example using a virtual environment and `pip install`:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt 
```

### 2. Configuration

Input source, output destination and other settings need to be **configured via environment variables**. There are different required environment variables depending on whether the pipeline needs to run as a script or as an API service. Detailed documentation is available under [docs/Configuration.md](docs/Configuration.md).

### 3a. Running as a script

When running as a Python script, PDF files can be processed from a local directory or from an S3 bucket. Likewise, the output PDF files can be written to either a local directory or an S3 bucket.

After configuring the required environment variables, the script can be executed like any normal Python script file:
```bash
python main.py
```

To run the script while additionally appending all output to a log file, you can use the following command:

```bash
python -u main.py | tee output.log 
```

### 3b. Running as an API

When deployed as an API, only reading from and writing to S3 is supported.

The API is built on [FastAPI](https://fastapi.tiangolo.com/). After configuring the required environment variables, the API can be started using the following command:
```bash
fastapi run api.py
```

Unless configured otherwise, this will start the API at http://0.0.0.0:8000 and detailed documentation (as well as en interface to test the different entpoints) will be accessible at http://0.0.0.0:8000/docs.

#### Endpoint `POST /`

> Starts OCR on a given PDF file.
> 
> Example JSON payload:
> ```json
> {
>   "file": "example.pdf"
> }
> ```
> 
> Responds with HTTP status code 204 (_No Content_) if the OCR process was successfully started.

#### Endpoint `POST /collect`

> Polls whether the OCR processing of a given PDF file has finished.
> 
> Example JSON payload:
> ```json
> {
>   "file": "example.pdf"
> }
> ```
> 
> Responds with HTTP status code 200 and a JSON response body, where the field `has_finished` indicates if the corresponding OCR process has finished or not yet.
> 
> Example JSON response:
> 
> ```json
> {
>   "has_finished": true,
>   "data": null
> }
> ```
> 
> Responds with HTTP status code 422 (_Error: Unprocessable Entity_) if no OCR process was ever started for this file.

## Governance

This repository is managed by the Swiss Federal Office of Topography [swisstopo](https://www.swisstopo.admin.ch/). The project lead and primary maintainer is Stijn Vermeeren [@stijnvermeeren-swisstopo](https://www.github.com/stijnvermeeren-swisstopo). Support has come from external contractors at [Visium](https://www.visium.ch/) and [EBP](https://www.ebp.global/). Individual contributors are listed on [GitHub's _Contributors_ page](https://github.com/swisstopo/swissgeol-ocr/graphs/contributors).

We welcome suggestions, bug reports and code contributions from third parties, because external feedback is also likely to improve the project for our internal use. However, the priority of any external request will have to be evaluated based on their compatibility with our legal mandate as a government agency.

### Licence

This project is released as open-source software, under the principle of "_public money, public code_", in accordance with the 2023 federal law "[_EMBAG_](https://www.fedlex.admin.ch/eli/fga/2023/787/de)", and following the guidance of the [tools for OSS published by the Federal Chancellery](https://www.bk.admin.ch/bk/en/home/digitale-transformation-ikt-lenkung/bundesarchitektur/open_source_software/hilfsmittel_oss.html).

The source code is licensed under the [AGPL License](LICENSE). This is due to the licensing of certain dependencies, most notably [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright), which is only avialable under either the AGPL license or a commercial license. If we can remove this dependency in the future, then we will switch to a more permissive license for this project.
