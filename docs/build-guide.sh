#!/bin/sh
# Regenerate the Accounting user guide PDF from its HTML source.
# Uses the Chameleon PySide6 venv's QtWebEngine (Chromium/Skia) print-to-PDF —
# LibreOffice headless on this machine currently emits text-less PDFs.
set -e
cd "$(dirname "$0")"
VENV=/aufs/devbase/pyside6-venv/bin/python
SRC=Chameleon_Accounting_User_Guide.src.html
OUT=Chameleon_Accounting_User_Guide.pdf
DISPLAY=:0 QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" \
  "$VENV" - "$SRC" "$OUT" <<'PY'
import sys, os
from PySide6.QtCore import QUrl, QMarginsF, QCoreApplication, Qt, QTimer
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)
src, out = sys.argv[1], sys.argv[2]
app = QApplication([]); view = QWebEngineView(); st = {"ok": False}
def on_load(ok):
    if not ok: app.quit(); return
    view.page().printToPdf(os.path.abspath(out),
        QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Orientation.Portrait,
                    QMarginsF(10, 10, 10, 10)))
def on_pdf(_p, ok): st["ok"] = bool(ok); app.quit()
view.loadFinished.connect(on_load)
view.page().pdfPrintingFinished.connect(on_pdf)
view.load(QUrl.fromLocalFile(os.path.abspath(src)))
QTimer.singleShot(45000, app.quit); app.exec()
sys.exit(0 if st["ok"] else 1)
PY
chmod 644 "$OUT"
echo "built $OUT"
