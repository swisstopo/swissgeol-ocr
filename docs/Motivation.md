# Motivation

This repository acts as a _wrapper_ around the OCR service [AWS Textract](https://aws.amazon.com/de/textract/).

There exist tools such as [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) that immediately produce a new, _searchable_ PDF file based on the text that was detected by an OCR model. However, an AWS Textract API call does not procude a new file, but essentially only a list of all the words that were detected in a PDF document, together with the exact page number and bounding box for each word. This repository brdiges that gap, producing a _searchable_ PDF file by enriching the original input document with hidden text that was returned by the AWS Textract API.

In some situations, the fact that AWS Textract cannot generate a new PDF file might be a disadvantage. However, for other use cases, having more control over how exactly the detected text is inserted in the new PDF file can be advantageous. This includes control over confidence thresholds, positioning, reading order, and other pre-processing or post-processing steps that could be useful.

This repository provides a reference implementation of an end-to-end OCR pipeline (from raw scanned PDF file to searchable PDF file) based on AWS Textract. While the implemented pre- and post-processing steps are optimized for dealing with geological documents from the archives of the Swiss [Federal Office of Topography swisstopo](https://www.swisstopo.admin.ch/), the pipeline is also likely to work well for many other types of scanned documents.


## Pre-processing

Before running OCR on a PDF file, several pre-processing steps are applied, with the following goals:
- Fixing common issues in our PDF files (especially those that were scanned from paper documents or microfiches), such as:
  - incorrectly defined page dimensions,
  - images with an excessively high resolution or with insufficient compression, causing unnecessarily large file sizes.
- Optimizing each page for better OCR results from AWS Textract, taking into account the strengths and limitations of that OCR service.

In particular, the following pre-processing steps are applied:
- If necessary, PDF pages are rescaled, and images are cropped and/or converted from JPX to JPG.
- "Digitally born" PDF pages are detected and skipped when applying OCR.
- If a scanned PDF page already contains digital text from an older OCR run, this text can be removed, and the OCR will be re-applied.
- Pages with large dimensions are cut into smaller sections, that are sent separately to the AWS Textract service in multiple requests. Indeed, AWS Textract has certain [limits on file size and page dimensions](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html), and even within those limits, the quality of the results tends to be better when the input dimensions are smaller.

## OCR (AWS Textract model)

This pipeline relies on the [AWS Textract](https://aws.amazon.com/en/textract/) cloud service for OCR (optical character recognition).

The main reasons for selecting the OCR model from AWS to process documents in the [swissgeol.ch](https://swissgeol.ch) application are:
- The [swissgeol.ch](https://swissgeol.ch) applications and PDF files were already hosted on AWS. Swisstopo already has data protection and security concepts in place for processing geological documents on AWS.
- On our documents, AWS Textract produced OCR results of significantly higher quality compared to open source alternatives such as [Tesseract](https://github.com/tesseract-ocr/tesseract)/[OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF).
- Reasonable throughput and low [pricing](https://aws.amazon.com/en/textract/pricing/) (0.0015 USD per page as of January 2026).
- We automatically benefit from improvements in the AWS OCR model. Although AWS unfortunately does not publish any detailed release notes or changelog for Textract, we did notice significant quality improvements when they [announced the deployment of a new OCR model in 2025](https://aws.amazon.com/about-aws/whats-new/2025/06/amazon-textract-detectdocumenttext-analyzedocument-apis/).

In principle, it should be possible to substitute AWS Textract with another OCR model (either cloud-based or local). However, this is currently not configurable, as the use of AWS Textract is hard-coded into this pipeline. Moreover, other OCR models will have different strengths, weaknesses and limitations. Consequently, significant changes to the pre- and post‐processing steps will most likely be required to achieve optimal results with a different OCR model.

## Post-processing

After applying pre-processing and OCR, the post-processing step produces a new PDF file in which all the detected text is digitally legible.

When AWS Textract applies OCR to a scanned document in a PDF file, the result is not a new PDF file, but rather just a list of all the detected words on any page, along with the exact page number and bounding box for each word.

The detected words must be inserted into the PDF file in an invisible way (the words are already visible in the scanned image), while still allowing users to search for text and to select and/or copy-paste certain text fragments. This is achieved by using the so-called _PDF rendering mode 3_.

The order in which the detected words and lines are inserted into the new PDF file affects how text can be selected in many PDF viewers. Since this is an important and complex topic, it is explained in more detail on a dedicated page: [**ReadingOrder.md**](ReadingOrder.md).
