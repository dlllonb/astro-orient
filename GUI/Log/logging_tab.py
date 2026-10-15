from PySide6.QtCore import QSignalBlocker, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QStyle, QToolButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .fields import FIELDS


class LoggingTab(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.items = {}
        self.session_path = ""
        self._selection_locked = False
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(18)

        title = QLabel("Recording")
        title.setObjectName("panelTitle")
        root.addWidget(title)
        self.configuration = QWidget()
        config = QFormLayout(self.configuration)
        config.setContentsMargins(0, 0, 0, 0)
        config.setSpacing(12)
        destination_row = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.setReadOnly(True)
        self.destination.setPlaceholderText("No destination selected")
        self.browse = QToolButton()
        self.browse.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.browse.setToolTip("Choose recording folder")
        self.browse.clicked.connect(self._choose_folder)
        destination_row.addWidget(self.destination, 1)
        destination_row.addWidget(self.browse)
        config.addRow("Save location", destination_row)
        self.interval = QSpinBox()
        self.interval.setRange(1, 86400)
        self.interval.setSingleStep(1)
        self.interval.setValue(1)
        self.interval.setSuffix(" s")
        self.interval.setFixedWidth(150)
        config.addRow("Sample interval", self.interval)
        root.addWidget(self.configuration)

        content = QHBoxLayout()
        content.setSpacing(28)
        self.fields = QTreeWidget()
        self.fields.setHeaderLabel("Recorded fields")
        self.fields.setUniformRowHeights(True)
        self.fields.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.fields.setStyleSheet("QTreeWidget { background: white; } QTreeWidget::item { min-height: 26px; }")
        self.groups = {}
        for field in FIELDS:
            if field.group not in self.groups:
                group = QTreeWidgetItem(self.fields, [field.group])
                group.setFlags(group.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                group.setCheckState(0, Qt.CheckState.Unchecked)
                group.setToolTip(0, f"Select or clear all {field.group} fields")
                font = group.font(0)
                font.setBold(True)
                group.setFont(0, font)
                self.groups[field.group] = group
            item = QTreeWidgetItem(self.groups[field.group], [field.label])
            if field.unavailable:
                item.setDisabled(True)
                item.setToolTip(0, field.unavailable)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if field.default else Qt.CheckState.Unchecked)
            self.items[field.key] = item
        self.groups["Camera"].setToolTip(0, "Selecting camera data also saves images with frame timestamps once per logging interval.")
        self._refresh_group_checks()
        self.fields.itemChanged.connect(self._field_changed)
        self.fields.expandAll()
        content.addWidget(self.fields, 3)

        session = QVBoxLayout()
        session.setSpacing(16)
        self.toggle = QPushButton("Start log")
        self.toggle.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.toggle.clicked.connect(self._toggle_recording)
        session.addWidget(self.toggle)
        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        session.addWidget(self.status)
        counts = QFormLayout()
        self.rows = QLabel("0")
        self.images = QLabel("0")
        self.elapsed = QLabel("0.0 s")
        self.missed = QLabel("0")
        for name, widget in (("CSV rows", self.rows), ("Images saved", self.images), ("Elapsed", self.elapsed), ("Missed intervals", self.missed)):
            counts.addRow(name, widget)
        session.addLayout(counts)
        session.addWidget(QLabel("Session folder"))
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        session.addWidget(self.path)
        self.open_folder = QPushButton("Open folder")
        self.open_folder.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.open_folder.setEnabled(False)
        self.open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.session_path)))
        session.addWidget(self.open_folder)
        session.addStretch(1)
        content.addLayout(session, 2)
        root.addLayout(content, 1)
        self.controller.progress.connect(self._progress)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Recording destination", self.destination.text())
        if folder:
            self.destination.setText(folder)

    def _refresh_group_checks(self):
        # Disabled placeholders must not remove or control a category checkbox.
        with QSignalBlocker(self.fields):
            for group in self.groups.values():
                states = [group.child(i).checkState(0) for i in range(group.childCount())
                          if not group.child(i).isDisabled()]
                if all(state == Qt.CheckState.Checked for state in states):
                    state = Qt.CheckState.Checked
                elif any(state == Qt.CheckState.Checked for state in states):
                    state = Qt.CheckState.PartiallyChecked
                else:
                    state = Qt.CheckState.Unchecked
                group.setCheckState(0, state)

    def _field_changed(self, item, column):
        if self._selection_locked or column != 0:
            return
        if item.parent() is None:
            with QSignalBlocker(self.fields):
                checked = item.checkState(0) == Qt.CheckState.Checked
                for index in range(item.childCount()):
                    child = item.child(index)
                    if not child.isDisabled():
                        child.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._refresh_group_checks()

    def _lock_selection(self, locked):
        if locked == self._selection_locked:
            return
        self._selection_locked = locked
        with QSignalBlocker(self.fields):
            for item in (*self.groups.values(), *self.items.values()):
                if item.isDisabled():
                    continue
                flags = item.flags()
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable if locked
                              else flags | Qt.ItemFlag.ItemIsUserCheckable)
        self.fields.setToolTip("Field selection is fixed during recording." if locked else "")

    def _toggle_recording(self):
        if self.controller.running:
            self.controller.stop()
            return
        if not self.destination.text():
            self._choose_folder()
            if not self.destination.text():
                return
        keys = [field.key for field in FIELDS if not field.unavailable and self.items[field.key].checkState(0) == Qt.CheckState.Checked]
        try:
            self.controller.start(self.destination.text(), keys, self.interval.value())
        except (ValueError, RuntimeError, OSError) as exc:
            QMessageBox.warning(self, "Cannot start recording", str(exc))

    @Slot(dict)
    def _progress(self, event):
        state = event["state"]
        active = state != "finished"
        self.configuration.setEnabled(not active)
        self._lock_selection(active)
        self.toggle.setEnabled(state != "stopping")
        self.toggle.setText("Stop log" if active else "Start log")
        self.toggle.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop if active else QStyle.StandardPixmap.SP_MediaPlay))
        self.status.setText({"starting": "Starting...", "recording": "Recording", "stopping": "Finishing files...", "finished": "Stopped"}[state])
        if "path" in event:
            self.session_path = event["path"]
            self.path.setText(self.session_path)
            self.open_folder.setEnabled(bool(self.session_path))
        for key, label in (("rows", self.rows), ("images", self.images), ("missed", self.missed)):
            if key in event:
                label.setText(str(event[key]))
        if "elapsed" in event:
            self.elapsed.setText(f"{event['elapsed']:.1f} s")
        if event.get("error"):
            self.status.setText("Recording failed")
            QMessageBox.warning(self, "Recording failed", event["error"])
