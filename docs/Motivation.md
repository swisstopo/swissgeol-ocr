# Motivation

This repository acts as a _wrapper_ around the OCR service [AWS Textract](https://aws.amazon.com/de/textract/).

There exist tools such as [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) that immediately produce a new, _searchable_ PDF file based on the text that was detected by an OCR model. However, the response of an AWS Textract API call is not a new file, but essentially only a list of all the words that were detected in a PDF document, together with the exact page number and bounding box for each word. This repository fills that gap, producing a _searchable_ PDF file by enriching the original input document with hidden text that was returned the AWS Textract API.

In some situations, the fact that AWS Textract cannot generate a new PDF file might be a downside. However, for other use cases, there can also be advantages in having more control over how exactly the detected text is inserted in the new PDF file (confidence thresholds, positioning, reading order, etc.), as well as over other pre-processing or post-processing steps that could be useful.

This repository provides a reference implementation for an end-to-end (raw scanned PDF file to searchable PDF file) OCR pipeline based on AWS Textract. While the implemented pre- and post-processing steps are optimized for dealing with  geological documents from the archives of the Swiss [Federal Office of Topography swisstopo](
https://www.swisstopo.admin.ch/), the pipeline is also likely to work well for many other types of scanned documents. 


## Pre-processing

Before running OCR on a PDF file, several pre-processing steps are applied, with the following goals:
- Fixing certain issues that commonly occur in our PDF files (especially those that were scanned from paper documents or microfiches), such as:
  - incorrectly defined page dimensions,
  - images with an excessively high resolution or with insufficient compression, causing unnecessarily large file sizes.
- Optimizing each page for better OCR results from AWS Textract, taking into account the strengths and limitations of that OCR service.

In particular, the following pre-processing steps are applied:
- If necessary, PDF pages rescaled, and images are cropped and/or converted from JPX to JPG.
- PDF pages that are already "digitally born" are detected, and can be skipped when applying OCR.
- When a scanned PDF page already contains digital text from an older OCR run, this text can be removed, and the OCR will be re-applied.
- Pages with large dimensions are cut into smaller sections, that are sent separately to the AWS Textract service in multiple requests. Indeed, AWS Textract has certain [limits on file size and page dimensions](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html), and even within those limits, the quality of the results tends to be better when the input dimensions are smaller.

## OCR

For OCR (optical character recognition), this pipeline relies on the [AWS Textract](https://aws.amazon.com/en/textract/) cloud service.

The main reasons for choosing the OCR model from AWS for processing the documents on the [swissgeol.ch](https://swissgeol.ch) application are:
- The [swissgeol.ch](https://swissgeol.ch) applications and PDF files were already hosted on AWS. Swisstopo already has data protection and security concepts in place for processing geological documents on AWS.
- On our documents, AWS Textract produced OCR results of significantly higher quality compared to open source alternatives such as [Tesseract](https://github.com/tesseract-ocr/tesseract)/[OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF).
- Reasonable throughput and low [pricing](https://aws.amazon.com/en/textract/pricing/) (0.0015 USD per page as of January 2026).

In principle, it should be possible to substitute AWS Textract with another OCR model (either cloud-based or local). However, this is currently not configurable, as the use of AWS Textract is hard-coded into this pipeline. Moreover, other OCR models will have different strengths, weaknesses and limitations. Consequently, significant changes to the pre- and post‐processing steps will most likely be required to achieve optimal results when using a different OCR model.

## Post-processing

After applying pre-processing and OCR, the post-processing step produces a new PDF file where all the detected text is digitally legible.

When AWS Textract applies OCR to a scanned document in a PDF file, the result is not a new PDF file, but rather just a list of all words that were detected on any page, together with the exact page number and bounding box for each word.

These detected words need to be inserted into the PDF file in an invisible way (the words are already visible in the scanned image), but so that user can still search for text in the file, as well as select and/or copy-paste certain text fragments. This is achieved by using the so-called _PDF rendering mode 3_.


