import fcntl
import hashlib
import logging
import mimetypes
import os
import shutil
import time
from pathlib import Path
from urllib.parse import quote

from flask import Response, current_app, request, send_file
from PIL import Image, ImageOps

from services.google_drive_service import download_file_to_path


logger = logging.getLogger(__name__)

UPLOADS_ROOT = Path(os.getenv('UPLOADS_ROOT', 'uploads'))
DRIVE_CACHE_ROOT = Path(
    os.getenv('GDRIVE_LOCAL_CACHE_DIR', 'uploads/cache/gdrive')
)
DERIVATIVE_ROOT = Path(
    os.getenv('EXAM_DERIVATIVE_DIR', 'uploads/derived/exam-files')
)
X_ACCEL_PREFIX = os.getenv(
    'X_ACCEL_INTERNAL_PREFIX',
    '/_protected_exam_files/',
).rstrip('/') + '/'

CACHE_TTL_SECONDS = int(os.getenv('GDRIVE_CACHE_TTL_SECONDS', str(2 * 86400)))
CACHE_LIMIT_BYTES = int(float(os.getenv('GDRIVE_CACHE_LIMIT_GB', '15')) * 1024 ** 3)
CACHE_HIGH_WATERMARK = float(os.getenv('GDRIVE_CACHE_HIGH_WATERMARK', '0.80'))
CACHE_TARGET_WATERMARK = float(os.getenv('GDRIVE_CACHE_TARGET_WATERMARK', '0.70'))
DELIVERY_GID = int(os.getenv('X_ACCEL_FILE_GID', '33'))

THUMBNAIL_SIZE = (560, 560)
PREVIEW_SIZE = (1800, 1800)


def _absolute(path):
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve()


def _is_under(path, root):
    try:
        return os.path.commonpath(
            [str(_absolute(path)), str(_absolute(root))]
        ) == str(_absolute(root))
    except (OSError, ValueError):
        return False


def _prepare_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o750)
    current = path
    root = _absolute(UPLOADS_ROOT)
    while _is_under(current, root):
        try:
            os.chmod(current, 0o750)
            os.chown(current, -1, DELIVERY_GID)
        except OSError:
            logger.debug('Não foi possível ajustar grupo de %s', current)
        if _absolute(current) == root:
            break
        current = current.parent


def set_delivery_permissions(path):
    path = Path(path)
    _prepare_directory(path.parent)
    try:
        os.chmod(path, 0o640)
        os.chown(path, -1, DELIVERY_GID)
    except OSError:
        logger.debug('Não foi possível ajustar permissões de %s', path)


def cache_path_for_drive_file(file_id):
    safe_id = ''.join(
        character
        for character in str(file_id or '')
        if character.isalnum() or character in {'-', '_'}
    )
    if not safe_id:
        raise ValueError('ID do arquivo remoto inválido.')
    return DRIVE_CACHE_ROOT / safe_id


def _lock_path_for_cache(cache_path):
    return cache_path.with_name(f'.{cache_path.name}.lock')


