"""KLAB-specific UI metric normalization.

The KLAB theme refreshes colors and borders, but many SBEMimage windows still
use fixed Qt geometries. This helper now prefers spacing/layout expansion over
font shrinking so KLAB text remains readable.
"""

import re

from qtpy.QtCore import QObject, QEvent, QTimer
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
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
    """Tightens spacing and grows layout-managed widgets before text is clipped."""

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
            root_growth_needed = 0
            for widget in widgets:
                if widget.width() <= 0:
                    continue
                overflow_width = self._overflow_width(widget)
                desired_compact = overflow_width > 0
                current_compact = bool(widget.property('klabCompact'))
                if desired_compact == current_compact:
                    pass
                else:
                    widget.setProperty('klabCompact', desired_compact)
                    self._repolish(widget)

                growth = self._expand_layout_widget(widget, overflow_width)
                root_growth_needed = max(root_growth_needed, growth)
            if root_growth_needed > 0:
                self._expand_dialog_width(root, root_growth_needed)
        finally:
            root.setProperty('_klab_polish_in_progress', False)

    def _needs_compact_metrics(self, widget):
        return self._overflow_width(widget) > 0

    def _overflow_width(self, widget):
        if isinstance(widget, QGroupBox):
            return self._overflow_pixels(
                widget, widget.title(), widget.width() - 22, extra_padding=8)
        if isinstance(widget, QLabel):
            if widget.pixmap() is not None or widget.movie() is not None:
                return 0
            if widget.wordWrap():
                return 0
            return self._overflow_pixels(
                widget, widget.text(), widget.contentsRect().width(),
                extra_padding=2)
        if isinstance(widget, QTabBar):
            return self._tabbar_overflow_pixels(widget)
        if isinstance(widget, (QCheckBox, QRadioButton)):
            return self._overflow_pixels(
                widget,
                widget.text(),
                widget.width() - 22,
                extra_padding=6)
        if isinstance(widget, (QPushButton, QToolButton)):
            available_width = widget.width() - 12
            if not widget.icon().isNull():
                available_width -= widget.iconSize().width() + 4
            return self._overflow_pixels(
                widget, widget.text(), available_width, extra_padding=6)
        if isinstance(widget, QComboBox):
            return self._overflow_pixels(
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
            return self._overflow_pixels(
                widget, text, widget.width() - 22, extra_padding=4)
        return 0

    def _tabbar_overflow_pixels(self, tabbar):
        font_metrics = tabbar.fontMetrics()
        overflow_pixels = 0
        for index in range(tabbar.count()):
            rect = tabbar.tabRect(index)
            if rect.width() <= 0:
                continue
            required = font_metrics.horizontalAdvance(tabbar.tabText(index)) + 14
            overflow_pixels = max(overflow_pixels, required - max(0, rect.width() - 2))
        return max(0, overflow_pixels)

    def _overflow_pixels(self, widget, text, available_width, extra_padding=0):
        plain_text = self._plain_text(text)
        if not plain_text:
            return 0
        available_width = max(0, int(available_width) - int(extra_padding))
        if available_width <= 0:
            return 1
        required_width = widget.fontMetrics().horizontalAdvance(plain_text)
        return max(0, required_width - available_width)

    @staticmethod
    def _is_layout_managed(widget):
        parent = widget.parentWidget()
        if parent is None:
            return False
        layout = parent.layout()
        if layout is None:
            return False
        return layout.indexOf(widget) != -1

    def _expand_layout_widget(self, widget, overflow_width):
        if overflow_width <= 0 or not self._is_layout_managed(widget):
            return 0
        desired_width = max(
            widget.minimumWidth(),
            widget.sizeHint().width(),
            widget.width() + int(overflow_width) + 12)
        if desired_width <= widget.minimumWidth():
            return 0
        widget.setMinimumWidth(desired_width)
        widget.updateGeometry()
        return max(0, desired_width - widget.width())

    @staticmethod
    def _expand_dialog_width(root, growth_width):
        if growth_width <= 0 or not isinstance(root, QDialog):
            return
        if root.layout() is None:
            return
        requested_growth = min(int(growth_width) + 24, 220)
        current_target = int(root.property('_klab_target_width') or root.width())
        desired_width = max(current_target, root.sizeHint().width(), root.width() + requested_growth)
        if desired_width <= current_target:
            return
        root.setProperty('_klab_target_width', desired_width)
        if root.minimumWidth() == root.maximumWidth() == root.width():
            root.setFixedWidth(desired_width)
        else:
            root.setMinimumWidth(max(root.minimumWidth(), desired_width))
            root.resize(max(root.width(), desired_width), root.height())

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
