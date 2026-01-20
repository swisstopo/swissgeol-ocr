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
