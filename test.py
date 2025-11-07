#!/usr/bin/env python3
"""Test script for the agent with optional streaming mode."""

import argparse
import requests
import sys
from test_utils import format_agent_output, process_sse_stream, display_user_query, generate_diagram

API_URL = "http://localhost:8000"


def test_agent(query: str, stream: bool = False):
    """Test the agent with a query.
    
    Args:
        query: The query string
        stream: Whether to use streaming mode (default: False)
    """
    display_user_query(query)
    
    if stream:
        response = requests.post(
            f"{API_URL}/api/query",
            json={"query": query},
            params={"stream": True},
            stream=True,
            timeout=300,
        )
        response.raise_for_status()
        return process_sse_stream(response)
    else:
        response = requests.post(
            f"{API_URL}/api/query",
            json={"query": query},
            params={"stream": False},
            timeout=300,
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the agent with a query")
    parser.add_argument("query", nargs="?", help="The query to test")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming mode (default: synchronous mode)"
    )
    
    args = parser.parse_args()
    
    if not args.query:
        print("Usage: python test.py <query> [--stream]")
        print("\nGenerating agent diagram...")
        generate_diagram()
        sys.exit(0)
    
    print("Generating agent diagram...")
    generate_diagram()
    print()
    
    result = test_agent(args.query, stream=args.stream)
    format_agent_output(result, skip_conversation_history=args.stream)

