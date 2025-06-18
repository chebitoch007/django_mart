import os
import json
from urllib2 import urlopen
from contextlib import closing
from functools import wraps


def load_config():
    with closing(urlopen(os.environ['CONFIG_URL'])) as fh:
        return json.load(fh)


def view_decorator(view):
    """
    Prepends a loaded cfg argument to the view call
    """
    @wraps(view)
    def inner(request, *args, **kwargs):
        cfg = load_config()
        return view(cfg, request, *args, **kwargs)
    return inner


def view_undecorator(view):
    """
    Removes the cfg argument from the view for
    use with legacy views
    """
    @wraps(view)
    def inner(cfg, request, *args, **kwargs):
        return view(request, *args, **kwargs)
    return inner
