import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QFrame,
    QGroupBox, QComboBox, QCheckBox, QDialog, QLineEdit, QFormLayout, QRadioButton,
    QButtonGroup, QListWidget, QInputDialog, QMenu
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from datetime import datetime
import pandas as pd
import logging
import webbrowser
import os

from history_manager import HistoryManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CustomColumnDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加自定义字段")
        self.setFixedSize(400, 300)
        layout = QFormLayout(self)

        # Column name
        self.name_edit = QLineEdit()
        layout.addRow("字段名称:", self.name_edit)

        # Column type
        self.type_group = QButtonGroup(self)
        self.numeric_radio = QRadioButton("数字字段")
        self.enum_radio = QRadioButton("单选枚举值")
        self.multi_radio = QRadioButton("多选枚举值")
        self.type_group.addButton(self.numeric_radio)
        self.type_group.addButton(self.enum_radio)
        self.type_group.addButton(self.multi_radio)
        self.numeric_radio.setChecked(True)
        layout.addRow("字段类型:", self.numeric_radio)
        layout.addRow("", self.enum_radio)
        layout.addRow("", self.multi_radio)

        # Enum values input
        self.enum_list = QListWidget()
        self.enum_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addRow("枚举值 (多选):", self.enum_list)
        self.add_enum_btn = QPushButton("添加枚举值")
        self.add_enum_btn.clicked.connect(self.add_enum_value)
        layout.addRow("", self.add_enum_btn)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addRow(button_layout)

    def add_enum_value(self):
        value, ok = QInputDialog.getText(self, "添加枚举值", "请输入枚举值:")
        if ok and value.strip():
            self.enum_list.addItem(value.strip())

    def get_column_definition(self):
        name = self.name_edit.text().strip()
        if not name:
            return None
        if self.numeric_radio.isChecked():
            column_type = "numeric"
        elif self.enum_radio.isChecked():
            column_type = "enum"
        else:
            column_type = "multi"
        enum_values = [self.enum_list.item(i).text() for i in range(self.enum_list.count())] if column_type in ["enum", "multi"] else []
        return {"name": name, "type": column_type, "enum_values": enum_values}

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Label Tool v1.0")
        self.resize(1200, 750)

        self.history_manager = HistoryManager()
        self.jama_items = ["作者身份", "信息来源", "披露声明", "时效性"]
        self.gqs_items = ["差(1)", "一般(2)", "中等(3)", "良好(4)", "优秀(5)"]
        self.discern_items = [
            "视频目的清晰且简洁",
            "信息来源可靠且明确提及",
            "内容基于可靠证据或研究",
            "提及不同的治疗或管理选项",
            "披露利益冲突或资助来源"
        ]
        self.custom_columns = []  # Store custom column definitions
        self.current_meta = None
        self.current_data = None
        self.current_jama = None
        self.current_gqs = None
        self.current_discern = None
        self.current_custom_data = None  # Store custom column data
        self.sort_column = -1
        self.sort_order = Qt.AscendingOrder

        self.init_ui()
        self.load_history()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top frame (Settings)
        top_frame = QGroupBox("设置")
        top_layout = QHBoxLayout(top_frame)
        top_layout.setSpacing(5)
        top_layout.setContentsMargins(5, 5, 5, 5)

        self.import_btn = QPushButton("导入文件")
        self.import_btn.setMaximumHeight(30)
        self.import_btn.clicked.connect(self.import_file)
        top_layout.addWidget(self.import_btn)

        self.add_field_btn = QPushButton("新增字段")
        self.add_field_btn.setMaximumHeight(30)
        self.add_field_btn.clicked.connect(self.add_custom_column)
        top_layout.addWidget(self.add_field_btn)

        self.delete_field_btn = QPushButton("删除字段")
        self.delete_field_btn.setMaximumHeight(30)
        self.delete_field_btn.clicked.connect(self.delete_custom_column)
        top_layout.addWidget(self.delete_field_btn)

        delete_btn = QPushButton("删除历史记录")
        delete_btn.setMaximumHeight(30)
        delete_btn.clicked.connect(self.delete_selected_history)
        top_layout.addWidget(delete_btn)

        save_btn = QPushButton("保存记录")
        save_btn.setMaximumHeight(30)
        save_btn.clicked.connect(self.save_records)
        top_layout.addWidget(save_btn)

        export_btn = QPushButton("导出数据")
        export_btn.setMaximumHeight(30)
        export_btn.clicked.connect(self.export_data)
        top_layout.addWidget(export_btn)

        top_layout.addStretch()
        top_frame.setMaximumHeight(50)
        main_layout.addWidget(top_frame)

        self.status_label = QLabel("等待操作...")
        self.status_label.setMinimumHeight(60)
        self.status_label.setMaximumHeight(60)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFrameStyle(QFrame.Box | QFrame.Plain)
        main_layout.addWidget(self.status_label)

        # History tree
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["导入时间", "文件名", "数据量"])
        self.history_tree.header().setSectionResizeMode(QHeaderView.Interactive)
        self.history_tree.setColumnWidth(0, 200)
        self.history_tree.setColumnWidth(1, 300)
        self.history_tree.setColumnWidth(2, 80)
        self.history_tree.setFixedHeight(150)
        self.history_tree.itemSelectionChanged.connect(self.on_history_select)
        main_layout.addWidget(self.history_tree)

        # Data table
        self.data_table = QTableWidget()
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.update_table_columns()
        self.data_table.cellClicked.connect(self.on_data_click)
        self.data_table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.data_table.horizontalHeader().setSortIndicatorShown(True)
        main_layout.addWidget(self.data_table)

    def update_table_columns(self):
        base_columns = [
            "标题", "发布时间", "作者", "点赞数", "评论数", "分享数", "收藏数",
            "认证状态", "查看", "视频时长（秒）", "JAMA评分", "GQS评分", "DISCERN评分"
        ]
        custom_column_names = [col["name"] for col in self.custom_columns]
        all_columns = base_columns + custom_column_names
        self.data_table.setColumnCount(len(all_columns))
        self.data_table.setHorizontalHeaderLabels(all_columns)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # Calculate column widths
        font = self.data_table.font()
        font_metrics = QFontMetrics(font)
        min_width = 80  # Minimum width for columns
        base_column_widths = [300, 160, 140, 100, 100, 100, 100, 160, 80, 120, 480, 160, 1000]  # Default widths
        custom_column_widths = []

        for col_def in self.custom_columns:
            col_width = min_width
            if col_def["type"] == "numeric":
                col_width = max(col_width, font_metrics.width(col_def["name"]) + 20)
            elif col_def["type"] == "enum":
                max_option_width = max([font_metrics.width(opt) for opt in col_def["enum_values"]] + [font_metrics.width("未选择")])
                col_width = max(col_width, max_option_width + 40)  # Extra padding for combo box
            else:  # multi
                # Calculate width needed for all checkboxes + score label
                checkbox_width = sum(font_metrics.width(opt) + 30 for opt in col_def["enum_values"])  # 30 for checkbox size
                score_width = font_metrics.width(f"({len(col_def['enum_values'])}/{len(col_def['enum_values'])})") + 20
                col_width = max(col_width, checkbox_width + score_width + 20)  # Extra padding
            custom_column_widths.append(col_width)

        column_widths = base_column_widths + custom_column_widths
        for i, width in enumerate(column_widths):
            self.data_table.setColumnWidth(i, width)

    def add_custom_column(self):
        dialog = CustomColumnDialog(self)
        if dialog.exec_():
            column_def = dialog.get_column_definition()
            if column_def:
                if column_def["name"] in [col["name"] for col in self.custom_columns]:
                    QMessageBox.warning(self, "警告", "字段名称已存在！")
                    return
                self.custom_columns.append(column_def)
                self.update_table_columns()
                if self.current_data is not None:
                    # Initialize with empty set for multi-select or empty string for others
                    initial_value = set() if column_def["type"] == "multi" else ""
                    self.current_custom_data[column_def["name"]] = [initial_value for _ in range(len(self.current_data))]
                    self.load_data_table(
                        self.current_data, self.current_jama, self.current_gqs,
                        self.current_discern, self.current_custom_data
                    )
                self.history_manager.save_custom_columns(self.current_meta, self.custom_columns)
                QMessageBox.information(self, "提示", f"已添加字段：{column_def['name']}")

    def delete_custom_column(self):
        if not self.custom_columns:
            QMessageBox.warning(self, "警告", "没有可删除的自定义字段！")
            return
        
        # Create a dialog to select column to delete
        dialog = QDialog(self)
        dialog.setWindowTitle("删除自定义字段")
        layout = QVBoxLayout(dialog)
        
        combo = QComboBox()
        combo.addItems([col["name"] for col in self.custom_columns])
        layout.addWidget(QLabel("选择要删除的字段:"))
        layout.addWidget(combo)
        
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        def on_ok():
            col_name = combo.currentText()
            if col_name:
                reply = QMessageBox.question(
                    self, "确认删除", f"确定要删除字段 '{col_name}' 吗？此操作不可恢复！",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.custom_columns = [col for col in self.custom_columns if col["name"] != col_name]
                    if self.current_custom_data and col_name in self.current_custom_data:
                        del self.current_custom_data[col_name]
                    if self.current_data is not None and col_name in self.current_data.columns:
                        self.current_data.drop(columns=[col_name], inplace=True)
                    self.update_table_columns()
                    self.history_manager.save_custom_columns(self.current_meta, self.custom_columns)
                    if self.current_data is not None:
                        self.load_data_table(
                            self.current_data, self.current_jama, self.current_gqs,
                            self.current_discern, self.current_custom_data
                        )
                    QMessageBox.information(self, "提示", f"已删除字段：{col_name}")
                    dialog.accept()
        
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec_()

    def import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "支持的文件 (*.csv *.xlsx *.xls *.txt);;CSV文件 (*.csv);;Excel文件 (*.xlsx *.xls);;文本文件 (*.txt);;所有文件 (*)"
        )
        if not file_path:
            return

        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, encoding="utf-8-sig")
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            elif file_path.endswith('.txt'):
                df = pd.read_csv(file_path, sep='\t', encoding="utf-8")
            else:
                raise ValueError("不支持的文件格式")

            expected_columns = [
                "title", "publish_time", "author_name", "like_count", "comment_count",
                "share_count", "collect_count", "video_url", "danmaku_count", "duration",
                "video_id", "play_count", "author_official_role", "is_verified"
            ]
            for col in expected_columns:
                if col not in df.columns:
                    if col in ["like_count", "comment_count", "share_count", "collect_count",
                               "danmaku_count", "play_count", "author_official_role", "is_verified"]:
                        df[col] = 0
                    else:
                        df[col] = ""
            filename = os.path.basename(file_path)
            self.history_manager.add_history(filename, df.to_dict('records'), self.custom_columns)
            self.load_history()
            self.status_label.setText(f"导入完成，文件：{filename}，数据量：{len(df)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{str(e)}")
            self.status_label.setText("等待操作...")

    def export_data(self):
        if self.current_data is None or self.current_data.empty or self.current_meta is None:
            QMessageBox.warning(self, "警告", "请先选择历史数据")
            return

        export_df = self.current_data.copy()
        export_df['jama_details'] = [', '.join(j) if j else '' for j in self.current_jama or [[]] * len(export_df)]
        export_df['discern_details'] = [', '.join(d) if d else '' for d in self.current_discern or [[]] * len(export_df)]
        for col_name in self.current_custom_data or {}:
            # Convert sets to comma-separated strings for multi-select columns
            col_def = next((col for col in self.custom_columns if col["name"] == col_name), None)
            if col_def and col_def["type"] == "multi":
                export_df[col_name] = [', '.join(val) if isinstance(val, set) else val for val in self.current_custom_data[col_name]]
            else:
                export_df[col_name] = self.current_custom_data[col_name]

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        default_filename = f"{self.current_meta['filename']}_{timestamp}.csv"
        file_path, _ = QFileDialog.getSaveFileName(self, "保存数据", default_filename, "CSV文件 (*.csv)")
        if file_path:
            try:
                export_df.to_csv(file_path, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "提示", f"数据成功导出到 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出数据失败：{str(e)}")

    def on_header_clicked(self, logicalIndex):
        if logicalIndex == 8:  # Skip "查看" column
            return
        if self.current_data is None or self.current_data.empty:
            return

        if self.sort_column == logicalIndex:
            self.sort_order = Qt.DescendingOrder if self.sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self.sort_order = Qt.AscendingOrder
        self.sort_column = logicalIndex

        header = self.data_table.horizontalHeaderItem(logicalIndex).text()
        column_map = {
            "标题": "title",
            "发布时间": "publish_time",
            "作者": "author_name",
            "点赞数": "like_count",
            "评论数": "comment_count",
            "分享数": "share_count",
            "收藏数": "collect_count",
            "视频时长（秒）": "duration",
            "认证状态": "is_verified",
            "JAMA评分": "jama_score",
            "GQS评分": "gqs_score",
            "DISCERN评分": "discern_score"
        }
        column_map.update({col["name"]: col["name"] for col in self.custom_columns})
        column = column_map.get(header)

        if column and (column in self.current_data.columns or column in self.current_custom_data):
            try:
                if column == "publish_time":
                    self.current_data["publish_time"] = pd.to_datetime(self.current_data["publish_time"], errors='coerce')
                elif column == "duration" or any(col["name"] == column and col["type"] == "numeric" for col in self.custom_columns):
                    if column in self.current_data.columns:
                        self.current_data[column] = pd.to_numeric(self.current_data[column], errors='coerce')
                    else:
                        self.current_custom_data[column] = pd.to_numeric(self.current_custom_data[column], errors='coerce')
                indices = (self.current_data if column in self.current_data.columns else pd.Series(self.current_custom_data[column])).sort_values(
                    ascending=(self.sort_order == Qt.AscendingOrder),
                    na_position='last'
                ).index.tolist()
                self.current_data = self.current_data.iloc[indices].reset_index(drop=True)
                self.current_jama = [self.current_jama[i] for i in indices]
                self.current_gqs = [self.current_gqs[i] for i in indices]
                self.current_discern = [self.current_discern[i] for i in indices]
                if self.current_custom_data:
                    for col in self.current_custom_data:
                        self.current_custom_data[col] = [self.current_custom_data[col][i] for i in indices]
                self.load_data_table(
                    self.current_data, self.current_jama, self.current_gqs,
                    self.current_discern, self.current_custom_data
                )
                self.data_table.horizontalHeader().setSortIndicator(logicalIndex, self.sort_order)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"排序失败：{str(e)}")

    def on_history_select(self):
        selected_items = self.history_tree.selectedItems()
        if not selected_items:
            return
        item = selected_items[0]
        idx = self.history_tree.indexOfTopLevelItem(item)
        metas = self.history_manager.get_history()
        meta = metas[idx]

        data_return = self.history_manager.get_data(meta)
        df = data_return[0]
        jama = data_return[1] if len(data_return) > 1 else None
        gqs = data_return[2] if len(data_return) > 2 else None
        discern = data_return[3] if len(data_return) > 3 else None
        custom_data = data_return[4] if len(data_return) > 4 else None
        self.custom_columns = meta.get("custom_columns", [])

        if jama is None or not isinstance(jama, list) or not all(isinstance(s, set) for s in jama):
            jama = [set() for _ in range(len(df))]
        if gqs is None or not isinstance(gqs, list) or not all(isinstance(s, int) for s in gqs):
            gqs = [1 for _ in range(len(df))]
        if discern is None or not isinstance(discern, list) or not all(isinstance(s, set) for s in discern):
            discern = [set() for _ in range(len(df))]
        if custom_data is None:
            custom_data = {col["name"]: [set() if col["type"] == "multi" else "" for _ in range(len(df))] for col in self.custom_columns}

        self.current_meta = meta
        self.current_data = df
        self.current_jama = jama
        self.current_gqs = gqs
        self.current_discern = discern
        self.current_custom_data = custom_data

        if self.current_data is not None:
            self.current_data['jama_score'] = [len(j) for j in self.current_jama]
            self.current_data['gqs_score'] = self.current_gqs
            self.current_data['discern_score'] = [len(d) for d in self.current_discern]
            for col in self.current_custom_data:
                self.current_data[col] = self.current_custom_data[col]

        self.update_table_columns()
        self.load_data_table(df, jama, gqs, discern, custom_data)

    def load_history(self):
        self.history_tree.clear()
        metas = self.history_manager.get_history()
        for meta in metas:
            try:
                ts_fmt = datetime.strptime(meta["timestamp"], "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except:
                ts_fmt = meta.get("timestamp", "")
            item = QTreeWidgetItem([
                ts_fmt,
                meta["filename"],
                str(meta["count"])
            ])
            self.history_tree.addTopLevelItem(item)

    def load_data_table(self, df, jama, gqs, discern, custom_data=None):
        self.data_table.setRowCount(len(df))
        self.jama_checkboxes = []
        self.discern_checkboxes = []
        self.custom_widgets = {col["name"]: [] for col in self.custom_columns}
        for i, row in df.iterrows():
            selected_jama_items = jama[i] if i < len(jama) else set()
            jama_score = len(selected_jama_items)
            selected_discern_items = discern[i] if i < len(discern) else set()
            discern_score = len(selected_discern_items)

            self.data_table.setItem(i, 0, QTableWidgetItem(str(row.get("title", ""))))
            self.data_table.setItem(i, 1, QTableWidgetItem(str(row.get("publish_time", ""))))
            self.data_table.setItem(i, 2, QTableWidgetItem(str(row.get("author_name", ""))))
            self.data_table.setItem(i, 3, QTableWidgetItem(str(int(row.get("like_count", 0)) if not pd.isna(row.get("like_count")) else 0)))
            self.data_table.setItem(i, 4, QTableWidgetItem(str(int(row.get("comment_count", 0)) if not pd.isna(row.get("comment_count")) else 0)))
            self.data_table.setItem(i, 5, QTableWidgetItem(str(int(row.get("share_count", 0)) if not pd.isna(row.get("share_count")) else 0)))
            self.data_table.setItem(i, 6, QTableWidgetItem(str(int(row.get("collect_count", 0)) if not pd.isna(row.get("collect_count")) else 0)))
            self.data_table.setItem(i, 7, QTableWidgetItem(str(row.get("is_verified", ""))))
            self.data_table.setItem(i, 8, QTableWidgetItem("查看"))
            self.data_table.setItem(i, 9, QTableWidgetItem(str(row.get("duration", ""))))

            # JAMA annotation
            jama_widget = QWidget()
            jama_layout = QHBoxLayout(jama_widget)
            jama_layout.setContentsMargins(0, 0, 0, 0)
            jama_layout.setSpacing(5)
            row_jama_checkboxes = {}
            for item in self.jama_items:
                cb = QCheckBox(item)
                cb.setChecked(item in selected_jama_items)
                cb.stateChanged.connect(lambda state, r=i, it=item: self.update_jama(r, it, state))
                jama_layout.addWidget(cb)
                row_jama_checkboxes[item] = cb
            jama_score_label = QLabel(f"({jama_score}/4)")
            jama_layout.addWidget(jama_score_label)
            jama_layout.addStretch()
            self.data_table.setCellWidget(i, 10, jama_widget)
            self.jama_checkboxes.append(row_jama_checkboxes)

            # GQS annotation
            gqs_widget = QWidget()
            gqs_layout = QHBoxLayout(gqs_widget)
            gqs_layout.setContentsMargins(0, 0, 0, 0)
            gqs_layout.setSpacing(5)
            gqs_combo = QComboBox()
            gqs_combo.addItems(self.gqs_items)
            current_gqs_score = gqs[i] if i < len(gqs) else 1
            if current_gqs_score > 0:
                gqs_combo.setCurrentIndex(current_gqs_score - 1)
            gqs_combo.currentIndexChanged.connect(lambda idx, r=i: self.update_gqs(r, idx + 1))
            gqs_layout.addWidget(gqs_combo)
            gqs_score_label = QLabel(f"({gqs_combo.currentIndex() + 1}/5)")
            gqs_layout.addWidget(gqs_score_label)
            gqs_layout.addStretch()
            self.data_table.setCellWidget(i, 11, gqs_widget)

            # DISCERN annotation
            discern_widget = QWidget()
            discern_layout = QHBoxLayout(discern_widget)
            discern_layout.setContentsMargins(0, 0, 0, 0)
            discern_layout.setSpacing(5)
            row_discern_checkboxes = {}
            for item in self.discern_items:
                cb = QCheckBox(item)
                cb.setChecked(item in selected_discern_items)
                cb.stateChanged.connect(lambda state, r=i, it=item: self.update_discern(r, it, state))
                discern_layout.addWidget(cb)
                row_discern_checkboxes[item] = cb
            discern_score_label = QLabel(f"({discern_score}/5)")
            discern_layout.addWidget(discern_score_label)
            discern_layout.addStretch()
            self.data_table.setCellWidget(i, 12, discern_widget)
            self.discern_checkboxes.append(row_discern_checkboxes)

            # Custom columns
            for col_idx, col_def in enumerate(self.custom_columns, 13):
                col_name = col_def["name"]
                col_type = col_def["type"]
                current_value = custom_data.get(col_name, [set() if col_type == "multi" else "" for _ in range(len(df))])[i]
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(5)
                if col_type == "numeric":
                    line_edit = QLineEdit()
                    line_edit.setText(str(current_value))
                    line_edit.textChanged.connect(lambda text, r=i, cn=col_name: self.update_custom_data(r, cn, text))
                    layout.addWidget(line_edit)
                    layout.addStretch()
                elif col_type == "enum":
                    combo = QComboBox()
                    combo.addItems(["未选择"] + col_def["enum_values"])
                    combo.setCurrentText(str(current_value) if current_value else "未选择")
                    combo.currentTextChanged.connect(lambda text, r=i, cn=col_name: self.update_custom_data(r, cn, text))
                    layout.addWidget(combo)
                    layout.addStretch()
                else:  # multi
                    multi_widget = QWidget()
                    multi_layout = QHBoxLayout(multi_widget)
                    multi_layout.setContentsMargins(0, 0, 0, 0)
                    multi_layout.setSpacing(5)
                    row_multi_checkboxes = {}
                    for item in col_def["enum_values"]:
                        cb = QCheckBox(item)
                        cb.setChecked(item in current_value)
                        cb.stateChanged.connect(lambda state, r=i, cn=col_name, it=item: self.update_custom_multi(r, cn, it, state))
                        multi_layout.addWidget(cb)
                        row_multi_checkboxes[item] = cb
                    score_label = QLabel(f"({len(current_value)}/{len(col_def['enum_values'])})")
                    multi_layout.addWidget(score_label)
                    multi_layout.addStretch()
                    layout.addWidget(multi_widget)
                    self.custom_widgets[col_name].append(row_multi_checkboxes)
                self.data_table.setCellWidget(i, col_idx, widget)
                if col_type != "multi":
                    self.custom_widgets[col_name].append(widget)

    def update_jama(self, row, item, state):
        if not self.current_jama or row >= len(self.current_jama):
            return
        if not isinstance(self.current_jama[row], set):
            self.current_jama[row] = set()
        if state == Qt.Checked:
            self.current_jama[row].add(item)
        else:
            self.current_jama[row].discard(item)
        score = len(self.current_jama[row])
        if 0 <= row < self.data_table.rowCount():
            jama_widget = self.data_table.cellWidget(row, 10)
            if jama_widget and jama_widget.layout():
                score_label = jama_widget.layout().itemAt(jama_widget.layout().count() - 1).widget()
                if score_label:
                    score_label.setText(f"({score}/4)")
        self.current_data['jama_score'] = [len(j) for j in self.current_jama]

    def update_gqs(self, row, score):
        if not self.current_gqs or row >= len(self.current_gqs):
            return
        self.current_gqs[row] = score
        if 0 <= row < self.data_table.rowCount():
            gqs_widget = self.data_table.cellWidget(row, 11)
            if gqs_widget and gqs_widget.layout():
                score_label = gqs_widget.layout().itemAt(1).widget()
                if score_label:
                    score_label.setText(f"({score}/5)")
        self.current_data['gqs_score'] = self.current_gqs

    def update_discern(self, row, item, state):
        if not self.current_discern or row >= len(self.current_discern):
            return
        if not isinstance(self.current_discern[row], set):
            self.current_discern[row] = set()
        if state == Qt.Checked:
            self.current_discern[row].add(item)
        else:
            self.current_discern[row].discard(item)
        score = len(self.current_discern[row])
        if 0 <= row < self.data_table.rowCount():
            discern_widget = self.data_table.cellWidget(row, 12)
            if discern_widget and discern_widget.layout():
                score_label = discern_widget.layout().itemAt(discern_widget.layout().count() - 1).widget()
                if score_label:
                    score_label.setText(f"({score}/5)")
        self.current_data['discern_score'] = [len(d) for d in self.current_discern]

    def update_custom_data(self, row, column_name, value):
        if not self.current_custom_data or row >= len(self.current_data):
            return
        try:
            if any(col["name"] == column_name and col["type"] == "numeric" for col in self.custom_columns):
                value = float(value) if value.strip() else ""
            self.current_custom_data[column_name][row] = value
            self.current_data[column_name] = self.current_custom_data[column_name]
        except ValueError:
            QMessageBox.warning(self, "警告", f"请输入有效的数字到 {column_name}")

    def update_custom_multi(self, row, column_name, item, state):
        if not self.current_custom_data or row >= len(self.current_data):
            return
        if not isinstance(self.current_custom_data[column_name][row], set):
            self.current_custom_data[column_name][row] = set()
        if state == Qt.Checked:
            self.current_custom_data[column_name][row].add(item)
        else:
            self.current_custom_data[column_name][row].discard(item)
        score = len(self.current_custom_data[column_name][row])
        col_def = next((col for col in self.custom_columns if col["name"] == column_name), None)
        if col_def and 0 <= row < self.data_table.rowCount():
            col_idx = 13 + [col["name"] for col in self.custom_columns].index(column_name)
            cell_widget = self.data_table.cellWidget(row, col_idx)
            if cell_widget and cell_widget.layout():
                multi_widget = cell_widget.layout().itemAt(0).widget()
                if multi_widget and multi_widget.layout():
                    score_label = multi_widget.layout().itemAt(multi_widget.layout().count() - 1).widget()
                    if score_label:
                        score_label.setText(f"({score}/{len(col_def['enum_values'])})")
        self.current_data[column_name] = self.current_custom_data[column_name]

    def on_data_click(self, row, col):
        if col == 8:  # 查看列
            url = self.current_data.loc[row, "video_url"] if self.current_data is not None and row < len(self.current_data) else None
            if not url:
                url = self.current_data.loc[row, "note_url"] if self.current_data is not None and row < len(self.current_data) else None
            if url:
                webbrowser.open_new_tab(url)

    def save_records(self):
        if self.current_meta and self.current_jama and self.current_gqs and self.current_discern:
            try:
                self.history_manager.save_annotations(
                    self.current_meta, self.current_jama, self.current_gqs,
                    self.current_discern, self.current_custom_data
                )
                QMessageBox.information(self, "提示", "记录保存成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存记录失败：{str(e)}")

    def delete_selected_history(self):
        selected_items = self.history_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要删除的历史记录")
            return
        item = selected_items[0]
        idx = self.history_tree.indexOfTopLevelItem(item)
        metas = self.history_manager.get_history()
        meta = metas[idx]
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除文件 {meta['filename']} 的记录吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                success = self.history_manager.delete_history(meta)
                if success:
                    QMessageBox.information(self, "提示", "删除成功")
                    self.load_history()
                    self.data_table.clearContents()
                    self.current_meta = None
                    self.current_data = None
                    self.current_jama = None
                    self.current_gqs = None
                    self.current_discern = None
                    self.current_custom_data = None
                    self.custom_columns = []
                    self.update_table_columns()
                else:
                    QMessageBox.critical(self, "错误", "删除失败，请稍后重试")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除历史记录失败：{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())