def ensure_cached_drive_file(service, file_id):
    """Baixa uma única vez, de forma atômica e protegida contra concorrência."""
    cache_path = cache_path_for_drive_file(file_id)
    _prepare_directory(cache_path.parent)
    lock_path = _lock_path_for_cache(cache_path)

    with open(lock_path, 'a+b') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if cache_path.is_file():
                os.utime(cache_path, None)
                set_delivery_permissions(cache_path)
                return str(cache_path)

            temporary_path = cache_path.with_name(
                f'.{cache_path.name}.{os.getpid()}.part'
            )
            temporary_path.unlink(missing_ok=True)
            try:
                download_file_to_path(service, file_id, temporary_path)
                with open(temporary_path, 'rb') as downloaded:
                    os.fsync(downloaded.fileno())
                os.replace(temporary_path, cache_path)
                set_delivery_permissions(cache_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    cleanup_drive_cache()
    return str(cache_path)


def promote_staging_to_cache(staging_path, drive_file_id):
    """
    Preserva o original recente no cache por dois dias.
    Usa hardlink quando possível, evitando duplicação física durante a transição.
    """
    source = _absolute(staging_path)
    if not source.is_file():
        raise FileNotFoundError('Arquivo local de staging não encontrado.')

    cache_path = cache_path_for_drive_file(drive_file_id)
    _prepare_directory(cache_path.parent)
    lock_path = _lock_path_for_cache(cache_path)
    with open(lock_path, 'a+b') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if not cache_path.exists():
                temporary_path = cache_path.with_name(
                    f'.{cache_path.name}.{os.getpid()}.promote'
                )
                temporary_path.unlink(missing_ok=True)
                try:
                    try:
                        os.link(source, temporary_path)
                    except OSError:
                        shutil.copy2(source, temporary_path)
                    os.replace(temporary_path, cache_path)
                finally:
                    temporary_path.unlink(missing_ok=True)
            os.utime(cache_path, None)
            set_delivery_permissions(cache_path)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    cleanup_drive_cache()
    return str(cache_path)


def derivative_paths(source, record_id):
    root = DERIVATIVE_ROOT / source / str(int(record_id))
    return {
        'thumbnail': root / 'thumbnail.webp',
        'preview': root / 'preview.webp',
    }


def _save_webp_atomic(image, destination, quality):
    _prepare_directory(destination.parent)
    temporary = destination.with_name(
        f'.{destination.name}.{os.getpid()}.part'
    )
    temporary.unlink(missing_ok=True)
    try:
        image.save(
            temporary,
            format='WEBP',
            quality=quality,
            method=4,
        )
        os.replace(temporary, destination)
        set_delivery_permissions(destination)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_image_derivatives(source, record_id, original_path):
    paths = derivative_paths(source, record_id)
    if paths['thumbnail'].is_file() and paths['preview'].is_file():
        return {key: str(value) for key, value in paths.items()}

    with Image.open(original_path) as opened:
        normalized = ImageOps.exif_transpose(opened)
        if normalized.mode not in {'RGB', 'RGBA'}:
            normalized = normalized.convert('RGB')

        if not paths['preview'].is_file():
            preview = normalized.copy()
            preview.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
            _save_webp_atomic(preview, paths['preview'], quality=84)

        if not paths['thumbnail'].is_file():
            thumbnail = normalized.copy()
            thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            _save_webp_atomic(thumbnail, paths['thumbnail'], quality=76)

    return {key: str(value) for key, value in paths.items()}


def get_or_create_image_derivative(source, record_id, variant, original_path):
    if variant not in {'thumbnail', 'preview'}:
        raise ValueError('Variação de imagem inválida.')
    paths = derivative_paths(source, record_id)
    if not paths[variant].is_file():
        ensure_image_derivatives(source, record_id, original_path)
    return str(paths[variant])


def _cache_candidates():
    if not DRIVE_CACHE_ROOT.exists():
        return []
    candidates = []
    for path in DRIVE_CACHE_ROOT.iterdir():
        if not path.is_file() or path.name.startswith('.'):
            continue
        stat = path.stat()
        candidates.append({
            'path': path,
            'size': stat.st_size,
            'last_access': max(stat.st_atime, stat.st_mtime),
        })
    return candidates


def cleanup_drive_cache(now=None):
    """
    Expira originais após dois dias e aplica LRU ao alcançar 80% de 15 GB.
    O alvo após pressão é 70%, reduzindo ciclos repetidos de exclusão.
    """
    now = now or time.time()
    removed = []
    candidates = _cache_candidates()

    for item in list(candidates):
        if now - item['last_access'] <= CACHE_TTL_SECONDS:
            continue
        item['path'].unlink(missing_ok=True)
        removed.append(str(item['path']))
        candidates.remove(item)

    total = sum(item['size'] for item in candidates)
    high = int(CACHE_LIMIT_BYTES * CACHE_HIGH_WATERMARK)
    target = int(CACHE_LIMIT_BYTES * CACHE_TARGET_WATERMARK)
    if total >= high:
        for item in sorted(candidates, key=lambda value: value['last_access']):
            item['path'].unlink(missing_ok=True)
            total -= item['size']
            removed.append(str(item['path']))
            if total <= target:
                break
    return {'removed': removed, 'remaining_bytes': max(total, 0)}


def _etag_for_path(path):
    stat = Path(path).stat()
    payload = f'{stat.st_size}:{stat.st_mtime_ns}'.encode()
    return hashlib.sha256(payload).hexdigest()[:24]


def protected_local_file_response(
    path,
    *,
    mimetype=None,
    download_name=None,
    as_attachment=False,
    max_age=86400,
):
    """
    Autoriza no Flask e delega os bytes ao Nginx. Em ambientes sem X-Accel,
    usa send_file com suporte condicional e Range.
    """
    absolute_path = _absolute(path)
    if not absolute_path.is_file() or not _is_under(absolute_path, UPLOADS_ROOT):
        return Response('Arquivo não encontrado', status=404)

    set_delivery_permissions(absolute_path)
    mimetype = (
        mimetype
        or mimetypes.guess_type(download_name or absolute_path.name)[0]
        or 'application/octet-stream'
    )
    etag = _etag_for_path(absolute_path)
    cache_control = f'private, max-age={int(max_age)}, must-revalidate'

    if request.if_none_match.contains(etag):
        response = Response(status=304)
        response.set_etag(etag)
        response.headers['Cache-Control'] = cache_control
        return response

    use_x_accel = current_app.config.get(
        'USE_X_ACCEL_REDIRECT',
        os.getenv('USE_X_ACCEL_REDIRECT', 'false').lower()
        in {'1', 'true', 'yes', 'on'},
    )
    if use_x_accel:
        relative = absolute_path.relative_to(_absolute(UPLOADS_ROOT))
        internal_path = X_ACCEL_PREFIX + quote(relative.as_posix())
        response = Response(status=200, mimetype=mimetype)
        response.headers['X-Accel-Redirect'] = internal_path
    else:
        response = send_file(
            absolute_path,
            mimetype=mimetype,
            as_attachment=as_attachment,
            download_name=download_name,
            conditional=True,
            etag=etag,
            max_age=max_age,
        )

    response.set_etag(etag)
    response.headers['Cache-Control'] = cache_control
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    disposition = 'attachment' if as_attachment else 'inline'
    if download_name:
        response.headers['Content-Disposition'] = (
            f"{disposition}; filename*=UTF-8''{quote(download_name)}"
        )
    return response
