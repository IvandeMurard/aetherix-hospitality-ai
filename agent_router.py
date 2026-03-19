"""
Agent Router

Dispatches to the right execution path based on system availability:

  MCP path    → mcp_agent.py       Claude + MCP protocol, dynamic tool discovery
  Direct path → autonomous_agent.py  Mistral, hardcoded integrations

Decision logic (in order):
  1. Is ANTHROPIC_API_KEY set?          Required for Claude / MCP agent.
  2. Are all required MCP servers present and enabled in the registry?
  3. If both true  → MCP path
     If either false → Direct path (graceful fallback)

This lets both architectures coexist. Flip a system's "enabled" flag in
mcp_servers/registry.py to force a fallback without touching agent code.

Usage:
  python agent_router.py --date 2025-12-24 --location "Paris, France"
  python agent_router.py --status          # show routing report only
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


def _check_routing() -> tuple:
    """
    Returns (path, reason):
      path   — "mcp" or "direct"
      reason — human-readable explanation
    """
    from mcp_servers.registry import all_required_available, get_available_systems, REQUIRED_SYSTEMS

    has_claude = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_mistral = bool(os.getenv("MISTRAL_API_KEY"))
    available = get_available_systems()

    if not has_claude:
        if not has_mistral:
            print("ERROR: Neither ANTHROPIC_API_KEY nor MISTRAL_API_KEY is set.")
            sys.exit(1)
        return "direct", "ANTHROPIC_API_KEY not set — Claude/MCP requires it"

    if not all_required_available():
        missing = [s for s in REQUIRED_SYSTEMS if not available.get(s)]
        reason = f"MCP servers missing or disabled: {missing}"
        if not has_mistral:
            print(f"ERROR: Cannot use MCP path ({reason}) and MISTRAL_API_KEY is not set.")
            sys.exit(1)
        return "direct", reason

    return "mcp", "All required MCP servers available + ANTHROPIC_API_KEY set"


def _print_routing_report() -> tuple:
    """Print a status table and return the routing decision."""
    from mcp_servers.registry import REGISTRY, get_available_systems, REQUIRED_SYSTEMS

    available = get_available_systems()
    path, reason = _check_routing()

    print(f"\n{'═' * 64}")
    print("  AGENT ROUTER — System Availability")
    print(f"{'═' * 64}")
    print(f"  {'System':<12}  {'Server file':<28}  {'Status':<12}  {'Required'}")
    print(f"  {'-'*12}  {'-'*28}  {'-'*12}  {'-'*8}")

    for name, meta in REGISTRY.items():
        is_ready = available.get(name, False)
        tag = "✓ ready" if is_ready else "✗ missing"
        req = "required" if name in REQUIRED_SYSTEMS else ""
        server_name = os.path.basename(meta["server_path"])
        print(f"  {name:<12}  {server_name:<28}  {tag:<12}  {req}")

    has_claude = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_mistral = bool(os.getenv("MISTRAL_API_KEY"))

    print(f"\n  ANTHROPIC_API_KEY  : {'✓ set' if has_claude else '✗ not set'}")
    print(f"  MISTRAL_API_KEY    : {'✓ set' if has_mistral else '✗ not set'}")
    print(f"\n  ▶  Selected path   : {path.upper()}")
    print(f"  ▶  Reason          : {reason}")
    print(f"{'═' * 64}\n")

    return path, reason


def main():
    parser = argparse.ArgumentParser(
        description="Agent Router — dispatches to MCP or direct agent based on availability"
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date to predict (YYYY-MM-DD, default: today)"
    )
    parser.add_argument(
        "--location",
        default="Paris, France",
        help="Hotel location for events search (default: Paris, France)"
    )
    parser.add_argument(
        "--city",
        default="Paris",
        help="City name for weather lookup (default: Paris)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show routing status report and exit without running a prediction"
    )
    args = parser.parse_args()

    path, _ = _print_routing_report()

    if args.status:
        return

    if path == "mcp":
        from mcp_agent import run_hotel_mcp_agent
        asyncio.run(run_hotel_mcp_agent(args.date, args.location, args.city))
    else:
        from autonomous_agent import AutonomousAgent
        agent = AutonomousAgent()
        location_parts = args.location.split(",")
        city = args.city or (location_parts[0].strip() if location_parts else "Paris")
        agent.predict_for_date(
            date=args.date,
            location=args.location,
            city=city,
            country="FR"
        )


if __name__ == "__main__":
    main()
