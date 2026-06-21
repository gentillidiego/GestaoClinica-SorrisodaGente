import io
import os
import threading
import time
from pathlib import Path

from flask import Flask
from PIL import Image, ImageChops

import services.protected_file_delivery_service as delivery


def make_app(use_x_accel=False):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test',
        TESTING=True,
        USE_X_ACCEL_REDIRECT=use_x_accel,
    )
    return app


def configure_roots(monkeypatch, tmp_path):
    uploads = tmp_path / 'uploads'
    monkeypatch.setattr(delivery, 'UPLOADS_ROOT', uploads)
    monkeypatch.setattr(delivery, 'DRIVE_CACHE_ROOT', uploads / 'cache' / 'gdrive')
    monkeypatch.setattr(
        delivery,
        'DERIVATIVE_ROOT',
        uploads / 'derived' / 'exam-files',
    )
    monkeypatch.setattr(delivery, 'DELIVERY_GID', os.getgid())
    return uploads


def test_image_derivatives_create_small_permanent_webp_files(tmp_path, monkeypatch):
    uploads = configure_roots(monkeypatch, tmp_path)
    original = uploads / 'staging' / 'large.jpg'
    original.parent.mkdir(parents=True)
    Image.new('RGB', (3200, 2400), color=(20, 80, 140)).save(original, 'JPEG')

    paths = delivery.ensure_image_derivatives('exam_image', 101, original)

    with Image.open(paths['thumbnail']) as thumb:
        assert thumb.format == 'WEBP'
        assert thumb.width <= 560
        assert thumb.height <= 560
    with Image.open(paths['preview']) as preview:
        assert preview.format == 'WEBP'
        assert preview.width <= 1800
        assert preview.height <= 1800
    assert Path(paths['thumbnail']).stat().st_size < original.stat().st_size


def test_image_preview_uses_lossless_webp_without_changing_resized_pixels(
    tmp_path,
    monkeypatch,
):
    uploads = configure_roots(monkeypatch, tmp_path)
    monkeypatch.setattr(delivery, 'DERIVATIVE_LOSSLESS', True)
    original = uploads / 'staging' / 'radiografia.png'
    original.parent.mkdir(parents=True)
    source = Image.effect_noise((2400, 1600), 80).convert('RGB')
    source.save(original, 'PNG')

    paths = delivery.ensure_image_derivatives('exam_image', 102, original)

    expected = source.copy()
    expected.thumbnail(delivery.PREVIEW_SIZE, Image.Resampling.LANCZOS)
    with Image.open(paths['preview']) as preview:
        actual = preview.convert('RGB')
        assert ImageChops.difference(actual, expected).getbbox() is None


def test_atomic_drive_cache_download_is_shared_between_concurrent_requests(
    tmp_path,
    monkeypatch,
):
    configure_roots(monkeypatch, tmp_path)
    downloads = []
    barrier = threading.Barrier(4)

    def fake_download(service, file_id, destination):
        downloads.append(file_id)
        time.sleep(0.08)
        Path(destination).write_bytes(b'cached-content')

    monkeypatch.setattr(delivery, 'download_file_to_path', fake_download)
    monkeypatch.setattr(delivery, 'cleanup_drive_cache', lambda: {})

    results = []

    def worker():
        barrier.wait()
        results.append(delivery.ensure_cached_drive_file(object(), 'drive-1'))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert downloads == ['drive-1']
    assert len(set(results)) == 1
    assert Path(results[0]).read_bytes() == b'cached-content'


def test_staged_original_is_promoted_to_recent_cache_without_second_download(
    tmp_path,
    monkeypatch,
):
    uploads = configure_roots(monkeypatch, tmp_path)
    staged = uploads / 'staging' / 'exam.jpg'
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b'original')
    monkeypatch.setattr(delivery, 'cleanup_drive_cache', lambda: {})

    cache_path = delivery.promote_staging_to_cache(staged, 'drive-new')

    assert Path(cache_path).read_bytes() == b'original'
    assert staged.exists()
    assert os.stat(cache_path).st_ino == os.stat(staged).st_ino


def test_cache_expires_after_two_days_and_uses_lru_watermark(tmp_path, monkeypatch):
    configure_roots(monkeypatch, tmp_path)
    monkeypatch.setattr(delivery, 'CACHE_TTL_SECONDS', 2 * 86400)
    monkeypatch.setattr(delivery, 'CACHE_LIMIT_BYTES', 100)
    monkeypatch.setattr(delivery, 'CACHE_HIGH_WATERMARK', 0.80)
    monkeypatch.setattr(delivery, 'CACHE_TARGET_WATERMARK', 0.70)
    delivery.DRIVE_CACHE_ROOT.mkdir(parents=True)

    expired = delivery.DRIVE_CACHE_ROOT / 'expired'
    oldest = delivery.DRIVE_CACHE_ROOT / 'oldest'
    newest = delivery.DRIVE_CACHE_ROOT / 'newest'
    expired.write_bytes(b'x' * 10)
    oldest.write_bytes(b'x' * 45)
    newest.write_bytes(b'x' * 45)
    now = time.time()
    os.utime(expired, (now - 3 * 86400, now - 3 * 86400))
    os.utime(oldest, (now - 100, now - 100))
    os.utime(newest, (now - 10, now - 10))

    result = delivery.cleanup_drive_cache(now=now)

    assert not expired.exists()
    assert not oldest.exists()
    assert newest.exists()
    assert result['remaining_bytes'] == 45


def test_x_accel_response_is_private_etagged_and_internal(tmp_path, monkeypatch):
    uploads = configure_roots(monkeypatch, tmp_path)
    file_path = uploads / 'cache' / 'gdrive' / 'drive-file'
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b'0123456789')
    app = make_app(use_x_accel=True)

    with app.test_request_context('/protected'):
        response = delivery.protected_local_file_response(
            file_path,
            mimetype='application/pdf',
            download_name='laudo.pdf',
        )

    assert response.status_code == 200
    assert response.headers['X-Accel-Redirect'].endswith('/cache/gdrive/drive-file')
    assert response.headers['Accept-Ranges'] == 'bytes'
    assert response.headers['Cache-Control'].startswith('private')
    assert response.headers['ETag']


def test_fallback_delivery_supports_pdf_range_requests(tmp_path, monkeypatch):
    uploads = configure_roots(monkeypatch, tmp_path)
    file_path = uploads / 'cache' / 'gdrive' / 'drive-pdf'
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b'0123456789')
    app = make_app(use_x_accel=False)

    with app.test_request_context(
        '/protected',
        headers={'Range': 'bytes=2-5'},
    ):
        response = delivery.protected_local_file_response(
            file_path,
            mimetype='application/pdf',
            download_name='laudo.pdf',
        )

    assert response.status_code == 206
    response.direct_passthrough = False
    assert response.get_data() == b'2345'
    assert response.headers['Content-Range'] == 'bytes 2-5/10'
