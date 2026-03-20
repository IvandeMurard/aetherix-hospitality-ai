"""
Hotel F&B Agent — MCP Edition

Claude-powered agent that connects to the Hotel Context Layer via MCP.

This replaces the old autonomous_agent.py where each integration was
hardcoded (WeatherFetcher, EventsFetcher, etc. imported directly).

Now the agent connects to a single MCP server (the context layer),
discovers available tools automatically, and calls them through the
standard MCP protocol. Adding a new hotel system = adding a new MCP
server. Zero changes to this agent file.

Architecture:
    Claude (MCP Client)
        ↓ MCP protocol
    Hotel Context Layer (hotel_context_server.py)
        ↓ existing APIs / mock data
    Weather / Events / PMS / Pattern Memory
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


SYSTEM_PROMPT = """You are an expert hotel F&B (Food & Beverage) operations AI agent.

Your role is to predict demand for the F&B department 48 hours ahead and provide
actionable operational guidance, using the hotel's context layer (MCP) to access
all relevant systems in a single protocol call.

You have access to:
- Weather data — impacts outdoor seating, hot/cold beverage preferences
- Local events — concerts, sports, festivals drive walk-in footfall
- Hotel PMS — reservations, occupancy, group bookings, meal plans, special requests
- Historical pattern memory — real past scenarios with actual outcomes and staffing

After gathering context, produce a structured prediction:

**Expected covers:** [number]
**Recommended staff:** [number]
**Confidence:** [0-100%]

**Key drivers:**
1. [factor]
2. [factor]
3. [factor]

**Operational recommendations:**
- [specific action]
- [specific action]

Be concise and actionable. Hotel managers need clear numbers, not essays.
Never invent data — always call the tools first."""


async def run_hotel_mcp_agent(
    date: str,
    location: str = "Paris, France",
    city: str = "Paris"
) -> str:
    """
    Run the hotel F&B demand prediction agent using Claude + MCP.

    Connects to the Hotel Context Layer MCP server, discovers all tools,
    then lets Claude autonomously gather context and produce a prediction.
    """
    claude = anthropic.Anthropic()

    server_path = os.path.join(os.path.dirname(__file__), "mcp_servers", "hotel_context_server.py")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
        env={**os.environ}
    )

    print(f"\n{'═' * 60}")
    print("  HOTEL F&B AGENT  —  MCP Edition")
    print(f"{'═' * 60}")
    print(f"  Date     : {date}")
    print(f"  Location : {location}")
    print(f"  Model    : claude-sonnet-4-6")
    print(f"  Protocol : MCP (Model Context Protocol)")
    print(f"{'═' * 60}")
    print("  Connecting to Hotel Context Layer...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_response = await session.list_tools()
            tool_names = [t.name for t in tools_response.tools]
            print(f"  Tools discovered: {tool_names}")
            print(f"{'═' * 60}\n")

            # Format MCP tools for Claude's tool_use API
            claude_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
                for tool in tools_response.tools
            ]

            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Predict F&B demand for {location} on {date}. "
                        f"City for weather: {city}. "
                        f"Today is {datetime.now().strftime('%Y-%m-%d')}. "
                        f"Use all available tools to gather context before predicting."
                    )
                }
            ]

            # Agentic loop — Claude calls tools until it has enough context
            step = 1
            while True:
                response = claude.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=claude_tools,
                    messages=messages
                )

                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text = block.text

                    print(f"\n{'═' * 60}")
                    print("  PREDICTION")
                    print(f"{'═' * 60}")
                    print(final_text)
                    print(f"{'═' * 60}\n")
                    return final_text

                elif response.stop_reason == "tool_use":
                    tool_results = []

                    for block in response.content:
                        if block.type == "tool_use":
                            args_preview = json.dumps(block.input, ensure_ascii=False)
                            print(f"  [{step}] {block.name}({args_preview[:70]}{'...' if len(args_preview) > 70 else ''})")

                            # Call the tool through MCP — single protocol, any system
                            result = await session.call_tool(block.name, block.input)

                            if result.content:
                                result_text = (
                                    result.content[0].text
                                    if hasattr(result.content[0], "text")
                                    else str(result.content[0])
                                )
                            else:
                                result_text = "{}"

                            preview = result_text[:100].replace("\n", " ")
                            print(f"       → {preview}{'...' if len(result_text) > 100 else ''}")
                            step += 1

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_text
                            })

                    messages.append({"role": "user", "content": tool_results})

                else:
                    break

    return "Agent completed"


def main():
    parser = argparse.ArgumentParser(
        description="Hotel F&B MCP Agent — Claude-powered demand prediction via MCP"
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
        help="City name for weather (default: Paris)"
    )
    args = parser.parse_args()

    asyncio.run(run_hotel_mcp_agent(args.date, args.location, args.city))


if __name__ == "__main__":
    main()
