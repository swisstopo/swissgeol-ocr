import pymupdf
from pymupdf.mupdf import FzErrorFormat


def rotation_from_transform_matrix(transform: pymupdf.Matrix) -> int | None:
    if abs(transform.b) < pymupdf.EPSILON and abs(transform.c) < pymupdf.EPSILON:
        if abs(transform.a) > pymupdf.EPSILON and abs(transform.d) > pymupdf.EPSILON:
            if transform.a > 0 and transform.d > 0:
                return 0
            if transform.a < 0 and transform.d < 0:
                return 180
    if abs(transform.a) < pymupdf.EPSILON and abs(transform.d) < pymupdf.EPSILON:
        if abs(transform.b) > pymupdf.EPSILON and abs(transform.c) > pymupdf.EPSILON:
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
        print("  Skipping page because rotation is not 0 but {}.".format(page.rotation))
        return

    for dict in page.get_image_info(xrefs=True):
        xref = dict["xref"]
        if dict["width"] == 1 and dict["height"] == 1:
            # Ignore the 1x1 dummy image that is added by the PyMuPDF Page.delete_image method; see LGD-579
            continue

        try:
            img_size = pymupdf.Matrix(dict["width"], dict["height"])
            extracted_img = out_doc.extract_image(xref)
            image_bbox = pymupdf.Rect(*dict["bbox"])

            extension = extracted_img['ext']
            if extension == 'jb2':
                # Example PDF file with a JBIG2 image: A204.pdf
                print("  Skipping JBIG2 image.")
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
                print("  Cropping {} image (bbox {}, page.rect {}).".format(extension, image_bbox, page.rect))
                transform = pymupdf.Matrix(dict["transform"])

                if not page.rect.intersects(image_bbox):
                    print("  Image does not intersect the visible part of the page. Skipping image.")
                    continue

                rotation = rotation_from_transform_matrix(transform)
                if rotation is None:
                    print("  Image rotation could not be computed from transform matrix. Skipping image.")
                    continue

                transform_inv = pymupdf.Matrix(transform)
                transform_inv.invert()

                # The image’s “transformation matrix” is defined as the matrix, for which the expression
                # bbox / transform == pymupdf.Rect(0, 0, 1, 1) is true.
                # Consequently, by multiplying page.rect with transform^-1 and scaling to the image size, we get the visible
                # part of the page, measured in image pixel coordinates.
                crop = pymupdf.Rect(page.rect)
                crop.transform(transform_inv)
                crop.transform(img_size)

                img = _pixmap_from_xref(out_doc, xref)
                cropped_image = pymupdf.Pixmap(img, int(img.width), int(img.height), crop.round())
                cropped_image_bytes = cropped_image.tobytes(extension, jpg_quality=85)
                if len(cropped_image_bytes) > 0.8 * dict["size"]:
                    print("  Skipping crop as new image is not significantly smaller.")
                    continue

                page.delete_image(xref)

                insert_image_location = pymupdf.Rect(page.rect)
                insert_image_location.intersect(image_bbox)

                page.insert_image(
                    insert_image_location,
                    stream=cropped_image_bytes,
                    rotate=-rotation
                )
        except ValueError:
            print("  Encountered ValueError, skipping image crop.")


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
                print(f"  Converting JPX image to JPG (bbox {image_bbox}, page.rect {page.rect}).")

                img = _pixmap_from_xref(doc, xref)
                if img:
                    page.replace_image(xref, stream=img.tobytes('jpg', jpg_quality=85))
        except ValueError:
            print(f"  Encountered ValueError for xref {xref}, skipping replace_jpx_images.")


def downscale_images_x2(doc: pymupdf.Document, page_index: int):
    page = doc[page_index]
    for dict in page.get_image_info(xrefs=True):
        xref = dict['xref']
        try:
            extracted_img = doc.extract_image(xref)
            ext = extracted_img['ext']
            image_bbox = pymupdf.Rect(*dict["bbox"])
            print(f"  Downscaling {ext} image (width {dict['width']}, height {dict['height']}, bbox {image_bbox}, page.rect {page.rect}).")

            img = _pixmap_from_xref(doc, xref)
            img.shrink(1)  # reduce width and height by a factor of 2^1 = 2
            page.replace_image(xref, stream=img.tobytes(ext, jpg_quality=85))
            # Without clean_contents() after replace_image(), we get issues (changing xref values, increasing PDF file
            # size) with certain input PDFs, e.g. deep well AM7RV03900_bp_19960801_Wellenberg-SB1.pdf.
            page.clean_contents()
        except ValueError:
            print(f"  Encountered ValueError for xref {xref}, skipping downscale_images_x2.")


def _pixmap_from_xref(doc: pymupdf.Document, xref: int) -> pymupdf.Pixmap:
    try:
        img = pymupdf.Pixmap(doc, xref)
        # Force the image into RGB color-space. Otherwise, colors might get distorted, e.g. in A8297.pdf.
        # See also https://github.com/pymupdf/PyMuPDF/issues/725#issuecomment-730561405
        return pymupdf.Pixmap(pymupdf.csRGB, img)
    except FzErrorFormat:
        print("  Unsupported image format. Skipping image.")
