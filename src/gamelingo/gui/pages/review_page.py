import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QTextEdit, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt

from gamelingo.translation.review import ReviewService
from gamelingo.gui.state import AppState

class ReviewPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.service = None
        self.current_unit_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Left side - List of units
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_refresh.clicked.connect(self.load_units)
        left_layout.addWidget(self.btn_refresh)
        
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.list_widget)
        
        # Right side - Editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.lbl_id = QLabel("ID: ")
        self.lbl_status = QLabel("Status: ")
        right_layout.addWidget(self.lbl_id)
        right_layout.addWidget(self.lbl_status)
        
        right_layout.addWidget(QLabel("Source Text:"))
        self.txt_source = QTextEdit()
        self.txt_source.setReadOnly(True)
        right_layout.addWidget(self.txt_source)
        
        right_layout.addWidget(QLabel("Translated Text:"))
        self.txt_target = QTextEdit()
        right_layout.addWidget(self.txt_target)
        
        self.lbl_validation = QLabel("")
        self.lbl_validation.setStyleSheet("color: red;")
        right_layout.addWidget(self.lbl_validation)
        
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save (Draft)")
        self.btn_save.clicked.connect(self.on_save)
        
        self.btn_approve = QPushButton("Approve")
        self.btn_approve.clicked.connect(self.on_approve)
        
        self.btn_reject = QPushButton("Reject")
        self.btn_reject.clicked.connect(self.on_reject)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_approve)
        btn_layout.addWidget(self.btn_reject)
        right_layout.addLayout(btn_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        self.set_editor_enabled(False)
        
    def refresh(self):
        if self.state.db:
            self.service = ReviewService(self.state.db)
            self.load_units()
            
    def load_units(self):
        if not self.service:
            return
            
        self.list_widget.clear()
        units = self.service.list_units_for_review("default", ["draft", "needs_review", "rejected", "failed"])
        
        for u in units:
            item = QListWidgetItem(f"[{u['status']}] {u['id']}")
            item.setData(Qt.UserRole, u['id'])
            self.list_widget.addItem(item)
            
        self.set_editor_enabled(False)
        self.current_unit_id = None
        
    def on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            self.set_editor_enabled(False)
            return
            
        unit_id = items[0].data(Qt.UserRole)
        self.current_unit_id = unit_id
        
        unit = self.service.get_unit(unit_id)
        if unit:
            self.lbl_id.setText(f"ID: {unit['id']}")
            self.lbl_status.setText(f"Status: {unit['status']}")
            self.txt_source.setPlainText(unit['source_text'])
            self.txt_target.setPlainText(unit.get('translated_text') or "")
            
            flags_text = ""
            if unit.get('quality_flags'):
                try:
                    flags = json.loads(unit['quality_flags'])
                    if flags:
                        flags_text = "\n".join([f"[{f.get('severity')}] {f.get('message')}" for f in flags])
                except Exception:
                    pass
            self.lbl_validation.setText(flags_text)
            
            self.set_editor_enabled(True)

    def set_editor_enabled(self, enabled):
        self.txt_target.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        self.btn_approve.setEnabled(enabled)
        self.btn_reject.setEnabled(enabled)

    def on_save(self):
        if not self.current_unit_id:
            return
        
        try:
            self.service.update_translation(self.current_unit_id, self.txt_target.toPlainText())
            self.on_selection_changed() # Reload details
            self.update_list_item_status()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
    def on_approve(self):
        if not self.current_unit_id:
            return
        
        try:
            self.service.approve(self.current_unit_id)
            self.on_selection_changed()
            self.update_list_item_status()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
    def on_reject(self):
        if not self.current_unit_id:
            return
            
        try:
            self.service.reject(self.current_unit_id, "")
            self.on_selection_changed()
            self.update_list_item_status()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
    def update_list_item_status(self):
        unit = self.service.get_unit(self.current_unit_id)
        if unit:
            items = self.list_widget.selectedItems()
            if items:
                items[0].setText(f"[{unit['status']}] {unit['id']}")
