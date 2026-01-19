"""Unit tests for textract."""
from ocr.textline import TextLine, TextWord
from ocr.textract import clip_rects, text_lines_from_response
from pymupdf import Rect, Matrix


def test_clip_rects():
    small = Rect(0, 0, 1000, 1000)
    assert clip_rects(small) == [small]

    large = Rect(0, 0, 3000, 3000)
    top_left = Rect(0, 0, 2000, 2000)
    top_right = Rect(1600, 0, 3000, 2000)
    bottom_left = Rect(0, 1600, 2000, 3000)
    bottom_right = Rect(1600, 1600, 3000, 3000)
    assert clip_rects(large) == [large, top_left, bottom_left, top_right, bottom_right]

    wide = Rect(0, 0, 5000, 200)
    left = Rect(0, 0, 2000, 200)
    middle = Rect(1600, 0, 3600, 200)
    right = Rect(3200, 0, 5000, 200)
    assert clip_rects(wide) == [wide, left, middle, right]

    tall = Rect(0, 0, 200, 5000)
    top = Rect(0, 0, 200, 2000)
    middle = Rect(0, 1600, 200, 3600)
    bottom = Rect(0, 3200, 200, 5000)
    assert clip_rects(tall) == [tall, top, middle, bottom]


def test_parse_response():
    response = {'DocumentMetadata': {'Pages': 1}, 'Blocks': [{'BlockType': 'PAGE', 'Geometry': {'BoundingBox': {'Width': 0.778192400932312, 'Height': 0.5504970550537109, 'Left': 0.10665097087621689, 'Top': 0.10083939880132675}, 'Polygon': [{'X': 0.10679113864898682, 'Y': 0.10083939880132675}, {'X': 0.8848433494567871, 'Y': 0.10111355036497116}, {'X': 0.8846840262413025, 'Y': 0.6513364315032959}, {'X': 0.10665097087621689, 'Y': 0.6509254574775696}]}, 'Id': 'a81edf66-b058-4317-adab-5bf4725f41d8', 'Relationships': [{'Type': 'CHILD', 'Ids': ['add5e2cc-a953-4d24-aca0-1ad68086ec38', 'b4044f2d-7f2d-45d0-832c-37897fb3776c', '738d4f72-5ca8-4a96-ad54-d609c0152782', 'a6b6d29c-3b66-41da-8fce-143e3a0f1749', '322fda1a-88a0-45c0-95ed-c5a2b78a50a3']}]}, {'BlockType': 'LINE', 'Confidence': 90.83386993408203, 'Text': 'Merry', 'Geometry': {'BoundingBox': {'Width': 0.29303497076034546, 'Height': 0.09029601514339447, 'Left': 0.34796637296676636, 'Top': 0.22256392240524292}, 'Polygon': [{'X': 0.34799033403396606, 'Y': 0.22256392240524292}, {'X': 0.6410013437271118, 'Y': 0.2226785570383072}, {'X': 0.6409761905670166, 'Y': 0.3128599226474762}, {'X': 0.34796637296676636, 'Y': 0.312736839056015}]}, 'Id': 'add5e2cc-a953-4d24-aca0-1ad68086ec38', 'Relationships': [{'Type': 'CHILD', 'Ids': ['15a29d31-5734-4a8f-beb4-0f7c781f608b']}]}, {'BlockType': 'LINE', 'Confidence': 99.56712341308594, 'Text': 'Christmas', 'Geometry': {'BoundingBox': {'Width': 0.4656425416469574, 'Height': 0.08312307298183441, 'Left': 0.2757081985473633, 'Top': 0.30257537961006165}, 'Polygon': [{'X': 0.2757299542427063, 'Y': 0.30257537961006165}, {'X': 0.7413507699966431, 'Y': 0.3027694523334503}, {'X': 0.7413272857666016, 'Y': 0.38569843769073486}, {'X': 0.2757081985473633, 'Y': 0.3854920268058777}]}, 'Id': 'b4044f2d-7f2d-45d0-832c-37897fb3776c', 'Relationships': [{'Type': 'CHILD', 'Ids': ['4ce5482a-af20-4e0b-9ca7-3b5fece0dc62']}]}, {'BlockType': 'LINE', 'Confidence': 100.0, 'Text': 'AND', 'Geometry': {'BoundingBox': {'Width': 0.08761616796255112, 'Height': 0.020372536033391953, 'Left': 0.4544379413127899, 'Top': 0.38989371061325073}, 'Polygon': [{'X': 0.45444342494010925, 'Y': 0.38989371061325073}, {'X': 0.5420541167259216, 'Y': 0.38993266224861145}, {'X': 0.5420485138893127, 'Y': 0.410266250371933}, {'X': 0.4544379413127899, 'Y': 0.4102267026901245}]}, 'Id': '738d4f72-5ca8-4a96-ad54-d609c0152782', 'Relationships': [{'Type': 'CHILD', 'Ids': ['0f802ead-cc95-4cf2-b8cf-f11ff83a9811']}]}, {'BlockType': 'LINE', 'Confidence': 100.0, 'Text': 'HAPPY NEW YEAR', 'Geometry': {'BoundingBox': {'Width': 0.35144227743148804, 'Height': 0.02117144875228405, 'Left': 0.3371144235134125, 'Top': 0.4196668565273285}, 'Polygon': [{'X': 0.337119996547699, 'Y': 0.4196668565273285}, {'X': 0.6885566711425781, 'Y': 0.4198265075683594}, {'X': 0.6885507702827454, 'Y': 0.4408383071422577}, {'X': 0.3371144235134125, 'Y': 0.44067633152008057}]}, 'Id': 'a6b6d29c-3b66-41da-8fce-143e3a0f1749', 'Relationships': [{'Type': 'CHILD', 'Ids': ['29999b63-e502-4c8b-a92d-8c27022305da', 'f07c5726-3578-49c0-8694-419cd7bf0c3f', '36304d80-7543-4a32-a743-0334dc59e61c']}]}, {'BlockType': 'LINE', 'Confidence': 100.0, 'Text': '2026', 'Geometry': {'BoundingBox': {'Width': 0.1646667718887329, 'Height': 0.0383591502904892, 'Left': 0.4189315438270569, 'Top': 0.4527221918106079}, 'Polygon': [{'X': 0.41894182562828064, 'Y': 0.4527221918106079}, {'X': 0.5835983157157898, 'Y': 0.4527987241744995}, {'X': 0.5835877060890198, 'Y': 0.4910813570022583}, {'X': 0.4189315438270569, 'Y': 0.49100279808044434}]}, 'Id': '322fda1a-88a0-45c0-95ed-c5a2b78a50a3', 'Relationships': [{'Type': 'CHILD', 'Ids': ['9b0e9dcc-d49d-4d13-9133-680856b0b7bf']}]}, {'BlockType': 'WORD', 'Confidence': 90.83386993408203, 'Text': 'Merry', 'TextType': 'PRINTED', 'Geometry': {'BoundingBox': {'Width': 0.29303497076034546, 'Height': 0.09029601514339447, 'Left': 0.34796637296676636, 'Top': 0.22256392240524292}, 'Polygon': [{'X': 0.34799033403396606, 'Y': 0.22256392240524292}, {'X': 0.6410013437271118, 'Y': 0.2226785570383072}, {'X': 0.6409761905670166, 'Y': 0.3128599226474762}, {'X': 0.34796637296676636, 'Y': 0.312736839056015}], 'RotationAngle': 0.0}, 'Id': '15a29d31-5734-4a8f-beb4-0f7c781f608b'}, {'BlockType': 'WORD', 'Confidence': 99.56712341308594, 'Text': 'Christmas', 'TextType': 'PRINTED', 'Geometry': {'BoundingBox': {'Width': 0.4656425416469574, 'Height': 0.08312307298183441, 'Left': 0.2757081985473633, 'Top': 0.30257537961006165}, 'Polygon': [{'X': 0.2757299542427063, 'Y': 0.30257537961006165}, {'X': 0.7413507699966431, 'Y': 0.3027694523334503}, {'X': 0.7413272857666016, 'Y': 0.38569843769073486}, {'X': 0.2757081985473633, 'Y': 0.3854920268058777}], 'RotationAngle': 0.0}, 'Id': '4ce5482a-af20-4e0b-9ca7-3b5fece0dc62'}, {'BlockType': 'WORD', 'Confidence': 100.0, 'Text': 'AND', 'TextType': 'PRINTED', 'Geometry': {'BoundingBox': {'Width': 0.08761616796255112, 'Height': 0.020372536033391953, 'Left': 0.4544379413127899, 'Top': 0.38989371061325073}, 'Polygon': [{'X': 0.45444342494010925, 'Y': 0.38989371061325073}, {'X': 0.5420541167259216, 'Y': 0.38993266224861145}, {'X': 0.5420485138893127, 'Y': 0.410266250371933}, {'X': 0.4544379413127899, 'Y': 0.4102267026901245}], 'RotationAngle': 0.0}, 'Id': '0f802ead-cc95-4cf2-b8cf-f11ff83a9811'}, {'BlockType': 'WORD', 'Confidence': 100.0, 'Text': 'HAPPY', 'TextType': 'PRINTED', 'Geometry': {'BoundingBox': {'Width': 0.1310444176197052, 'Height': 0.020762523636221886, 'Left': 0.33711445331573486, 'Top': 0.41985654830932617}, 'Polygon': [{'X': 0.3371199369430542, 'Y': 0.41985654830932617}, {'X': 0.46815887093544006, 'Y': 0.4199160933494568}, {'X': 0.4681532680988312, 'Y': 0.4406190812587738}, {'X': 0.33711445331573486, 'Y': 0.44055867195129395}], 'RotationAngle': 0.0}, 'Id': '29999b63-e502-4c8b-a92d-8c27022305da'}, {'BlockType': 'WORD', 'Confidence': 100.0, 'Text': 'NEW', 'TextType': 'PRINTED', 'Geometry': {'BoundingBox': {'Width': 0.09267579019069672, 'Height': 0.02011886239051819, 'Left': 0.48016321659088135, 'Top': 0.4202031195163727}, 'Polygon': [{'X': 0.4801686704158783, 'Y': 0.4202031195163727}, {'X': 0.5728390216827393, 'Y': 0.4202452301979065}, {'X': 0.5728334784507751, 'Y': 0.44032198190689087}, {'X': 0.48016321659088135, 'Y': 0.4402792751789093}], 'RotationAngle': 0.0}, 'Id': 'f07c5726-3578-49c0-8694-419cd7bf0c3f'}, {'BlockType': 'WORD', 'Confidence': 100.0, 'Text': 'YEAR', 'TextType': 'PRINTED', 'Geometry': {'BoundingBox': {'Width': 0.10590099543333054, 'Height': 0.021059909835457802, 'Left': 0.582655668258667, 'Top': 0.41977840662002563}, 'Polygon': [{'X': 0.582661509513855, 'Y': 0.41977840662002563}, {'X': 0.6885566711425781, 'Y': 0.4198265075683594}, {'X': 0.6885507702827454, 'Y': 0.4408383071422577}, {'X': 0.582655668258667, 'Y': 0.44078949093818665}], 'RotationAngle': 0.0}, 'Id': '36304d80-7543-4a32-a743-0334dc59e61c'}, {'BlockType': 'WORD', 'Confidence': 100.0, 'Text': '2026', 'TextType': 'PRINTED', 'Geometry': {'BoundingBox': {'Width': 0.1646667718887329, 'Height': 0.0383591502904892, 'Left': 0.4189315438270569, 'Top': 0.4527221918106079}, 'Polygon': [{'X': 0.41894182562828064, 'Y': 0.4527221918106079}, {'X': 0.5835983157157898, 'Y': 0.4527987241744995}, {'X': 0.5835877060890198, 'Y': 0.4910813570022583}, {'X': 0.4189315438270569, 'Y': 0.49100279808044434}], 'RotationAngle': 0.0}, 'Id': '9b0e9dcc-d49d-4d13-9133-680856b0b7bf'}], 'DetectDocumentTextModelVersion': '1.0', 'ResponseMetadata': {'RequestId': '07b776a6-b135-44db-ad07-21fc61c31698', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amzn-requestid': '07b776a6-b135-44db-ad07-21fc61c31698', 'content-type': 'application/x-amz-json-1.1', 'content-length': '6870', 'date': 'Mon, 19 Jan 2026 10:48:10 GMT'}, 'RetryAttempts': 0}}
    page_height = 841.8897705078125
    transform = Matrix(595.303955078125, 0.0, 0.0, 841.8897705078125, 0.0, 0.0)

    expected_lines = [
        TextLine(
            text="Merry",
            orientation=0,
            derotated_rect=Rect(207.145751953125, 187.42607812608247, 381.59063720703125, 263.3417441395425),
            rect=Rect(207.145751953125, 187.37428283691406, 381.59063720703125, 263.3935852050781),
            confidence=0.9083386993408203,
            words=[
                TextWord(
                    text="Merry",
                    derotated_rect=Rect(207.145751953125, 187.42607812608247, 381.59063720703125, 263.3417441395425),
                    orientation=0,
                )
            ],
        ),
        TextLine(
            text="Christmas",
            orientation=0,
            derotated_rect=Rect(164.13018798828125, 254.82199799657317, 441.32904052734375, 324.6286855971768),
            rect=Rect(164.13018798828125, 254.73512268066406, 441.32904052734375, 324.715576171875),
            confidence=0.9956712341308593,
            words=[
                TextWord(
                    text="Christmas",
                    derotated_rect=Rect(164.13018798828125, 254.82199799657317, 441.32904052734375, 324.6286855971768),
                    orientation=0,
                )
            ],
        ),
        TextLine(
            text="AND",
            orientation=0,
            derotated_rect=Rect(270.5287170410156, 328.26419051810564, 322.68695068359375, 345.3823243744725),
            rect=Rect(270.5287170410156, 328.2475280761719, 322.68695068359375, 345.3989562988281),
            confidence=1.0,
            words=[
                TextWord(
                    text="AND",
                    derotated_rect=Rect(270.5287170410156, 328.26419051810564, 322.68695068359375, 345.3823243744725),
                    orientation=0,
                )
            ],
        ),
        TextLine(
            text="HAPPY NEW YEAR",
            orientation=0,
            derotated_rect=Rect(200.685546875, 353.3814237938003, 409.9005126953125, 371.06907669448094),
            rect=Rect(200.685546875, 353.313232421875, 409.9005126953125, 371.13726806640625),
            confidence=1.0,
            words=[
                TextWord(
                    text="HAPPY",
                    derotated_rect=Rect(200.68556213378906, 353.4983671566244, 278.69683837890625, 370.927261505485),
                    orientation=0,
                ),
                TextWord(
                    text="NEW",
                    derotated_rect=Rect(285.8430480957031, 353.7826841684573, 341.0133361816406, 370.6846009877927),
                    orientation=0,
                ),
                TextWord(
                    text="YEAR",
                    derotated_rect=Rect(346.85723876953125, 353.4276884305617, 409.9005126953125, 371.11671464561016),
                    orientation=0,
                ),
            ],
        ),
        TextLine(
            text="2026",
            orientation=0,
            derotated_rect=Rect(249.3916015625, 381.1752469019573, 347.41839599609375, 413.40330534413647),
            rect=Rect(249.3916015625, 381.1421813964844, 347.41839599609375, 413.4363708496094),
            confidence=1.0,
            words=[
                TextWord(
                    text="2026",
                    derotated_rect=Rect(
                        249.3916015625, 381.1752469019573, 347.41839599609375, 413.40330534413647),
                    orientation=0,
                )
            ],
        ),
    ]

    assert text_lines_from_response(response, transform, page_height) == expected_lines

