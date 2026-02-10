# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Pyaptly automates creation and management of APT mirrors and snapshots using `aptly` under the hood. It reads a YAML config file and orchestrates `aptly` CLI commands in dependency order.

## Development Commands

### Environment Setup

Before running tests, source the test environment (sets `$HOME` and `$PATH` for `.aptly-bin/`):
```bash
source testenv
git submodule update --init --recursive  # test fixtures live in submodules
```

### Running Tests

```bash
make test-local          # full suite (starts local webserver with test packages)
py.test -x               # run all tests, stop at first failure
py.test -xvs pyaptly/aptly_test.py::test_mirror_create  # single test
```

Tests require `$HOME` to contain "pyaptly" or "vagrant" — this prevents accidental deletion of system data. `source testenv` handles this.

### Linting

Flake8 is configured in `.flake8` (ignores E203, E221, E222, E241, E251, E272). Run via:
```bash
flake8 pyaptly/
```

## Architecture

Nearly all logic lives in `pyaptly/__init__.py`. The design has three distinct phases:

### 1. Command Objects with Dependency Tracking

`Command` and `FunctionCommand` wrap either a subprocess call or a Python function. Each command declares:
- `provides`: virtual tokens it satisfies after running
- `requires`: virtual tokens that must be satisfied before it runs

`Command.order_commands()` topologically sorts commands into a valid execution sequence. This is the core of pyaptly — it ensures mirrors exist before snapshots, snapshots exist before publishes, etc.

### 2. System State Reader

`SystemStateReader` queries the live `aptly` instance to build a picture of current state: GPG keys, mirrors, repos, snapshots, and publish endpoints. It also maps snapshot merge-trees and publish-to-snapshot relationships.

### 3. Command Builders

Pure functions (`cmd_mirror_create`, `cmd_snapshot_create`, `cmd_publish_update`, etc.) diff desired config against current state and return lists of `Command` objects to close the gap.

### Data Flow

```
YAML config → SystemStateReader (current state) → Command builders
→ Command.order_commands() (topological sort) → execute()
```

### Timestamped Snapshots

Snapshot names can contain `%T`, expanded to a rounded timestamp (daily/weekly/ISO-week). `expand_timestamped_name()` handles expansion; `round_timestamp()` / `date_round_weekly()` handle the rounding logic. Publish configs reference snapshots by `"current"`, `"previous"`, or numeric offset.

### Config Merging

YAML configs support a `merge` key listing other YAML files to merge in, enabling config reuse.

## Test Infrastructure

`pyaptly/test.py` provides helpers for integration tests:
- `clean_and_config()`: context manager that sets up an isolated `$HOME` and wipes aptly state between tests
- `read_yml()` / `merge()`: config loading with merge support
- `execute_and_parse_show_cmd()`: parses output from `aptly snapshot show`

Test files: `aptly_test.py` (mirrors/snapshots/publishes), `dateround_test.py`, `graph_test.py`, `helpers_test.py`.

## CLI Usage

```bash
pyaptly -c config.yml mirror create [name]
pyaptly -c config.yml snapshot update [name]
pyaptly -c config.yml publish update [endpoint]
pyaptly -d ...   # debug mode, also writes .dot file for dependency graph
pyaptly -p ...   # pretend mode, no side effects
```
