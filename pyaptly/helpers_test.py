"""Testing testing helper functions"""
import datetime
import subprocess
import threading
from unittest.mock import patch

import pytest

from pyaptly import (
    Command,
    FunctionCommand,
    SystemStateReader,
    call_output,
    format_timestamp,
    unit_or_list_to_list,
)


def test_call_output_error():
    """Test if call_output raises errors correctly"""
    args = [
        'bash',
        '-c',
        'exit 42',
    ]
    error = False
    try:
        call_output(args)
    except subprocess.CalledProcessError as e:
        assert e.returncode == 42
        error = True
    assert error


def test_command_dependency_fail():
    """Test if bad dependencies fail correctly."""
    a = Command(['ls'])
    error = False
    try:
        a.require("turbo", "banana")
    except AssertionError:
        error = True
    assert error


def test_dependency_callback_file():
    """Test if bad dependencies fail correctly."""
    state = SystemStateReader()
    try:
        state.has_dependency(['turbo', 'banana'])
    except ValueError as e:
        assert "Unknown dependency" in e.args[0]
        error = True
    assert error


# --- unit_or_list_to_list ---

def test_unit_or_list_to_list_scalar():
    """A single string is wrapped in a list."""
    assert unit_or_list_to_list("foo") == ["foo"]


def test_unit_or_list_to_list_list():
    """A list is returned as-is."""
    assert unit_or_list_to_list(["foo", "bar"]) == ["foo", "bar"]


# --- format_timestamp ---

def test_format_timestamp():
    """Timestamps are formatted as ISO-style strings."""
    ts = datetime.datetime(2015, 10, 1, 23, 0)
    assert format_timestamp(ts) == "20151001T2300Z"


# --- Command.run_levels ---

def test_run_levels_single_command():
    """A single-command level executes the command."""
    results = []
    cmd = FunctionCommand(lambda: results.append(1))
    Command.run_levels([[cmd]])
    assert results == [1]


def test_run_levels_respects_level_order():
    """Commands in later levels run after earlier levels complete."""
    order = []
    lock = threading.Lock()

    def make_appender(val):
        def f():
            with lock:
                order.append(val)
        return FunctionCommand(f)

    Command.run_levels([[make_appender(1)], [make_appender(2)]])
    assert order == [1, 2]


def test_run_levels_parallel_within_level():
    """Multiple commands in a single level execute concurrently."""
    barrier = threading.Barrier(2, timeout=5)
    results = []

    def f():
        barrier.wait()
        results.append(True)

    Command.run_levels([[FunctionCommand(f), FunctionCommand(f)]])
    assert len(results) == 2


def test_run_levels_exception_propagates():
    """An exception raised inside a command propagates from run_levels."""
    def bad():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        Command.run_levels([[FunctionCommand(bad)]])


def test_run_levels_exception_propagates_from_parallel():
    """An exception in a parallel-level command propagates from run_levels."""
    def bad():
        raise RuntimeError("parallel-boom")

    with pytest.raises(RuntimeError, match="parallel-boom"):
        Command.run_levels([[FunctionCommand(bad), FunctionCommand(bad)]])


# --- SystemStateReader parallel fetch helpers ---

def test_fetch_one_snapshot_parses_sources():
    """_fetch_one_snapshot extracts source snapshot names from aptly output."""
    fake_output = (
        "Name: my-snap\n"
        "Sources:\n"
        "  other-snap [snapshot]\n"
        "  unrelated [repo]\n"
        "Description: test\n"
    )
    reader = SystemStateReader()
    with patch("pyaptly.call_output", return_value=(fake_output, "")):
        name, sources = reader._fetch_one_snapshot("my-snap")
    assert name == "my-snap"
    assert sources == {"other-snap"}


def test_fetch_one_publish_parses_sources():
    """_fetch_one_publish extracts source snapshot names from aptly output."""
    fake_output = (
        "Prefix: s3:mybucket\n"
        "Sources:\n"
        "  main: my-snap [snapshot]\n"
        "  contrib: other-snap [snapshot]\n"
        "Distribution: stable\n"
    )
    reader = SystemStateReader()
    with patch("pyaptly.call_output", return_value=(fake_output, "")):
        publish, sources = reader._fetch_one_publish("s3:mybucket stable")
    assert publish == "s3:mybucket stable"
    assert sources == {"my-snap", "other-snap"}
