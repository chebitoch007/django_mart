import os

def enabled(cfg, flag):
    if flag in os.environ:
        return os.environ.get(flag, "False") == "True"
    else:
        return cfg.get(flag, False)
