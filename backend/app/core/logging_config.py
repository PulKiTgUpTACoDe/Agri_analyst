import logging, sys

def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    root.addHandler(handler)
    for name in ("httpx", "httpcore", "langchain", "langsmith", "google"):
        logging.getLogger(name).setLevel(logging.WARNING)
