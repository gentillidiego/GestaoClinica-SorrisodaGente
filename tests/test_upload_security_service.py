import io

import pytest
from PIL import Image
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from pypdf import PdfWriter
from werkzeug.datastructures import FileStorage

import services.upload_security_service as upload_security


def make_storage(content, filename, mimetype='application/octet-stream'):
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type=mimetype,
    )


def image_bytes(image_format='PNG', size=(24, 16)):
    stream = io.BytesIO()
    Image.new('RGB', size, color=(30, 90, 150)).save(
        stream,
        format=image_format,
    )
    return stream.getvalue()


def pdf_bytes():
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    writer.write(stream)
    return stream.getvalue()


def dicom_bytes():
    stream = io.BytesIO()
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset(
        None,
        {},
        file_meta=file_meta,
        preamble=b'\0' * 128,
    )
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.Rows = 32
    dataset.Columns = 48
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = 'MONOCHROME2'
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.PixelData = b'\0' * (dataset.Rows * dataset.Columns)
    dataset.save_as(stream, enforce_file_format=True)
    return stream.getvalue()


def test_real_content_wins_over_browser_mime_and_wrong_image_extension():
    upload = make_storage(
        image_bytes('PNG'),
        'radiografia.jpg',
        mimetype='text/plain',
    )

    inspection = upload_security.inspect_uploaded_file(
        upload,
        allowed_formats=upload_security.STANDARD_IMAGE_FORMATS,
    )

    assert inspection.detected_format == 'PNG'
    assert inspection.safe_filename == 'radiografia.png'
    assert inspection.mime_type == 'image/png'
    assert inspection.filename_corrected is True
    assert (inspection.width, inspection.height) == (24, 16)
    assert upload.stream.tell() == 0


def test_corrupt_and_fake_images_are_rejected_before_storage():
    with pytest.raises(upload_security.UploadValidationError, match='corrompida'):
        upload_security.inspect_uploaded_file(
            make_storage(
                b'\xff\xd8\xff\xe0' + b'truncated',
                'quebrada.jpg',
                'image/jpeg',
            ),
            allowed_formats=upload_security.STANDARD_IMAGE_FORMATS,
        )

    with pytest.raises(upload_security.UploadValidationError, match='formato permitido'):
        upload_security.inspect_uploaded_file(
            make_storage(b'arquivo executavel', 'falsa.png', 'image/png'),
            allowed_formats=upload_security.STANDARD_IMAGE_FORMATS,
        )


def test_image_pixel_bomb_is_rejected_with_configurable_limit(monkeypatch):
    monkeypatch.setattr(upload_security, 'CLINICAL_IMAGE_MAX_PIXELS', 100)

    with pytest.raises(upload_security.UploadValidationError, match='grande demais'):
        upload_security.inspect_uploaded_file(
            make_storage(image_bytes('PNG', (11, 10)), 'grande.png', 'image/png'),
            allowed_formats=upload_security.STANDARD_IMAGE_FORMATS,
        )


def test_pdf_is_parsed_and_fake_or_truncated_pdf_is_rejected():
    inspection = upload_security.inspect_uploaded_file(
        make_storage(pdf_bytes(), 'laudo.bin', 'application/octet-stream'),
        allowed_formats=upload_security.CLINICAL_LAB_FORMATS,
    )
    assert inspection.detected_format == 'PDF'
    assert inspection.safe_filename == 'laudo.pdf'
    assert inspection.pages == 1

    with pytest.raises(upload_security.UploadValidationError, match='encerramento válido'):
        upload_security.inspect_uploaded_file(
            make_storage(b'%PDF-1.7\n1 0 obj\n', 'incompleto.pdf', 'application/pdf'),
            allowed_formats=upload_security.CLINICAL_LAB_FORMATS,
        )


def test_dicom_metadata_is_validated_without_decoding_large_pixel_payload():
    inspection = upload_security.inspect_uploaded_file(
        make_storage(dicom_bytes(), 'captura.dcm', 'application/dicom'),
        allowed_formats=upload_security.ENDODONTIA_IMAGE_FORMATS,
    )

    assert inspection.detected_format == 'DICOM'
    assert inspection.mime_type == 'application/dicom'
    assert (inspection.width, inspection.height) == (48, 32)
    assert inspection.total_pixels == 1536
