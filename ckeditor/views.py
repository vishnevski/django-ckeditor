import os
import re
from urlparse import urlparse, urlunparse
from hashlib import md5
from datetime import datetime

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext

try:
    from pytils.translit import translify
except ImportError:
    translify = lambda x: x

try:
    from PIL import Image, ImageOps
except ImportError:
    import Image
    import ImageOps

try:
    from django.views.decorators.csrf import csrf_exempt
except ImportError:
    # monkey patch this with a dummy decorator which just returns the
    # same function (for compatability with pre-1.1 Djangos)
    def csrf_exempt(fn):
        return fn


def generate_filename(filename):
    hash_line = str(filename.encode(u'utf-8') + datetime.now().strftime(u"%Y-%m-%d %H:%M:%S"))
    operation_hash = md5(hash_line).hexdigest()
    md5_line = operation_hash[:4]
    ext = filename.split('.')[-1]
    file_path = os.path.join(settings.MEDIA_ROOT, ext.lower(), md5_line[:2], md5_line[2:])
    if not os.path.exists(file_path):
        try:
            os.makedirs(file_path, mode=0755)
        except Exception, e:
            pass
    hash_filename = operation_hash + '.' + ext
    return os.path.join(file_path, hash_filename)


def get_media_url(path):
    return path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL[:-1])


@csrf_exempt
def upload(request):
    """
    Uploads a file and send back its URL to CKEditor.

    TODO:
        Validate uploads
    """
    # Get the uploaded file from request.
    upload = request.FILES['upload']

    # Open output file in which to store upload.
    upload_filename = generate_filename(translify(upload.name))
    url = get_media_url(upload_filename)
    out = open(upload_filename, 'wb+')

    # Iterate through chunks and write to destination.
    for chunk in upload.chunks():
        out.write(chunk)
    out.close()

    # Respond with Javascript sending ckeditor upload url.
    return HttpResponse("""
    <script type='text/javascript'>
        window.parent.CKEDITOR.tools.callFunction(%s, '%s');
    </script>""" % (request.GET['CKEditorFuncNum'], url))


def get_image_files(user=None):
    """
    Recursively walks all dirs under upload dir and generates a list of
    full paths for each file found.
    """
    # If a user is provided and CKEDITOR_RESTRICT_BY_USER is True,
    # limit images to user specific path, but not for superusers.
    if user and not user.is_superuser and getattr(settings, 'CKEDITOR_RESTRICT_BY_USER', False):
        user_path = user.username
    else:
        user_path = ''

    browse_path = os.path.join(settings.CKEDITOR_UPLOAD_PATH, user_path)

    for root, dirs, files in os.walk(browse_path):
        for filename in [os.path.join(root, x) for x in files]:
            # bypass for thumbs
            if os.path.splitext(filename)[0].endswith('_thumb'):
                continue
            yield filename


def get_image_browse_urls(user=None):
    """
    Recursively walks all dirs under upload dir and generates a list of
    thumbnail and full image URL's for each file found.
    """
    images = []
    for filename in get_image_files(user=user):
        images.append({
            'thumb': get_media_url(filename),
            'src': get_media_url(filename)
        })

    return images


def browse(request):
    context = RequestContext(request, {
        'images': get_image_browse_urls(request.user),
    })
    return render_to_response('browse.html', context)
