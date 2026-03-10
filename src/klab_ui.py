"""KLAB-specific UI metric normalization.

The KLAB theme refreshes colors and borders, but many SBEMimage windows still
use fixed Qt geometries. This helper keeps KLAB-only widgets visually compact
enough to fit those native layouts without changing interaction behavior.
"""

import re

from qtpy.QtCore import QObject, QEvent, QTimer
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QGroupBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QTabBar,
    QToolButton,
    QWidget,
)


HTML_TAG_RE = re.compile(r'<[^>]+>')


class KLABThemePolisher(QObject):
    """Compacts only the KLAB widgets whose text would otherwise overflow."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._queued_roots = set()

    def install(self):
        self.app.installEventFilter(self)
        return self

    def eventFilter(self, obj, event):
        if not isinstance(obj, QWidget):
            return False
        if event.type() in (
                QEvent.Show,
                QEvent.Resize,
                QEvent.LayoutRequest,
                QEvent.FontChange):
            root = obj.window()
            if isinstance(root, QWidget) and root.isWindow():
                self._queue_root(root)
        return False

    def _queue_root(self, root):
        root_id = id(root)
        if root_id in self._queued_roots:
            return
        self._queued_roots.add(root_id)
        QTimer.singleShot(0, lambda root=root, root_id=root_id:
                          self._polish_root(root, root_id))

    def _polish_root(self, root, root_id):
        self._queued_roots.discard(root_id)
        if root is None or not isinstance(root, QWidget):
            return
        if root.property('_klab_polish_in_progress'):
            return
        root.setProperty('_klab_polish_in_progress', True)
        try:
            widgets = [root] + root.findChildren(QWidget)
            for widget in widgets:
                if widget.width() <= 0:
                    continue
                desired_compact = self._needs_compact_metrics(widget)
                current_compact = bool(widget.property('klabCompact'))
                if desired_compact == current_compact:
                    continue
                widget.setProperty('klabCompact', desired_compact)
                self._repolish(widget)
        finally:
            root.setProperty('_klab_polish_in_progress', False)

    def _needs_compact_metrics(self, widget):
        if isinstance(widget, QGroupBox):
            return self._text_overflows(
                widget, widget.title(), widget.width() - 22, extra_padding=8)
        if isinstance(widget, QLabel):
            if widget.pixmap() is not None or widget.movie() is not None:
                return False
            if widget.wordWrap():
                return False
            return self._text_overflows(
                widget, widget.text(), widget.contentsRect().width(),
                extra_padding=2)
        if isinstance(widget, QTabBar):
            return self._tabbar_overflows(widget)
        if isinstance(widget, (QCheckBox, QRadioButton)):
            return self._text_overflows(
                widget,
                widget.text(),
                widget.width() - 22,
                extra_padding=6)
        if isinstance(widget, (QPushButton, QToolButton)):
            available_width = widget.width() - 12
            if not widget.icon().isNull():
                available_width -= widget.iconSize().width() + 4
            return self._text_overflows(
                widget, widget.text(), available_width, extra_padding=6)
        if isinstance(widget, QComboBox):
            return self._text_overflows(
                widget,
                widget.currentText(),
                widget.width() - 24,
                extra_padding=6)
        if isinstance(widget, (QAbstractSpinBox, QDateTimeEdit)):
            text = ''
            line_edit = getattr(widget, 'lineEdit', lambda: None)()
            if line_edit is not None:
                text = line_edit.text() or line_edit.placeholderText()
            elif hasattr(widget, 'text'):
                text = widget.text()
            return self._text_overflows(
                widget, text, widget.width() - 22, extra_padding=4)
        return False

    def _tabbar_overflows(self, tabbar):
        font_metrics = tabbar.fontMetrics()
        for index in range(tabbar.count()):
            rect = tabbar.tabRect(index)
            if rect.width() <= 0:
                continue
            required = font_metrics.horizontalAdvance(tabbar.tabText(index)) + 14
            if required > rect.width() - 2:
                return True
        return False

    def _text_overflows(self, widget, text, available_width, extra_padding=0):
        plain_text = self._plain_text(text)
        if not plain_text:
            return False
        available_width = max(0, int(available_width) - int(extra_padding))
        if available_width <= 0:
            return True
        required_width = widget.fontMetrics().horizontalAdvance(plain_text)
        return required_width > available_width

    @staticmethod
    def _plain_text(text):
        if not text:
            return ''
        text = str(text).replace('&', '')
        return HTML_TAG_RE.sub('', text).strip()

    @staticmethod
    def _repolish(widget):
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.updateGeometry()
        widget.update()


def install_klab_theme_polisher(app):
    """Install KLAB-only event filtering on the QApplication."""
    polisher = KLABThemePolisher(app).install()
    app.klab_theme_polisher = polisher
    return polisher
