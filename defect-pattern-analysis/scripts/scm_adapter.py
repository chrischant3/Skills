#!/usr/bin/env python3
"""The common interface every source control adapter implements, and where adapters are found.

Linking (link_scm.py) talks to source control only through this interface, so a new
platform such as Bitbucket or GitHub is one new module with a SourceControlAdapter
subclass, plus one line in ADAPTER_MODULES. Nothing in the core changes.

An adapter does two jobs:
- fetch(): the REST fallback. It writes raw JSON to raw/, in the same file shapes that
  Claude saves from the platform's MCP, so both feed one normalise path.
- changes(): reads anonymised documents from clean/ (MCP or REST shaped) and returns
  platform-neutral Change records for one configured repo.

Adapters never see people: changes() reads only data that anonymise.py has written.
"""

import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# platform name -> module that defines ADAPTER, an instance of a SourceControlAdapter subclass.
ADAPTER_MODULES = {"gitlab": "scm_gitlab"}
# Platforms whose config shape is accepted but whose adapter isn't built yet: platform -> required fields.
PLANNED = {"azure": ("org", "project", "repo")}


@dataclass
class Change:
    """One merged change (a GitLab merge request, an Azure DevOps pull request, ...).

    Attributes:
        repo: the configured repo's name, as adapter.repo_name() gives it.
        kind: the platform's word for a change, such as "merge_request".
        id: the change's number within its repo, as a string.
        merged_at: ISO 8601 timestamp, or None if unknown.
        title, description, source_branch: text that may hold issue keys.
        commits: [{"id": sha, "message": text}] for every commit in the change.
        files: paths changed, without duplicates.
    """

    repo: str
    kind: str
    id: str
    merged_at: str | None
    title: str = ""
    description: str = ""
    source_branch: str = ""
    commits: list[dict] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def texts(self) -> list[str]:
        """Every piece of text that may name an issue key: title, description, branch, commit messages."""
        return [self.title, self.description, self.source_branch, *(c.get("message") or "" for c in self.commits)]


class SourceControlAdapter(ABC):
    """Base class for one source control platform.

    Attributes:
        platform: the name used in scm.yaml, such as "gitlab".
        required_fields: scm.yaml fields every repo on this platform must set.
        optional_fields: further scm.yaml fields this platform understands.
    """

    platform: str = ""
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()

    def check_field(self, key: str, value) -> None:
        """Raise ValueError if value isn't allowed for the optional field key."""

    def owns_file(self, name: str) -> bool:
        """True if a raw or clean file name is one of this platform's source control files."""
        return False

    def personal_owner(self, repo: dict, documents: dict) -> str | None:
        """The username a repo's path holds if it lives in a person's own namespace, else None.

        anonymise.py removes it everywhere, and repo_name() shows it as [person].
        """
        return None

    @abstractmethod
    def repo_name(self, repo: dict, documents: dict) -> str:
        """A stable, readable name for a configured repo, used in every output.

        Never holds a username: a repo in a personal namespace is shown as [person]/name.
        documents (file name -> parsed JSON) may tell the adapter what kind of namespace it is.
        """

    @abstractmethod
    def client_from_env(self, repo: dict, environ):
        """Build the platform's REST client from credentials in environ.

        Raises:
            KeyError: naming the environment variable that is missing.
        """

    @abstractmethod
    def fetch(self, repo: dict, since: str, out_dir, client) -> dict:
        """REST fallback: write raw JSON for every change merged on or after since into out_dir.

        Args:
            repo: the repo's scm.yaml entry.
            since: ISO date (YYYY-MM-DD), from the run's time window.
            out_dir: the run's raw/ folder.
            client: the platform's REST client.
        Returns:
            a summary such as {"repo": ..., "changes": n, "files_written": n}.
        """

    @abstractmethod
    def changes(self, documents: dict, repo: dict) -> list[Change]:
        """Return every change for repo found in documents (clean file name -> parsed JSON)."""


def adapter_for(platform: str) -> SourceControlAdapter:
    """Return the adapter for platform.

    Raises:
        NotImplementedError: for a planned platform that has no adapter yet.
        ValueError: for an unknown platform.
    """
    if platform in ADAPTER_MODULES:
        return importlib.import_module(ADAPTER_MODULES[platform]).ADAPTER
    if platform in PLANNED:
        raise NotImplementedError(f"{platform} linking isn't ready yet")
    raise ValueError(f"unknown platform {platform!r}; expected one of {sorted(known_platforms())}")


def known_platforms() -> set[str]:
    """Every platform scm.yaml may name, ready or planned."""
    return set(ADAPTER_MODULES) | set(PLANNED)


def is_ready(platform: str) -> bool:
    """True if platform has a working adapter."""
    return platform in ADAPTER_MODULES


def required_fields(platform: str) -> tuple[str, ...]:
    """The scm.yaml fields a repo on platform must set."""
    if platform in PLANNED:
        return PLANNED[platform]
    return adapter_for(platform).required_fields


def is_source_control_file(name: str) -> bool:
    """True if name is a source control file that any ready adapter reads."""
    return any(adapter_for(p).owns_file(name) for p in ADAPTER_MODULES)


def personal_owners(config: dict, documents: dict) -> list[str]:
    """Usernames held in the paths of configured repos that live in personal namespaces."""
    owners = []
    for repo in config["repos"]:
        if is_ready(repo["platform"]):
            owner = adapter_for(repo["platform"]).personal_owner(repo, documents)
            if owner:
                owners.append(owner)
    return owners


def optional_fields(platform: str) -> tuple[str, ...]:
    """Further scm.yaml fields a repo on platform may set (none for planned platforms)."""
    return () if platform in PLANNED else adapter_for(platform).optional_fields


def check_optional_field(platform: str, key: str, value, line: int) -> None:
    """Check an optional field's value, raising ValueError naming the line."""
    try:
        adapter_for(platform).check_field(key, value)
    except ValueError as err:
        raise ValueError(f"line {line}: {err}") from None
