import os
from pathlib import Path

from flask import abort, send_file
from werkzeug.utils import safe_join


SENSITIVE_CACHE_HEADERS = {
    'Cache-Control': 'no-store, no-cache, must-revalidate, private, max-age=0',
    'Pragma': 'no-cache',
    'Expires': '0',
    'X-Content-Type-Options': 'nosniff',
}


def sensitive_file_response(path, mimetype=None, as_attachment=False, download_name=None):
    response = send_file(
        os.path.abspath(path),
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=download_name,
    )
    response.headers.update(SENSITIVE_CACHE_HEADERS)
    return response


def safe_file_in_directory(directory, filename):
    if not filename or Path(filename).name != filename:
        abort(404)
    path = safe_join(directory, filename)
    if not path or not os.path.isfile(path):
        abort(404)
    return path
