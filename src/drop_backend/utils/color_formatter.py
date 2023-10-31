import logging


class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[0;36m',  # Cyan
        'INFO': '\033[0;37m',   # White
        'WARNING': '\033[1;33m',  # Yellow
        'ERROR': '\033[1;31m',  # Red
        'CRITICAL': '\033[1;41m'  # Red background
    }

    RESET = '\033[0m'

    def format(self, record):
        log_message = super().format(record)
        return f"{self.COLORS.get(record.levelname, self.RESET)}{log_message}{self.RESET}"
