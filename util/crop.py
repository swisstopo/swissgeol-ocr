import fitz
from pymupdf.mupdf import FzErrorFormat


def rotation_from_transform_matrix(transform: fitz.Matrix) -> int | None:
    if abs(transform.b) < fitz.EPSILON and abs(transform.c) < fitz.EPSILON:
        if abs(transform.a) > fitz.EPSILON and abs(transform.d) > fitz.EPSILON:
            if transform.a > 0 and transform.d > 0:
                return 0
            if transform.a < 0 and transform.d < 0:
                return 180
    if abs(transform.a) < fitz.EPSILON and abs(transform.d) < fitz.EPSILON:
        if abs(transform.b) > fitz.EPSILON and abs(transform.c) > fitz.EPSILON:
            if transform.b > 0 > transform.c:
                return 90
            if transform.b < 0 < transform.c:
                return 270


def crop_images(page: fitz.Page, out_doc: fitz.Document):
    if page.rotation != 0:
        # We had some issues with misplacement of the cropped image on pages with a non-trivial rotation, so to be on
        # the safe side, we enforce rotation=0. The preceding resize step should normally have reset the page rotation
        # already.
        print("  Skipping page because rotation is not 0 but {}.".format(page.rotation))
        return

    images_info = {dict["xref"]: dict for dict in page.get_image_info(xrefs=True)}

    for xref, dict in images_info.items():
        try:
            img_size = fitz.Matrix(dict["width"], dict["height"])
            extracted_img = out_doc.extract_image(xref)
            image_bbox = fitz.Rect(*dict["bbox"])

            extension = extracted_img['ext']
            if extension == 'jpx':
                # Some viewer, most notably the Edge browser, have problems displaying JPX images (slow / bad quality).
                # Therefore, we convert them to JPG.
                new_extension = 'jpg'
            else:
                new_extension = extension

            # allow images that are only slightly larger than the page, as cropping the image is not likely to reduce
            # the file size (it might even increase it) and might decrease the image quality.
            margin = 10  # in points
            page_rect_with_margin = fitz.Rect(
                page.rect.x0 - margin,
                page.rect.y0 - margin,
                page.rect.x1 + margin,
                page.rect.y1 + margin
            )

            if not page_rect_with_margin.contains(image_bbox) or new_extension != extension:
                print("  Cropping {} image (bbox {}, page.rect {}).".format(extension, image_bbox, page.rect))
                transform = fitz.Matrix(dict["transform"])

                if not page.rect.intersects(image_bbox):
                    print("  Image does not intersect the visible part of the page. Skipping image.")
                    continue

                rotation = rotation_from_transform_matrix(transform)
                if rotation is None:
                    print("  Image rotation could not be computed from transform matrix. Skipping image.")
                    continue

                transform_inv = fitz.Matrix(transform)
                transform_inv.invert()

                # The image’s “transformation matrix” is defined as the matrix, for which the expression
                # bbox / transform == fitz.Rect(0, 0, 1, 1) is true.
                # Consequently, by multiplying page.rect with transform^-1 and scaling to the image size, we get the visible
                # part of the page, measured in image pixel coordinates.
                crop = fitz.Rect(page.rect)
                crop.transform(transform_inv)
                crop.transform(img_size)

                # print(extracted_img["ext"])
                try:
                    img = fitz.Pixmap(extracted_img["image"])
                except FzErrorFormat:
                    print("  Unsupported image format. Skipping image.")
                    continue

                cropped_image = fitz.Pixmap(img, int(img.width), int(img.height), crop.round())
                page.delete_image(xref)

                insert_image_location = fitz.Rect(page.rect)
                insert_image_location.intersect(image_bbox)

                page.insert_image(
                    insert_image_location,
                    stream=cropped_image.tobytes(new_extension, jpg_quality=85),
                    rotate=-rotation
                )
        except ValueError:
            print("  Encountered ValueError, skipping image crop.")
