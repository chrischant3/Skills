#!/usr/bin/env python3
"""REST fallback for source control: fetch merged changes for every configured repo into raw/.

Use it when the platform's MCP isn't available. It writes the same file shapes Claude
saves from an MCP, so both go through anonymise.py and link_scm.py the same way.

Usage:
  scm_fetch.py --config scm.yaml --issues clean/ --out raw/
  scm_fetch.py --config scm.yaml --since 2026-01-31 --out raw/
  scm_fetch.py --print-since --issues clean/

The window starts at --since, or by default at the earliest created date among the
anonymised defects in clean/, so it follows the run's own time window. --print-since
prints that date, for use when fetching through an MCP instead.

Credentials come from the environment and are never written or logged. GitLab:
GITLAB_TOKEN. Azure DevOps: AZDO_PAT. Repos on platforms that aren't ready yet are skipped.
"""

import argparse
import os
import sys

import clean_data
import scm_adapter
import scm_config


def fetch_all(config: dict, since: str, out_dir, client_for=None) -> list[dict]:
    """Fetch every ready repo in config into out_dir.

    Args:
        config: as scm_config.load_config() returns it.
        since: ISO date the window starts on.
        out_dir: the run's raw/ folder.
        client_for: callable(repo) -> client; default builds one from the environment.
    Returns:
        one summary per repo: the adapter's fetch summary, or {"repo", "skipped": reason}.
    Raises:
        KeyError: naming a missing credential, before anything is fetched.
    """
    repos = config["repos"]
    if client_for is None:
        # Build every client first, so a missing credential stops the run before anything is fetched.
        clients = [
            scm_adapter.adapter_for(r["platform"]).client_from_env(r, os.environ)
            if scm_adapter.is_ready(r["platform"])
            else None
            for r in repos
        ]
    else:
        clients = [
            client_for(r) if scm_adapter.is_ready(r["platform"]) else None
            for r in repos
        ]
    results = []
    for repo, client in zip(repos, clients):
        if client is None:
            results.append(
                {
                    "repo": str(repo.get("repo") or repo.get("project")),
                    "skipped": f"{repo['platform']} isn't ready yet",
                }
            )
            continue
        results.append(
            scm_adapter.adapter_for(repo["platform"]).fetch(
                repo, since, out_dir, client
            )
        )
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch merged changes for every repo in scm.yaml into raw/."
    )
    ap.add_argument("--config", default="scm.yaml")
    ap.add_argument(
        "--issues", default="clean", help="anonymised defects, for the default window"
    )
    ap.add_argument(
        "--since",
        help="ISO date the window starts on (default: the earliest defect in --issues)",
    )
    ap.add_argument("--out", default="raw")
    ap.add_argument(
        "--print-since",
        action="store_true",
        help="print the window's start date and stop",
    )
    a = ap.parse_args(argv)
    try:
        since = a.since or clean_data.earliest_created(
            clean_data.load_clean_issues(a.issues)
        )
        if not since:
            raise ValueError(
                "no defects in --issues to take the window from; pass --since"
            )
        if a.print_since:
            print(since)
            return 0
        results = fetch_all(scm_config.load_config(a.config), since, a.out)
    except KeyError as err:
        print(f"error: set {err.args[0]} in your shell first", file=sys.stderr)
        return 2
    except (ValueError, RuntimeError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    for r in results:
        print(
            f"{r['repo']}: skipped, {r['skipped']}"
            if "skipped" in r
            else f"{r['repo']}: {r['changes']} merged changes since {since} -> {a.out}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
