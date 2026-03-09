from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

import json
import time
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from novelai.config.settings import settings


class DiagnosticsScreenMixin:
    """Diagnostics and usage history screen methods."""

    def _build_diagnostics_screen(self) -> Group:
        novels = self.storage.list_novels()
        total_novels = len(novels)
        total_translated = sum(self.storage.count_translated_chapters(novel_id) for novel_id in novels)

        cache_path = Path(settings.DATA_DIR) / "translation_cache.json"
        cache_entries = 0
        if cache_path.exists():
            try:
                cache_entries = len(json.loads(cache_path.read_text(encoding="utf-8")))
            except Exception:
                cache_entries = -1

        usage_summary = self.usage.summary()
        recent_usage = self.usage.list(limit=5)
        daily_history = self.usage.daily_history(limit=7)
        local_day = time.strftime("%Y-%m-%d")

        stats = Table.grid(expand=True, padding=(0, 2))
        stats.add_column(style="bold #f6bd60")
        stats.add_column(style="#e5e9f0")
        stats.add_row("Usage day", f"{local_day} (local)")
        stats.add_row("Novels stored", str(total_novels))
        stats.add_row("Translated chapters", str(total_translated))
        stats.add_row("Cached translations", str(cache_entries if cache_entries >= 0 else "error"))
        stats.add_row("Today's requests", str(usage_summary.get("total_requests")))
        stats.add_row("Today's tokens", str(usage_summary.get("total_tokens")))
        stats.add_row("Today's cost (USD)", f"${usage_summary.get('estimated_cost_usd', 0):.6f}")
        stats.add_row("Today's estimates", str(usage_summary.get("total_estimates")))
        stats.add_row("Estimated budget (USD)", f"${usage_summary.get('estimated_projection_cost_usd', 0):.6f}")

        usage_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #7dcfff")
        usage_table.add_column("Timestamp", style="#cbd5e1")
        usage_table.add_column("Type", style="#9ece6a")
        usage_table.add_column("Provider/Model", style="#e5e9f0")
        usage_table.add_column("Tokens", justify="right", style="#f6bd60")
        usage_table.add_column("Cost", justify="right", style="#bb9af7")

        if recent_usage:
            for entry in recent_usage:
                usage_table.add_row(
                    str(entry.get("timestamp")),
                    self._usage_entry_type_label(entry),
                    f"{entry.get('provider')}/{entry.get('model')}",
                    self._usage_entry_metric(entry),
                    f"${self._usage_entry_cost_usd(entry):.6f}",
                )
        else:
            usage_table.add_row("No usage records yet for today.", "-", "-", "-", "-")

        history_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #bb9af7")
        history_table.add_column("Date", style="#cbd5e1")
        history_table.add_column("Requests", justify="right", style="#e5e9f0")
        history_table.add_column("Tokens", justify="right", style="#7dcfff")
        history_table.add_column("Cost", justify="right", style="#f6bd60")
        history_table.add_column("Budget", justify="right", style="#9ece6a")

        if daily_history:
            for entry in daily_history:
                history_table.add_row(
                    str(entry.get("date")),
                    str(entry.get("total_requests")),
                    str(entry.get("total_tokens")),
                    f"${entry.get('estimated_cost_usd', 0):.6f}",
                    f"${entry.get('estimated_projection_cost_usd', 0):.6f}",
                )
        else:
            history_table.add_row("No stored usage history yet.", "-", "-", "-", "-")

        diagnostics_panel = Panel(
            Group(
                stats,
                Text(""),
                Text("Recent Activity Today", style="bold #7dcfff"),
                usage_table,
                Text(""),
                Text("Daily History", style="bold #bb9af7"),
                history_table,
            ),
            border_style="#7aa2f7",
            box=box.ROUNDED,
        )

        return Group(
            self._build_action_header(
                "Diagnostics",
                "Inspect today's local usage, recent activity, and the saved history from previous days.",
            ),
            diagnostics_panel,
            self._build_diagnostics_guide_panel(),
        )

    def _build_diagnostics_guide_panel(self) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        return Panel(
            Group(
                Text.assemble(
                    ("Status  ", "#9aa5ce"),
                    (self.last_status_message, f"bold {status_style}"),
                ),
                Text("Usage resets automatically at local midnight. Past days stay in history until you clear them.", style="#cbd5e1"),
                Text(""),
                Text("1) clear usage history        Remove today's usage and all saved daily history.", style="#cbd5e1"),
                Text("0) back                       Return to the dashboard.", style="#cbd5e1"),
            ),
            title="Guide Rail",
            border_style=status_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _parse_diagnostics_command(self, command: str) -> str | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return "back"
        if raw in ("1", "clear", "clear usage", "clear usage history"):
            return "clear"
        return None

    def _diagnostics_menu(self) -> None:
        self._set_status(
            "Diagnostics show today's local usage and keep past days in history until you clear them.",
            "info",
        )
        while True:
            command = self._prompt_renderable_command(
                self._build_diagnostics_screen(),
                default_value="0",
            )
            action = self._parse_diagnostics_command(command)
            if action is None:
                self._set_status("Unknown diagnostics command. Use 1 to clear usage history or 0 to go back.", "warning")
                continue
            if action == "back":
                self._set_status("Diagnostics refreshed.", "info")
                return

            self.usage.clear()
            self._set_status("Usage history cleared.", "success")

