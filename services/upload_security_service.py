import logging
import os
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pydicom import dcmread
from pydicom.errors import InvalidDicomError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from werkzeug.utils import secure_filename


logger = logging.getLogger(__name__)


def _positive_int_from_env(name, default):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        logger.warning('Valor inválido para %s; usando %s.', name, default)
        return default
    return value if value > 0 else default


CLINICAL_UPLOAD_MAX_FILE_MB = _positive_int_from_env(
    'CLINICAL_UPLOAD_MAX_FILE_MB',
    300,
)
CLINICAL_UPLOAD_MAX_REQUEST_MB = _positive_int_from_env(
    'CLINICAL_UPLOAD_MAX_REQUEST_MB',
    320,
)
CLINICAL_UPLOAD_MAX_FILE_BYTES = CLINICAL_UPLOAD_MAX_FILE_MB * 1024 * 1024
CLINICAL_UPLOAD_MAX_REQUEST_BYTES = (
    CLINICAL_UPLOAD_MAX_REQUEST_MB * 1024 * 1024
)

CLINICAL_IMAGE_MAX_WIDTH = _positive_int_from_env(
    'CLINICAL_IMAGE_MAX_WIDTH',
    50_000,
)
CLINICAL_IMAGE_MAX_HEIGHT = _positive_int_from_env(
    'CLINICAL_IMAGE_MAX_HEIGHT',
    50_000,
)
CLINICAL_IMAGE_MAX_PIXELS = _positive_int_from_env(
    'CLINICAL_IMAGE_MAX_PIXELS',
    150_000_000,
)
CLINICAL_IMAGE_MAX_TOTAL_PIXELS = _positive_int_from_env(
    'CLINICAL_IMAGE_MAX_TOTAL_PIXELS',
    300_000_000,
)
CLINICAL_IMAGE_MAX_FRAMES = _positive_int_from_env(
    'CLINICAL_IMAGE_MAX_FRAMES',
    512,
)
CLINICAL_PDF_MAX_PAGES = _positive_int_from_env(
    'CLINICAL_PDF_MAX_PAGES',
    10_000,
)

# Pillow avisa no limite e bloqueia acima do dobro. A verificação explícita
# abaixo continua sendo a autoridade e produz mensagens operacionais melhores.
Image.MAX_IMAGE_PIXELS = max(
    int(Image.MAX_IMAGE_PIXELS or 0),
    CLINICAL_IMAGE_MAX_PIXELS,
)


FORMAT_POLICIES = {
    'JPEG': {
        'extensions': {'.jpg', '.jpeg'},
        'canonical_extension': '.jpg',
        'mime_type': 'image/jpeg',
    },
    'PNG': {
        'extensions': {'.png'},
        'canonical_extension': '.png',
        'mime_type': 'image/png',
    },
    'WEBP': {
        'extensions': {'.webp'},
        'canonical_extension': '.webp',
        'mime_type': 'image/webp',
    },
    'TIFF': {
        'extensions': {'.tif', '.tiff'},
        'canonical_extension': '.tiff',
        'mime_type': 'image/tiff',
    },
    'DICOM': {
        'extensions': {'.dcm', '.dicom'},
        'canonical_extension': '.dcm',
        'mime_type': 'application/dicom',
    },
    'PDF': {
        'extensions': {'.pdf'},
        'canonical_extension': '.pdf',
        'mime_type': 'application/pdf',
    },
}

STANDARD_IMAGE_FORMATS = frozenset({'JPEG', 'PNG', 'WEBP'})
ENDODONTIA_IMAGE_FORMATS = frozenset(
    {'JPEG', 'PNG', 'WEBP', 'TIFF', 'DICOM'}
)
CLINICAL_LAB_FORMATS = frozenset(
    {'JPEG', 'PNG', 'WEBP', 'PDF'}
)


class UploadValidationError(ValueError):
    """Erro seguro para exibição ao usuário durante a validação do upload."""


@dataclass(frozen=True)
class UploadInspection:
    original_filename: str
    safe_filename: str
    detected_format: str
    extension: str
    mime_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    total_pixels: int | None = None
    pages: int | None = None
    encrypted: bool = False
    filename_corrected: bool = False

    @property
    def is_image(self):
        return self.detected_format != 'PDF'


