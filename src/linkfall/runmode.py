"""The run mode is recorded in every run header so a replay is exact (ADR 0006)."""

from enum import StrEnum


class RunMode(StrEnum):
    STORY = "story"
    HARDENED = "hardened"
