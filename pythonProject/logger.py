import logging

def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Console Handler: Ekrana yazdırmak için
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Formatter: Logların formatını belirliyoruz
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Handler'ları Logger'a ekliyoruz
    logger.addHandler(console_handler)

    return logger
