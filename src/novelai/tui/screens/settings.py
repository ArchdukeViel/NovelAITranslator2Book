from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

import asyncio
from typing import Any, Callable

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from novelai.config.settings import settings as app_settings
from novelai.providers.registry import available_providers, get_provider


class SettingsScreenMixin:
    """Settings, provider selection, and API key management screen methods."""

    def _build_settings_summary_panel(self) -> Panel:
        provider = self.settings.get_provider_key()
        model = self.settings.get_provider_model()
        models = self._available_models_for_provider(provider)
        api_key_state = "configured" if self.settings.get_api_key() else "missing"
        model_text = ", ".join(models) if models else "No provider-declared models."

        settings_table = Table.grid(expand=True, padding=(0, 2))
        settings_table.add_column(style="bold #f6bd60")
        settings_table.add_column(style="#e5e9f0")
        settings_table.add_row("Provider", provider)
        settings_table.add_row("Model", model)
        settings_table.add_row("API key", api_key_state)
        settings_table.add_row("Available models", model_text)
        settings_table.add_row("Target language", app_settings.TRANSLATION_TARGET_LANGUAGE)
        settings_table.add_row("Source language", "Auto-detected from source site")
        settings_table.add_row("Scrape delay", f"{app_settings.SCRAPE_DELAY_SECONDS}s")

        return Panel(settings_table, border_style="#bb9af7", box=box.ROUNDED)

    def _current_api_key_text(self) -> str:
        api_key = self.settings.get_api_key()
        return api_key if api_key else "not set"

    def _set_api_validation(self, message: str, kind: str = "muted") -> None:
        self.api_validation_message = message
        self.api_validation_kind = kind

    async def _validate_provider_connection_async(self) -> tuple[bool, str]:
        provider = get_provider(self.settings.get_provider_key())
        return await provider.validate_connection(model=self.settings.get_provider_model())

    def _validate_provider_connection(self) -> tuple[bool, str]:
        try:
            with self.console.status("[bold #7dcfff]Validating provider connection...[/bold #7dcfff]", spinner="dots"):
                is_valid, message = asyncio.run(self._validate_provider_connection_async())
        except Exception as exc:
            is_valid, message = False, f"Validation failed: {exc}"

        self._set_api_validation(message, "success" if is_valid else "warning")
        return is_valid, message

    def _build_numbered_choice_panel(
        self,
        title: str,
        options: list[str],
        *,
        descriptions: list[str] | None = None,
        border_style: str = "#7aa2f7",
        back_label: str = "Back",
    ) -> Panel:
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(style="bold #f6bd60", no_wrap=True)
        grid.add_column(style="#e5e9f0")

        for index, option in enumerate(options, start=1):
            description = descriptions[index - 1] if descriptions and index - 1 < len(descriptions) else ""
            grid.add_row(f"{index})", Text.assemble((option, "bold #e5e9f0"), (f"  {description}" if description else "", "#cbd5e1")))

        grid.add_row("0)", Text(back_label, style="#cbd5e1"))

        return Panel(
            grid,
            title=title,
            border_style=border_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _build_settings_choice_screen(
        self,
        title: str,
        description: str,
        options: list[str],
        *,
        descriptions: list[str] | None = None,
    ) -> Group:
        return Group(
            self._build_action_header(title, description),
            self._build_settings_summary_panel(),
            self._build_numbered_choice_panel(
                title,
                options,
                descriptions=descriptions,
                border_style="#bb9af7",
            ),
        )

    def _build_api_key_screen(self) -> Group:
        validation_style = self.STATUS_STYLES.get(self.api_validation_kind, self.STATUS_STYLES["muted"])
        api_key_panel = Panel(
            Group(
                Text.assemble(
                    ("Current API key  ", "#9aa5ce"),
                    (self._current_api_key_text(), "bold #e5e9f0"),
                ),
                Text.assemble(
                    ("Validation  ", "#9aa5ce"),
                    (self.api_validation_message, f"bold {validation_style}"),
                ),
                Text(""),
                Text("1) set API key                Enter or replace the runtime API key.", style="#cbd5e1"),
                Text("2) clear API key              Remove the current runtime API key.", style="#cbd5e1"),
                Text("3) validate connection        Check that the current provider can reach its service.", style="#cbd5e1"),
                Text("0) back                       Return to settings.", style="#cbd5e1"),
            ),
            title="API Key",
            border_style="#bb9af7",
            box=box.ROUNDED,
            expand=True,
        )
        return Group(
            self._build_action_header(
                "API Key",
                "Review the current runtime API key, set a new one, or clear it.",
            ),
            self._build_settings_summary_panel(),
            api_key_panel,
        )

    def _build_api_key_entry_screen(self) -> Group:
        return Group(
            self._build_action_header(
                "Set API Key",
                "Enter a runtime API key for the current provider. Press Enter on an empty line to keep the current key.",
            ),
            self._build_settings_summary_panel(),
            Panel(
                Text.assemble(
                    ("Current API key  ", "#9aa5ce"),
                    (self._current_api_key_text(), "bold #e5e9f0"),
                ),
                title="API Key",
                border_style="#bb9af7",
                box=box.ROUNDED,
                expand=True,
            ),
        )

    def _parse_api_key_command(self, command: str) -> str | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return "back"
        if raw in ("1", "set", "set api key", "update", "update api key"):
            return "set"
        if raw in ("2", "clear", "clear api key", "remove"):
            return "clear"
        if raw in ("3", "validate", "validate api key", "validate connection", "test"):
            return "validate"
        return None

    def _api_key_menu(self) -> None:
        self._set_status("Use 1 to set the API key, 2 to clear it, 3 to validate it, or 0 to go back.", "info")
        while True:
            command = self._prompt_renderable_command(
                self._build_api_key_screen(),
                default_value="0",
            )
            action = self._parse_api_key_command(command)
            if action is None:
                self._set_status("Unknown API key command. Use 1, 2, 3, or 0.", "warning")
                continue
            if action == "back":
                self._set_status("Settings ready.", "info")
                return
            if action == "clear":
                if self.settings.get_api_key():
                    self.settings.clear_api_key()
                    self._set_api_validation("Not validated yet.", "muted")
                    self._set_status("API key cleared.", "success")
                else:
                    self._set_status("API key is already not set.", "info")
                continue
            if action == "validate":
                is_valid, message = self._validate_provider_connection()
                self._set_status(message, "success" if is_valid else "warning")
                continue

            api_key = self._prompt_renderable_command(
                self._build_api_key_entry_screen(),
                default_value="",
                label="API Key",
                allow_any_printable=True,
            ).strip()
            if not api_key:
                self._set_status("API key unchanged.", "info")
                continue

            self.settings.set_api_key(api_key)
            is_valid, message = self._validate_provider_connection()
            if is_valid:
                self._set_status(f"API key updated for {self.settings.get_provider_key()}. {message}", "success")
            else:
                self._set_status(
                    f"API key updated for {self.settings.get_provider_key()}, but validation failed. {message}",
                    "warning",
                )

    def _prompt_numbered_choice(
        self,
        renderable_factory: Callable[[], Any],
        *,
        option_count: int,
        default_value: str = "1",
        label: str = "Choice",
    ) -> int | None:
        while True:
            command = self._prompt_renderable_command(
                renderable_factory(),
                default_value=default_value,
                label=label,
            )
            raw = command.strip().lower()
            if raw in ("0", "back", "b", "cancel"):
                return None
            if raw.isdigit():
                selection = int(raw)
                if 1 <= selection <= option_count:
                    return selection
            self._set_status(f"Choose a number from 1 to {option_count}, or 0 to go back.", "warning")

    def _select_provider_and_model(self) -> tuple[str, str] | None:
        providers = available_providers()
        if not providers:
            self._set_status("No providers are registered.", "warning")
            return None

        current_provider = self.settings.get_provider_key()
        default_provider_index = providers.index(current_provider) + 1 if current_provider in providers else 1
        provider_choice = self._prompt_numbered_choice(
            lambda: self._build_settings_choice_screen(
                "Select Provider",
                "Choose the translation provider you want to use.",
                providers,
            ),
            option_count=len(providers),
            default_value=str(default_provider_index),
        )
        if provider_choice is None:
            self._set_status("Provider selection cancelled.", "warning")
            return None

        provider = providers[provider_choice - 1]
        models = self._available_models_for_provider(provider)
        if not models:
            current_model = self.settings.get_provider_model()
            return provider, current_model

        current_model = self.settings.get_provider_model()
        default_model_index = models.index(current_model) + 1 if current_model in models else 1
        model_choice = self._prompt_numbered_choice(
            lambda: self._build_settings_choice_screen(
                "Select Model",
                f"Choose the default model for {provider}.",
                models,
            ),
            option_count=len(models),
            default_value=str(default_model_index),
        )
        if model_choice is None:
            self._set_status("Model selection cancelled.", "warning")
            return None

        return provider, models[model_choice - 1]

    def _build_settings_screen(self) -> Group:
        return Group(
            self._build_action_header(
                "Settings",
                "Choose the provider, then the model for that provider, and update the API key used by Add Novel translation.",
            ),
            self._build_settings_summary_panel(),
            self._build_settings_guide_panel(),
        )

    def _build_settings_guide_panel(self) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        provider = self.settings.get_provider_key()
        models = self._available_models_for_provider(provider)
        model_text = ", ".join(models) if models else "No provider-declared models."
        return Panel(
            Group(
                Text.assemble(
                    ("Status  ", "#9aa5ce"),
                    (self.last_status_message, f"bold {status_style}"),
                ),
                Text.assemble(("Provider models  ", "#9aa5ce"), (model_text, "#cbd5e1")),
                Text(""),
                Text("1) select provider            Pick a provider, then choose one of its models.", style="#cbd5e1"),
                Text("2) set API key                Update the runtime API key used by the provider.", style="#cbd5e1"),
                Text("3) advanced                   Change target language and scrape delay.", style="#cbd5e1"),
                Text("0) back                       Return to the dashboard.", style="#cbd5e1"),
            ),
            title="Guide Rail",
            border_style=status_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _parse_settings_command(self, command: str) -> str | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return "back"
        if raw in ("1", "provider", "select provider"):
            return "provider"
        if raw in ("2", "api", "api key", "set api key"):
            return "api_key"
        if raw in ("3", "advanced"):
            return "advanced"
        return None

    def _settings_menu(self) -> None:
        self._set_status("Use 1 to choose a provider and model, 2 to set the API key, 3 for advanced, or 0 to go back.", "info")
        while True:
            command = self._prompt_renderable_command(
                self._build_settings_screen(),
                default_value="0",
            )
            action = self._parse_settings_command(command)
            if action is None:
                self._set_status("Unknown settings command. Use 1, 2, 3, or 0.", "warning")
                continue
            if action == "back":
                self._set_status("Settings ready.", "info")
                return

            if action == "provider":
                selection = self._select_provider_and_model()
                if selection is None:
                    continue
                provider, model = selection
                self.settings.set_provider_key(provider)
                self.settings.set_provider_model(model)
                self._set_api_validation("Not validated yet.", "muted")
                self._set_status(f"Provider set to {provider}. Default model set to {model}.", "success")
                continue

            if action == "advanced":
                self._advanced_settings_menu()
                continue

            self._api_key_menu()

    def _advanced_settings_menu(self) -> None:
        """Prompt user to change target language and scrape delay."""
        lang = Prompt.ask(
            "[bold #f6bd60]Target language[/bold #f6bd60]",
            default=app_settings.TRANSLATION_TARGET_LANGUAGE,
            console=self.console,
        ).strip()
        if lang:
            app_settings.TRANSLATION_TARGET_LANGUAGE = lang

        delay_str = Prompt.ask(
            "[bold #f6bd60]Scrape delay (seconds)[/bold #f6bd60]",
            default=str(app_settings.SCRAPE_DELAY_SECONDS),
            console=self.console,
        ).strip()
        try:
            delay = float(delay_str)
            if delay < 0:
                raise ValueError
            app_settings.SCRAPE_DELAY_SECONDS = delay
        except ValueError:
            self._set_status("Invalid delay value — keeping current setting.", "warning")
            return

        self._set_status(
            f"Target language set to '{lang}', scrape delay set to {app_settings.SCRAPE_DELAY_SECONDS}s.",
            "success",
        )
