from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QListView,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container
from novelai.config.settings import settings
from novelai.interfaces.desktop.pages import (
    ActivityView,
    DiagnosticsView,
    HomeView,
    LibraryView,
    ProfilesView,
    SettingsView,
)
from novelai.interfaces.desktop.pages.import_page import ImportPage
from novelai.interfaces.desktop.pages.workspace import BookWorkspace, GlossaryTab, OCRReviewTab, TranslateTab
from novelai.interfaces.desktop.pages.workspace_panels import ExportTab
from novelai.interfaces.desktop.shared import (
    DesktopActivityModel,
    build_stylesheet,
    resolve_theme_preference,
)

__all__ = [
    "BookWorkspace",
    "DesktopMainWindow",
    "ExportTab",
    "GlossaryTab",
    "OCRReviewTab",
    "TranslateTab",
]


class DesktopMainWindow(QMainWindow):
    SIDEBAR_PANEL_WIDTH = 200
    SIDEBAR_NAV_WIDTH = 180

    ICON_ASSETS = {
        "home": "home.svg",
        "library": "library.svg",
        "import": "import.svg",
        "activity": "activity.svg",
        "profiles": "profiles.svg",
        "diagnostics": "diagnostics.svg",
        "settings": "settings.svg",
    }

    TOP_LEVEL_PAGES = (
        ("home", "Home"),
        ("library", "Novel Library"),
        ("import", "Import and Scrape"),
        ("activity", "Activity"),
        ("profiles", "Profiles"),
        ("diagnostics", "Diagnostics"),
        ("settings", "Settings"),
    )

    def __init__(self) -> None:
        super().__init__()
        bootstrap()
        self.activity_model = DesktopActivityModel()
        self.page_items: dict[str, QListWidgetItem] = {}
        self.page_widgets: dict[str, QWidget] = {}
        self._nav_labels_visible = True
        self.workspace_key: str | None = None
        self.workspace: BookWorkspace | None = None

        self.setWindowTitle("NovelAI2Book")
        self.resize(1380, 920)
        self.assets_dir = Path(__file__).resolve().parent / "assets"
        root = QSplitter()
        root.setObjectName("DesktopRoot")
        self.setCentralWidget(root)
        self.root_splitter = root

        self.nav_panel = QWidget()
        self.nav_panel.setObjectName("NavPanel")
        self.nav_panel.setMinimumWidth(self.SIDEBAR_PANEL_WIDTH)
        self.nav_panel.setMaximumWidth(self.SIDEBAR_PANEL_WIDTH)
        nav_layout = QVBoxLayout(self.nav_panel)
        nav_layout.setContentsMargins(6, 8, 6, 8)
        nav_layout.setSpacing(10)

        self.nav_brand_button = QPushButton()
        self.nav_brand_button.setObjectName("NavBrandButton")
        brand_icon = QIcon(str(self.assets_dir / "icons" / "workspace.svg"))
        if not brand_icon.isNull():
            self.nav_brand_button.setIcon(brand_icon)
            self.nav_brand_button.setIconSize(QSize(18, 18))
        else:
            self.nav_brand_button.setText("*")
        self.nav_brand_button.setToolTip("NovelAI2Book")
        nav_layout.addWidget(self.nav_brand_button, 0, Qt.AlignmentFlag.AlignHCenter)
        nav_layout.addSpacing(13)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setSpacing(7)
        self.nav.setUniformItemSizes(True)
        self.nav.setFlow(QListView.Flow.TopToBottom)
        self.nav.setMovement(QListView.Movement.Static)
        self.nav.setWrapping(False)
        self.nav.setWordWrap(False)
        self.nav.setGridSize(QSize(44, 44))
        self.nav.setResizeMode(QListView.ResizeMode.Adjust)
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setMinimumWidth(self.SIDEBAR_NAV_WIDTH)
        self.nav.setMaximumWidth(self.SIDEBAR_NAV_WIDTH)
        nav_layout.addWidget(self.nav)
        nav_layout.addStretch()

        self.nav_avatar = QLabel("AP")
        self.nav_avatar.setObjectName("NavAvatar")
        self.nav_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nav_avatar.setToolTip("Active Profile")
        nav_layout.addWidget(self.nav_avatar, 0, Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(self.nav_panel)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        root.setStretchFactor(0, 0)
        root.setStretchFactor(1, 1)
        root.setSizes([60, 1220])

        self.home_view = HomeView(self.activity_model)
        self.library_view = LibraryView()
        self.import_view = ImportPage(self.activity_model, self.refresh_all_views)
        self.activity_view = ActivityView(self.activity_model)
        self.library_view.open_requested.connect(self.open_workspace)
        self.library_view.navigate_requested.connect(self._navigate_to_page)
        self.home_view.navigate_requested.connect(self._navigate_to_page)
        self.home_view.open_workspace_requested.connect(self.open_workspace)
        self.import_view.open_workspace_requested.connect(self.open_workspace)
        self.profiles_view = ProfilesView(self.refresh_all_views)
        self.diagnostics_view = DiagnosticsView()
        self.settings_view = SettingsView(self.refresh_all_views)

        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.paletteChanged.connect(self._on_palette_changed)
            style_hints = app.styleHints()
            if hasattr(style_hints, "colorSchemeChanged"):
                style_hints.colorSchemeChanged.connect(self._on_palette_changed)

        for key, label in self.TOP_LEVEL_PAGES:
            widget = getattr(self, f"{key}_view")
            self._add_page(key, label, widget, scrollable=True)

        self.nav.currentItemChanged.connect(self._switch_view)
        self.activity_model.jobs_changed.connect(self._refresh_status_bar)
        self.activity_model.messages_changed.connect(self._refresh_status_bar)
        self._apply_nav_mode()
        self._navigate_to_page("home")
        self._refresh_status_bar()

    def _apply_theme_from_preferences(self) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        selected_theme = container.preferences.get_theme()
        resolved_theme = resolve_theme_preference(selected_theme, app)
        app.setStyleSheet(build_stylesheet(self.assets_dir, theme=resolved_theme))

    def _on_palette_changed(self, *_args: object) -> None:
        if container.preferences.get_theme().strip().lower() == "auto":
            self._apply_theme_from_preferences()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in {
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.ThemeChange,
        }:
            self._on_palette_changed()

    def _toggle_nav_labels(self) -> None:
        self._apply_nav_mode()

    def _apply_nav_mode(self) -> None:
        self.nav.setViewMode(QListView.ViewMode.ListMode)
        self.nav.setMinimumWidth(self.SIDEBAR_NAV_WIDTH)
        self.nav.setMaximumWidth(self.SIDEBAR_NAV_WIDTH)
        self.root_splitter.setSizes([200, 1080])

        for item in self.page_items.values():
            label = item.data(Qt.ItemDataRole.UserRole + 1)
            label_text = str(label) if isinstance(label, str) else ""
            item.setText(label_text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item.setSizeHint(QSize(168, 42))

    def _nav_icon(self, key: str):
        icon_map = {
            "home": QStyle.StandardPixmap.SP_DirHomeIcon,
            "library": QStyle.StandardPixmap.SP_DirOpenIcon,
            "import": QStyle.StandardPixmap.SP_FileIcon,
            "activity": QStyle.StandardPixmap.SP_BrowserReload,
            "profiles": QStyle.StandardPixmap.SP_DialogApplyButton,
            "diagnostics": QStyle.StandardPixmap.SP_MessageBoxInformation,
            "settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        }
        if key.startswith("workspace:"):
            workspace_icon_path = self.assets_dir / "icons" / "workspace.svg"
            workspace_icon = QIcon(str(workspace_icon_path))
            if not workspace_icon.isNull():
                return workspace_icon
            return self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        asset_name = self.ICON_ASSETS.get(key)
        if asset_name:
            asset_icon_path = self.assets_dir / "icons" / asset_name
            asset_icon = QIcon(str(asset_icon_path))
            if not asset_icon.isNull():
                return asset_icon

        icon_type = icon_map.get(key, QStyle.StandardPixmap.SP_FileDialogListView)
        return self.style().standardIcon(icon_type)

    @staticmethod
    def _wrap_scroll_page(widget: QWidget) -> QScrollArea:
        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setFrameShape(QScrollArea.Shape.NoFrame)
        container.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        container.setWidget(widget)
        return container

    def _add_page(self, key: str, label: str, widget: QWidget, *, scrollable: bool = False) -> None:
        stack_widget: QWidget = self._wrap_scroll_page(widget) if scrollable else widget
        item = QListWidgetItem("")
        item.setIcon(self._nav_icon(key))
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setData(Qt.ItemDataRole.UserRole + 1, label)
        item.setToolTip(label)
        item.setSizeHint(QSize(44, 44))
        self.page_items[key] = item
        self.page_widgets[key] = stack_widget
        self.nav.addItem(item)
        self.stack.addWidget(stack_widget)
        self._apply_nav_mode()

    def _navigate_to_page(self, key: str) -> None:
        item = self.page_items.get(key)
        if item is not None:
            self.nav.setCurrentItem(item)

    def _switch_view(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(key, str) and key in self.page_widgets:
            self.stack.setCurrentWidget(self.page_widgets[key])

    def _refresh_status_bar(self) -> None:
        provider = container.preferences.get_preferred_provider()
        model = container.preferences.get_preferred_model()
        jobs = len(self.activity_model.running_jobs())
        self.statusBar().showMessage(
            f"Library: {settings.NOVEL_LIBRARY_DIR} | Provider: {provider} | Model: {model} | Running Jobs: {jobs}"
        )

    def refresh_all_views(self) -> None:
        for key in ("home", "library", "import", "activity", "profiles", "diagnostics", "settings"):
            widget = getattr(self, f"{key}_view", None)
            if widget is not None and hasattr(widget, "refresh"):
                getattr(widget, "refresh")()
        if self.workspace is not None:
            self.workspace.refresh()
            workspace_item = self.page_items.get(self.workspace_key or "")
            if workspace_item is not None:
                title = (container.storage.load_metadata(self.workspace.novel_id) or {}).get("title") or self.workspace.novel_id
                workspace_label = f"Workspace: {title}"
                workspace_item.setData(Qt.ItemDataRole.UserRole + 1, workspace_label)
                workspace_item.setToolTip(f"Workspace: {title}")
                if self._nav_labels_visible:
                    workspace_item.setText(workspace_label)
        self._refresh_status_bar()

    def open_workspace(self, novel_id: str) -> None:
        key = f"workspace:{novel_id}"
        if self.workspace_key == key and self.workspace is not None:
            self.workspace.refresh()
            self._navigate_to_page(key)
            return

        if self.workspace is not None and self.workspace_key is not None:
            old_item = self.page_items.pop(self.workspace_key, None)
            old_widget = self.page_widgets.pop(self.workspace_key, None)
            if old_item is not None:
                row = self.nav.row(old_item)
                self.nav.takeItem(row)
            if old_widget is not None:
                self.stack.removeWidget(old_widget)
                old_widget.deleteLater()

        self.workspace_key = key
        self.workspace = BookWorkspace(
            novel_id,
            activity_model=self.activity_model,
            refresh_callback=self.refresh_all_views,
        )
        title = (container.storage.load_metadata(novel_id) or {}).get("title") or novel_id
        self._add_page(key, f"Workspace: {title}", self.workspace)
        self._navigate_to_page(key)
        self.refresh_all_views()


def main() -> None:
    bootstrap()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI Variable Text", 10))
    assets_dir = Path(__file__).resolve().parent / "assets"
    selected_theme = container.preferences.get_theme()
    resolved_theme = resolve_theme_preference(selected_theme, app)
    app.setStyleSheet(build_stylesheet(assets_dir, theme=resolved_theme))
    window = DesktopMainWindow()
    window.show()
    app.exec()
