import io

import pymupdf
from pymupdf.mupdf import FzErrorFormat
from PIL import Image
import logging


def rotation_from_transform_matrix(transform: pymupdf.Matrix) -> int | None:
    epsilon = 1e-4
    if abs(transform.b) < epsilon and abs(transform.c) < epsilon:
        if abs(transform.a) > epsilon and abs(transform.d) > epsilon:
            if transform.a > 0 and transform.d > 0:
                return 0
            if transform.a < 0 and transform.d < 0:
                return 180
    if abs(transform.a) < epsilon and abs(transform.d) < epsilon:
        if abs(transform.b) > epsilon and abs(transform.c) > epsilon:
            if transform.b > 0 > transform.c:
                return 90
            if transform.b < 0 < transform.c:
                return 270


def crop_images(out_doc: pymupdf.Document, page_index: int):
    page = out_doc[page_index]

    if page.rotation != 0:
        # We had some issues with misplacement of the cropped image on pages with a non-trivial rotation, so to be on
        # the safe side, we enforce rotation=0. The preceding resize step should normally have reset the page rotation
        # already.
        logging.info("  Skipping page because rotation is not 0 but {}.".format(page.rotation))
        return

    images = [
        dict
        for dict in page.get_image_info(xrefs=True)
        # Ignore the 1x1 dummy image that is added by the PyMuPDF Page.delete_image method; see LGD-579
        if dict["width"] > 1 or dict["height"] > 1
    ]

    if len(images) > 1:
        # Skip because we cannot reliably deal with overlapping images (e.g. their order might change if we crop and
        # replace one image but not the other, e.g. CHA0ECFE2F3FFE47728C76619E_01_profil.pdf).
        logging.info("  More than one image on the page, skipping image crop.")
        return

    for dict in images:
        xref = dict["xref"]
        try:
            img_size = pymupdf.Matrix(dict["width"], dict["height"])
            extracted_img = out_doc.extract_image(xref)
            image_bbox = pymupdf.Rect(*dict["bbox"])

            extension = extracted_img['ext']
            if extension == 'jb2':
                # Example PDF file with a JBIG2 image: A204.pdf
                logging.info("  Skipping JBIG2 image.")
                continue

            # allow images that are only slightly larger than the page, as cropping the image is not likely to reduce
            # the file size (it might even increase it) and might decrease the image quality.
            margin = 10  # in points
            page_rect_with_margin = pymupdf.Rect(
                page.rect.x0 - margin,
                page.rect.y0 - margin,
                page.rect.x1 + margin,
                page.rect.y1 + margin
            )

            if not page_rect_with_margin.contains(image_bbox):
                logging.info("  Cropping {} image (bbox {}, page.rect {}).".format(extension, image_bbox, page.rect))
                transform = pymupdf.Matrix(dict["transform"])

                if not page.rect.intersects(image_bbox):
                    logging.info("  Image does not intersect the visible part of the page. Skipping image.")
                    continue

                rotation = rotation_from_transform_matrix(transform)
                if rotation is None:
                    logging.info("  Image rotation could not be computed from transform matrix. Skipping image.")
                    continue

                insert_image_location = pymupdf.Rect(page.rect)
                insert_image_location.intersect(image_bbox)

                transform_inv = pymupdf.Matrix(transform)
                transform_inv.invert()

                # The image’s “transformation matrix” is defined as the matrix, for which the expression
                # bbox / transform == pymupdf.Rect(0, 0, 1, 1) is true.
                # Consequently, by multiplying page.rect with transform^-1 and scaling to the image size, we get the visible
                # part of the page, measured in image pixel coordinates.
                crop = pymupdf.Rect(insert_image_location)
                crop.transform(transform_inv)
                crop.transform(img_size)
                crop = crop.round()
                img = _pixmap_from_xref(out_doc, xref)

                # Concert to Pillow image for cropping, since cropping as PixMap causes uncontrollable caching in
                # MuPDF, leading to memory leaks.
                pillow_image = img.pil_image()
                cropped_image = pillow_image.crop((crop.x0, crop.y0, crop.x1, crop.y1))
                bytes_io = io.BytesIO()
                cropped_image.save(bytes_io, extension, quality=85, optimize=True)
                img_byte_arr = bytes_io.getvalue()

                old_size = dict["size"]
                new_size = len(img_byte_arr)
                if len(img_byte_arr) > 0.8 * dict["size"]:
                    logging.info(f"  Skipping crop as new image is not significantly smaller ({old_size} -> {new_size} bytes).")
                    continue
                else:
                    logging.info(f"  Cropped image is significantly smaller ({old_size} -> {new_size} bytes), replacing...")

                page.delete_image(xref)
                page.insert_image(
                    insert_image_location,
                    stream=img_byte_arr,
                    rotate=-rotation
                )
        except ValueError:
            logging.info("  Encountered ValueError, skipping image crop.")


