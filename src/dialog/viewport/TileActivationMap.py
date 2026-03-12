from qtpy.QtCore import QPointF, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QPainter, QPen
from qtpy.QtWidgets import QWidget


class TileActivationMap(QWidget):
    """Compact interactive grid map for toggling active tiles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = None
        self._interactive = True
        self._pending_active_tiles = set()
        self._tile_rects = {}
        self._drag_target_state = None
        self._drag_modified = False
        self._changed_callback = None
        self.setMinimumHeight(180)

    def sizeHint(self):
        return QSize(320, 220)

    def set_grid(self, grid):
        self.grid = grid
        self._pending_active_tiles = set(grid.active_tiles) if grid is not None else set()
        self._drag_target_state = None
        self._drag_modified = False
        self.update()

    def set_interactive(self, interactive):
        self._interactive = bool(interactive)
        self.update()

    def set_changed_callback(self, callback):
        self._changed_callback = callback

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())
        painter.setRenderHint(QPainter.Antialiasing, False)
        self._tile_rects = {}

        if self.grid is None:
            self._draw_message(painter, 'No grid selected.')
            return
        if self.grid.is_deferred_polygon_roi():
            self._draw_message(
                painter,
                'Deferred ROI\nOpen grid settings to materialize tiles.')
            return
        rows, cols = self.grid.size
        if rows <= 0 or cols <= 0:
            self._draw_message(painter, 'No tiles available.')
            return

        margin = 12
        avail_w = max(40, self.width() - 2 * margin)
        avail_h = max(40, self.height() - 2 * margin)
        tile_ratio = max(0.2, self.grid.tile_height_p() / max(1, self.grid.tile_width_p()))
        shift_ratio = min(0.45, abs(self.grid.row_shift) / max(1, self.grid.tile_width_p()))
        cell_w = min(avail_w / max(cols + shift_ratio, 1), avail_h / max(rows * tile_ratio, 1))
        cell_h = max(6.0, cell_w * tile_ratio)
        content_w = cell_w * (cols + shift_ratio)
        content_h = cell_h * rows
        origin_x = (self.width() - content_w) / 2
        origin_y = (self.height() - content_h) / 2
        row_shift = cell_w * shift_ratio

        active_fill = QColor(20, 123, 163)
        inactive_fill = QColor(224, 229, 233)
        disabled_fill = QColor(204, 204, 204)
        active_text = QColor(255, 255, 255)
        inactive_text = QColor(50, 50, 50)

        font = QFont(self.font())
        font_size = 8 if min(cell_w, cell_h) < 18 else 9
        font.setPointSize(font_size)
        painter.setFont(font)

        for row in range(rows):
            row_offset = row_shift if (row % 2 == 1 and self.grid.row_shift) else 0
            for col in range(cols):
                tile_index = row * cols + col
                x_pos = origin_x + row_offset + col * cell_w
                y_pos = origin_y + row * cell_h
                rect = QRectF(x_pos, y_pos, max(4.0, cell_w - 2), max(4.0, cell_h - 2))
                self._tile_rects[tile_index] = rect
                is_active = tile_index in self._pending_active_tiles
                fill = active_fill if is_active else inactive_fill
                if not self._interactive:
                    fill = disabled_fill if not is_active else QColor(140, 175, 190)
                painter.setPen(QPen(QColor(90, 98, 108), 1, Qt.SolidLine))
                painter.setBrush(fill)
                painter.drawRect(rect)
                if min(cell_w, cell_h) >= 16:
                    painter.setPen(active_text if is_active else inactive_text)
                    painter.drawText(rect, Qt.AlignCenter, str(tile_index))

    def _draw_message(self, painter, message):
        painter.setPen(QColor(90, 98, 108))
        painter.drawText(self.rect(), Qt.AlignCenter, message)

    def _tile_at(self, point):
        for tile_index, rect in self._tile_rects.items():
            if rect.contains(QPointF(point)):
                return tile_index
        return None

    def _apply_drag_to_tile(self, tile_index):
        if tile_index is None:
            return
        if self._drag_target_state:
            if tile_index not in self._pending_active_tiles:
                self._pending_active_tiles.add(tile_index)
                self._drag_modified = True
                self.update()
        else:
            if tile_index in self._pending_active_tiles:
                self._pending_active_tiles.remove(tile_index)
                self._drag_modified = True
                self.update()

    def mousePressEvent(self, event):
        if (not self._interactive
                or self.grid is None
                or self.grid.is_deferred_polygon_roi()
                or event.button() != Qt.LeftButton):
            return
        tile_index = self._tile_at(event.localPos())
        if tile_index is None:
            return
        self._drag_target_state = tile_index not in self._pending_active_tiles
        self._drag_modified = False
        self._apply_drag_to_tile(tile_index)

    def mouseMoveEvent(self, event):
        if self._drag_target_state is None:
            return
        self._apply_drag_to_tile(self._tile_at(event.localPos()))

    def mouseReleaseEvent(self, event):
        if self._drag_target_state is None:
            return
        self._drag_target_state = None
        if self.grid is None or not self._drag_modified:
            return
        self.grid.active_tiles = list(self._pending_active_tiles)
        self._drag_modified = False
        if self._changed_callback is not None:
            self._changed_callback()
