from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from dropwin import __version__
from dropwin.platform.windows import collect_wifi_diagnostics, get_wireless_adapters


class DiagnosticsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnostica Wi-Fi · DropWin")
        self.resize(760, 560)

        report = QPlainTextEdit()
        report.setReadOnly(True)
        report.setPlainText(collect_wifi_diagnostics())

        copy_button = QPushButton("Copia diagnostica")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(report.toPlainText())
        )
        close_button = QPushButton("Chiudi")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Report Windows in sola lettura. Non attiva AWDL e non modifica driver o impostazioni."
            )
        )
        layout.addWidget(report)
        layout.addWidget(copy_button)
        layout.addWidget(close_button)


class DropWinWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DropWin")
        self.setMinimumSize(560, 460)

        title = QLabel("DropWin")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Ricezione AirDrop per Windows")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status = QLabel(
            "Motore AirDrop non ancora disponibile\n"
            "Questa versione è uno scaffold di sviluppo."
        )
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.adapter_info = QLabel(self._adapter_summary())
        self.adapter_info.setWordWrap(True)
        self.adapter_info.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.diagnostics_button = QPushButton("Raccogli diagnostica Wi-Fi")
        self.diagnostics_button.clicked.connect(self._show_diagnostics)

        self.receive_button = QPushButton("Avvia ricezione")
        self.receive_button.setEnabled(False)
        self.receive_button.setToolTip(
            "La ricezione sarà abilitata quando un backend AWDL verificato sarà integrato."
        )
        footer = QLabel(f"Versione {__version__} · Prototipo, non ancora compatibile AirDrop")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        layout.addWidget(self.status)
        layout.addWidget(self.adapter_info)
        layout.addWidget(self.diagnostics_button)
        layout.addWidget(self.receive_button)
        layout.addStretch(1)
        layout.addWidget(footer)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
        self.setStyleSheet(
            """
            QMainWindow { background: #111827; color: #f9fafb; }
            QWidget { color: #f9fafb; font-size: 14px; }
            QLabel#title { font-size: 34px; font-weight: 700; }
            QPushButton {
                background: #2563eb; color: white; border: 0;
                border-radius: 9px; padding: 12px; font-weight: 600;
            }
            QPushButton:disabled { background: #374151; color: #9ca3af; }
            QPlainTextEdit {
                background: #0b1220; color: #e5e7eb;
                border: 1px solid #374151; border-radius: 6px;
            }
            """
        )

    def _show_diagnostics(self) -> None:
        dialog = DiagnosticsDialog(self)
        dialog.exec()

    @staticmethod
    def _adapter_summary() -> str:
        adapters = get_wireless_adapters()
        if not adapters:
            return "Schede Wi-Fi: nessun adattatore rilevato tramite inventario Windows."
        lines = ["Schede Wi-Fi rilevate (rilevamento informativo, non test AWDL):"]
        lines.extend(f"• {adapter.name}: {adapter.description}" for adapter in adapters)
        return "\n".join(lines)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DropWin")
    window = DropWinWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