def replace_jpx_images(doc: pymupdf.Document, page_index: int):
    page = doc[page_index]
    for dict in page.get_image_info(xrefs=True):
        xref = dict['xref']
        try:
            extracted_img = doc.extract_image(xref)
            if extracted_img['ext'] == 'jpx':
                # Some viewer, most notably the Edge browser, have problems displaying JPX images (slow / bad quality).
                # Therefore, we convert them to JPG.
                image_bbox = pymupdf.Rect(*dict["bbox"])
                logging.info(f"  Converting JPX image to JPG (bbox {image_bbox}, page.rect {page.rect}).")

                img = _pixmap_from_xref(doc, xref)
                if img:
                    page.replace_image(xref, stream=img.tobytes('jpg', jpg_quality=85))
        except ValueError:
            logging.info(f"  Encountered ValueError for xref {xref}, skipping replace_jpx_images.")


def downscale_images_x2(doc: pymupdf.Document, page_index: int) -> bool:
    downscale_successful = False
    page = doc[page_index]
    for dict in page.get_image_info(xrefs=True):
        xref = dict['xref']
        try:
            extracted_img = doc.extract_image(xref)
            ext = extracted_img['ext']
            image_bbox = pymupdf.Rect(*dict["bbox"])

            fp = io.BytesIO(extracted_img["image"])
            img = Image.open(fp)

            if ext == "jpeg":
                logging.info(f"  Downscaling {ext} image (width {dict['width']}, height {dict['height']}, bbox {image_bbox}, page.rect {page.rect}).")
                (width, height) = (img.width // 2, img.height // 2)
                if not (width > 0 and height > 0):
                    continue
                img = img.resize((width, height))
            else:
                # Always use JPEG when downscaling, as downscaling other image formats such as PNG can lead to strange
                # errors (e.g. 23dc42f0-5937-11ef-a4fb-00155d7ba234.pdf from Boreholes)
                logging.info(f"  Converting {ext} image to JPEG (width {dict['width']}, height {dict['height']}, bbox {image_bbox}, page.rect {page.rect}).")

            bytes_io = io.BytesIO()
            img.save(bytes_io, format="jpeg")
            page.replace_image(xref, stream=bytes_io.getvalue())
            # Without clean_contents() after replace_image(), we get issues (changing xref values, increasing PDF file
            # size) with certain input PDFs, e.g. deep well AM7RV03900_bp_19960801_Wellenberg-SB1.pdf.
            page.clean_contents()
            downscale_successful = True
        except ValueError:
            logging.info(f"  Encountered ValueError for xref {xref}, skipping downscale_images_x2.")

    return downscale_successful


def _pixmap_from_xref(doc: pymupdf.Document, xref: int) -> pymupdf.Pixmap:
    try:
        img = pymupdf.Pixmap(doc, xref)

        # Fix black-white inversion, e.g. for A8297.pdf.
        if not img.colorspace:  # a stencil-only pixmap, see https://github.com/pymupdf/PyMuPDF/issues/3912
            png = img.tobytes()  # convert it to a PNG
            img = pymupdf.Pixmap(png)  # re-open from a memory PNG
            img.invert_irect()  # invert the b&w pixmap

        return img
    except FzErrorFormat:
        logging.info("  Unsupported image format. Skipping image.")
