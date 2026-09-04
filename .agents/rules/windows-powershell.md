---
trigger: always_on
description: Mandatory Windows host environment and PowerShell shell execution conventions.
---

# Windows & PowerShell Execution Rules

This rule enforces Windows OS compatibility, PowerShell syntax safety, and encoding standards for all terminal commands and file generation.

## Host OS & Shell Environment

- **Operating System**: Windows (primary shell is Windows PowerShell or PowerShell Core).
- **Prohibited Bashisms**: Never use Unix/Linux bash syntax or commands:
  | Prohibited Bashism | Allowed PowerShell / Tool Equivalent |
  |---|---|
  | `export VAR=val` | `$env:VAR = "val"` |
  | `cat <file>` | `Get-Content <file>` or `view_file` |
  | `grep -rn <pat>` | `rg <pat>` or `grep_search` |
  | `rm -rf <path>` | `Remove-Item -Recurse -Force <path>` |
  | `touch <file>` | `New-Item -ItemType File -Path <file> -Force` |
  | `source <env>` | `& <script.ps1>` |
  | `which <bin>` | `Get-Command <bin>` |
  | `cmd1 && cmd2` | `cmd1; if ($?) { cmd2 }` |
  | `curl <url>` | `Invoke-RestMethod` / `Invoke-WebRequest` (PS 5.1 `curl` alias breaks on curl flags) |
  | `head -n N` | `... \| Select-Object -First N` |
  | `tail -n N` | `... \| Select-Object -Last N` |
  | `ls <path>` | `Get-ChildItem <path>` or `list_dir` |

## Path Quoting & Whitespace Safety

- **Mandatory Quoting**: Always quote file paths containing whitespace or special characters:
  ```powershell
  # CORRECT
  cd "c:\Akmal\Novel AI\frontend"
  powershell -File "c:\Akmal\Novel AI\tools\pytest.ps1"

  # PROHIBITED
  cd c:\Akmal\Novel AI\frontend
  ```

## UTF-8 Encoding Without BOM

- **PowerShell 5.1 BOM Trap**: In Windows PowerShell 5.1, `Set-Content -Encoding utf8` writes a Byte Order Mark (`\uFEFF`). The BOM silently breaks Node.js JSON parsers (`Unexpected token '﻿'`), Python runtimes, and Docker builds.
- **Mandatory Safe UTF-8 Writing**: Always write text files and JSON specifications without BOM using .NET API:
  ```powershell
  [System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding($false)))
  ```

## Long-Running Commands & Non-Blocking Execution

- Commands expected to run indefinitely (dev servers, file watchers) must be dispatched with `IsDaemon: true`.
- Background tasks (like `graphify update` or test suites) notify automatically on completion &mdash; do not poll `manage_task status` in a loop.
