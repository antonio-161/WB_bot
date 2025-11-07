import logging
from pathlib import Path

# Создаём директорию, если её нет
Path("logs").mkdir(exist_ok=True)

# Логгер для challenge
challenge_logger = logging.getLogger("challenge_tracker")
challenge_handler = logging.FileHandler("challenge_log.txt", encoding="utf-8")
challenge_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
challenge_logger.addHandler(challenge_handler)
challenge_logger.setLevel(logging.INFO)

# Логгер для errors
error_logger = logging.getLogger("error_tracker")
error_handler = logging.FileHandler("error_log.txt", encoding="utf-8")
error_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.INFO)
