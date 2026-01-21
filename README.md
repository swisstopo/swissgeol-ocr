# swissgeol.ch OCR pipeline

An end-to-end OCR pipeline (from raw scanned PDF file to searchable PDF file) based on the [AWS Textract](https://aws.amazon.com/de/textract/) cloud service.

This pipeline was developed by the Swiss [Federal Office of Topography swisstopo](https://www.swisstopo.admin.ch/). At swisstopo, it is used for digitising geological documents for internal use as well as for publication on the [swissgeol.ch](https://www.swissgeol.ch/) platform. In particular, the OCR pipeline has been integrated in the web applications [assets.swissgeol.ch](https://assets.swissgeol.ch/) ([GitHub Repo](https://github.com/swisstopo/swissgeol-assets-suite)) and [boreholes.swissgeol.ch](https://boreholes.swissgeol.ch/) ([GitHub Repo](https://github.com/swisstopo/swissgeol-boreholes-suite)).

The pipeline can be run as a Python script (processing either local files or objects in an S3 bucket) or deployed as an API (processing objects in an S3 bucket).

The overall pipeline functionality is similar to the [OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/) software, but with AWS Textract as the underlying OCR model instead of [Tesseract](https://tesseract-ocr.github.io/). If you have strong requirements regarding data protection, data soveriegnty or model transparency, then an open source OCR model such as Tesseract might be preferrable. On the other hand, a commercial API such as AWS Textract brings advantages such as scalability and high OCR quality at a relatively small price per page. Swisstopo's motivation for using AWS Textract and developing an OCR pipeline in this way is documented in more details on the page [docs/**Motivation.md**](docs/Motivation.md).

Features:
- Creates a new PDF file where the text detected by the AWS Textract OCR model can be selected and searched for text in any PDF viewer.
- PDF pages that are "digitally born" are detected and skipped when applying OCR.
- For PDF files that were previously processed by a different OCR pipeline, existing hidden text is removed, and OCR is re-applied, ensuring consistent OCR quality.
- Applies useful preprocessing steps such as scaling of PDF pages with incorrect dimensions, cropping of images, conversion of JPX images to JPG.
- Pages with large dimensions are cut into smaller sections, to respect the AWS Textract [limits on file size and page dimensions](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html) without compromising on quality.
- Adds metadata to an S3 object after processing, currently containing:
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

After configuring the required environment variables, the script can be executed like any normal Python script file:
```bash
python main.py
```

To run the script while additionally appending all output to a log file, you can use the following command:

```bash
python -u main.py | tee output.log 
```

### 3b. Running as an API

The API is built on [FastAPI](https://fastapi.tiangolo.com/). After configuring the required environment variables, the API can be started using the following command:
```bash
fastapi run api.py
```

Unless configured otherwise, this will start the API at http://0.0.0.0:8000 and detailed documentation (as well as en interface to test the different entpoints) will be accessible at http://0.0.0.0:8000/docs.

#### Endpoint `POST /`

Starts OCR on a given PDF file.

Example JSON payload:
```json
{
  "file": "example.pdf"
}
```

#### Endpoint `POST /collect`

Polls whether the OCR processing of a given PDF file has finished:

Example JSON payload:
```json
{
  "file": "example.pdf"
}
```


## Governance

This repository is managed by the Swiss Federal Office of Topography [swisstopo](https://www.swisstopo.admin.ch/). Project lead and primary maintainer is Stijn Vermeeren [@stijnvermeeren-swisstopo](https://www.github.com/stijnvermeeren-swisstopo). Support has come from external contractors at [Visium](https://www.visium.ch/) and [EBP](https://www.ebp.global/).

We welcome suggestions, bug reports and code contributions from third parties, as external feedback is also likely to make the project better for our internal use. However, the priority of any external request will have to be evaluated against their compatibility with our legal mandate as government agency.

### Licence

This project is released as open source software, under the principle of "_public money, public code_", in accordance with the 2023 federal law "[_EMBAG_](https://www.fedlex.admin.ch/eli/fga/2023/787/de)", and following the guidance of the [tools for OSS published by the Federal Chancellery](https://www.bk.admin.ch/bk/en/home/digitale-transformation-ikt-lenkung/bundesarchitektur/open_source_software/hilfsmittel_oss.html).

The source code is licensed under the [AGPL License](LICENSE). This is due to the licensing of certain dependencies, most notably [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright), which is only avialable under either the AGPL license or a commercial license. If in future we can remove this dependency, then we will switch to a more permissive license for this project.
