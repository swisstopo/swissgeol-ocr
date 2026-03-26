import logging

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d %(levelname)8s %(module)15s - %(funcName)-20s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
