import traceback

from PyQt5.QtWidgets import QMessageBox


def message(msg_type, information, details=None):
    msg = QMessageBox()

    if msg_type == "ERROR":
        msg.setIcon(QMessageBox.Critical)
    elif msg_type == "WARNING":
        msg.setIcon(QMessageBox.Warning)
    elif msg_type == "INFO":
        msg.setIcon(QMessageBox.Information)
    else:
        msg.setIcon(QMessageBox.NoIcon)

    info_text = msg_type + ": " + information
    msg.setText(info_text)
    if details is not None:
        msg.setDetailedText(details)

    msg.setWindowTitle(msg_type)
    msg.exec_()


def exception(exception):
    name = type(exception).__name__
    message("ERROR", "Raised exception \"" + name + "\"", traceback.format_exc())


def info(text, details=None):
    message("INFO", text, details)


def error(text, details=None):
    message("ERROR", text, details)


def warning(text, details=None):
    message("WARNING", text, details)