def human_file_size(byte_count):
    value = float(byte_count)
    for unit in ('bytes', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            if unit == 'bytes':
                return f'{int(value)} {unit}'
            return f'{value:.0f} {unit}'
        value /= 1024
    return f'{value:.0f} GB'


def request_size_is_allowed(content_length):
    return (
        not content_length
        or int(content_length) <= CLINICAL_UPLOAD_MAX_REQUEST_BYTES
    )


def _stream_size(stream):
    original_position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(original_position)
    return size


def _detect_format(stream):
    stream.seek(0)
    head = stream.read(1024)
    stream.seek(0)

    if head.startswith(b'\xff\xd8\xff'):
        return 'JPEG'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'PNG'
    if head.startswith((b'II*\x00', b'MM\x00*')):
        return 'TIFF'
    if (
        len(head) >= 12
        and head.startswith(b'RIFF')
        and head[8:12] == b'WEBP'
    ):
        return 'WEBP'
    if len(head) >= 132 and head[128:132] == b'DICM':
        return 'DICOM'
    if head.lstrip(b'\x00\t\r\n ').startswith(b'%PDF-'):
        return 'PDF'
    return None


def _safe_filename(original_filename, detected_format):
    policy = FORMAT_POLICIES[detected_format]
    safe_name = secure_filename(original_filename or '')
    original_extension = Path(safe_name).suffix.lower()
    extension = (
        original_extension
        if original_extension in policy['extensions']
        else policy['canonical_extension']
    )
    stem = Path(safe_name).stem if safe_name else ''
    stem = secure_filename(stem) or (
        'documento' if detected_format == 'PDF' else 'imagem'
    )
    corrected_name = f'{stem}{extension}'
    return corrected_name, extension, corrected_name != safe_name


def _check_image_dimensions(width, height, *, filename, frames=1):
    if width <= 0 or height <= 0:
        raise UploadValidationError(
            f'O arquivo “{filename}” não possui dimensões de imagem válidas.'
        )
    if (
        width > CLINICAL_IMAGE_MAX_WIDTH
        or height > CLINICAL_IMAGE_MAX_HEIGHT
    ):
        raise UploadValidationError(
            f'A imagem “{filename}” possui dimensão fora do limite de segurança '
            f'({CLINICAL_IMAGE_MAX_WIDTH} × {CLINICAL_IMAGE_MAX_HEIGHT} pixels).'
        )
    pixels = width * height
    if pixels > CLINICAL_IMAGE_MAX_PIXELS:
        raise UploadValidationError(
            f'A imagem “{filename}” é grande demais para processamento seguro '
            f'({pixels:,} pixels).'
        )
    if frames > CLINICAL_IMAGE_MAX_FRAMES:
        raise UploadValidationError(
            f'O arquivo “{filename}” contém quadros demais para processamento '
            'seguro.'
        )
    return pixels


def _inspect_pillow_image(stream, filename, expected_format):
    first_width = None
    first_height = None
    total_pixels = 0

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            stream.seek(0)
            with Image.open(stream) as image:
                actual_format = str(image.format or '').upper()
                if actual_format != expected_format:
                    raise UploadValidationError(
                        f'O conteúdo de “{filename}” não corresponde ao formato '
                        'da imagem enviada.'
                    )

                frames = int(getattr(image, 'n_frames', 1) or 1)
                if frames > CLINICAL_IMAGE_MAX_FRAMES:
                    raise UploadValidationError(
                        f'O arquivo “{filename}” contém quadros demais para '
                        'processamento seguro.'
                    )

                for frame_index in range(frames):
                    if frame_index:
                        image.seek(frame_index)
                    width, height = image.size
                    if first_width is None:
                        first_width, first_height = width, height
                    frame_pixels = _check_image_dimensions(
                        width,
                        height,
                        filename=filename,
                        frames=frames,
                    )
                    total_pixels += frame_pixels
                    if total_pixels > CLINICAL_IMAGE_MAX_TOTAL_PIXELS:
                        raise UploadValidationError(
                            f'O arquivo “{filename}” possui volume total de '
                            'pixels fora do limite de segurança.'
                        )
                    # load() força a decodificação e detecta truncamentos que uma
                    # simples leitura do cabeçalho não encontraria.
                    image.load()
    except UploadValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise UploadValidationError(
            f'A imagem “{filename}” excede o volume seguro de pixels para '
            'processamento.'
        ) from exc
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise UploadValidationError(
            f'A imagem “{filename}” está corrompida, incompleta ou não pôde ser lida.'
        ) from exc
    finally:
        stream.seek(0)

    return first_width, first_height, frames, total_pixels


def _inspect_dicom(stream, filename):
    try:
        stream.seek(0)
        dataset = dcmread(
            stream,
            stop_before_pixels=True,
            force=False,
        )
        rows = int(getattr(dataset, 'Rows', 0) or 0)
        columns = int(getattr(dataset, 'Columns', 0) or 0)
        frames = int(getattr(dataset, 'NumberOfFrames', 1) or 1)
        if not (
            getattr(dataset, 'SOPClassUID', None)
            or getattr(dataset.file_meta, 'MediaStorageSOPClassUID', None)
        ):
            raise UploadValidationError(
                f'O arquivo DICOM “{filename}” não possui identificação clínica válida.'
            )
        pixels = _check_image_dimensions(
            columns,
            rows,
            filename=filename,
            frames=frames,
        )
        total_pixels = pixels * frames
        if total_pixels > CLINICAL_IMAGE_MAX_TOTAL_PIXELS:
            raise UploadValidationError(
                f'O arquivo DICOM “{filename}” possui volume total de pixels '
                'fora do limite de segurança.'
            )
        return columns, rows, frames, total_pixels
    except UploadValidationError:
        raise
    except (InvalidDicomError, OSError, TypeError, ValueError) as exc:
        raise UploadValidationError(
            f'O arquivo “{filename}” não é um DICOM válido ou está corrompido.'
        ) from exc
    finally:
        stream.seek(0)


def _declared_pdf_page_count(reader):
    try:
        pages_root = reader.trailer['/Root']['/Pages']
        return int(pages_root.get('/Count', 0) or 0)
    except (KeyError, TypeError, ValueError):
        return 0


def _inspect_pdf(stream, filename, size_bytes):
    try:
        stream.seek(max(0, size_bytes - 1024 * 1024))
        tail = stream.read()
        if b'%%EOF' not in tail:
            raise UploadValidationError(
                f'O PDF “{filename}” está incompleto ou não possui encerramento válido.'
            )

        stream.seek(0)
        reader = PdfReader(stream, strict=False)
        encrypted = bool(reader.is_encrypted)
        if encrypted:
            # Um PDF protegido por senha ainda é um documento real. Preservamos
            # esse fluxo legítimo sem tentar quebrar ou remover a proteção.
            return None, True

        declared_pages = _declared_pdf_page_count(reader)
        if declared_pages > CLINICAL_PDF_MAX_PAGES:
            raise UploadValidationError(
                f'O PDF “{filename}” possui páginas demais para processamento seguro.'
            )

        page_count = len(reader.pages)
        if page_count <= 0:
            raise UploadValidationError(
                f'O PDF “{filename}” não contém páginas legíveis.'
            )
        if page_count > CLINICAL_PDF_MAX_PAGES:
            raise UploadValidationError(
                f'O PDF “{filename}” possui páginas demais para processamento seguro.'
            )

        # Acessar as caixas da primeira e última página força a resolução das
        # referências essenciais sem descompactar imagens clínicas grandes.
        page_indexes = {0, page_count - 1}
        for page_index in page_indexes:
            page = reader.pages[page_index]
            if page.mediabox is None:
                raise UploadValidationError(
                    f'O PDF “{filename}” possui estrutura de página inválida.'
                )
        return page_count, False
    except UploadValidationError:
        raise
    except (
        PdfReadError,
        EOFError,
        KeyError,
        OSError,
        RecursionError,
        TypeError,
        ValueError,
    ) as exc:
        raise UploadValidationError(
            f'O PDF “{filename}” está corrompido ou possui estrutura inválida.'
        ) from exc
    finally:
        stream.seek(0)


def inspect_uploaded_file(file, *, allowed_formats):
    """
    Inspeciona os bytes reais e devolve metadados confiáveis.

    O MIME informado pelo navegador não participa da decisão. Quando apenas a
    extensão está errada, o nome é corrigido para preservar a operação.
    """
    if not file or not getattr(file, 'filename', None):
        raise UploadValidationError('Selecione um arquivo para enviar.')

    stream = file.stream
    try:
        size_bytes = _stream_size(stream)
    except (AttributeError, OSError, ValueError) as exc:
        raise UploadValidationError(
            f'Não foi possível ler o arquivo “{file.filename}”.'
        ) from exc

    if size_bytes <= 0:
        raise UploadValidationError(
            f'O arquivo “{file.filename}” está vazio.'
        )
    if size_bytes > CLINICAL_UPLOAD_MAX_FILE_BYTES:
        raise UploadValidationError(
            f'O arquivo “{file.filename}” ultrapassa o limite operacional de '
            f'{human_file_size(CLINICAL_UPLOAD_MAX_FILE_BYTES)}.'
        )

    detected_format = _detect_format(stream)
    normalized_allowed = {str(item).upper() for item in allowed_formats}
    if not detected_format or detected_format not in normalized_allowed:
        allowed_labels = ', '.join(sorted(normalized_allowed))
        raise UploadValidationError(
            f'O conteúdo de “{file.filename}” não corresponde a um formato '
            f'permitido ({allowed_labels}).'
        )

    safe_name, extension, corrected = _safe_filename(
        file.filename,
        detected_format,
    )
    policy = FORMAT_POLICIES[detected_format]

    width = height = frames = total_pixels = pages = None
    encrypted = False
    if detected_format in {'JPEG', 'PNG', 'WEBP', 'TIFF'}:
        width, height, frames, total_pixels = _inspect_pillow_image(
            stream,
            safe_name,
            detected_format,
        )
    elif detected_format == 'DICOM':
        width, height, frames, total_pixels = _inspect_dicom(
            stream,
            safe_name,
        )
    elif detected_format == 'PDF':
        pages, encrypted = _inspect_pdf(stream, safe_name, size_bytes)

    stream.seek(0)
    return UploadInspection(
        original_filename=file.filename,
        safe_filename=safe_name,
        detected_format=detected_format,
        extension=extension,
        mime_type=policy['mime_type'],
        size_bytes=size_bytes,
        width=width,
        height=height,
        frames=frames,
        total_pixels=total_pixels,
        pages=pages,
        encrypted=encrypted,
        filename_corrected=corrected,
    )
