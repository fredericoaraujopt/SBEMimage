import sys

from qtpy.QtWidgets import QApplication, QLabel

from klab_ui import KLABThemePolisher


APP = QApplication.instance()
if APP is None:
    APP = QApplication(sys.argv)


def test_polisher_ignores_deleted_root():
    polisher = KLABThemePolisher(APP)
    label = QLabel('temporary root')
    root_id = id(label)
    label.deleteLater()
    QApplication.processEvents()

    polisher._polish_root(label, root_id)
