#!/usr/bin/env python3
"""Minimal test script for the agent."""

import requests
import sys
import os

# Add app directory to path to import agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from agent import create_agent_executor

API_URL = "http://localhost:8000"


def generate_diagram():
    """Generate and save a mermaid diagram of the agent graph."""
    try:
        agent = create_agent_executor()
        graph_img = agent.get_graph().draw_mermaid_png()
        
        output_path = "agent_diagram.png"
        with open(output_path, "wb") as f:
            f.write(graph_img)
        print(f"📊 Agent diagram saved to {output_path}")
        return True
    except Exception as e:
        print(f"⚠️  Could not generate diagram: {e}")
        return False


def test_agent(query: str):
    """Test the agent with a query."""
    try:
        response = requests.post(
            f"{API_URL}/api/query",
            json={"query": query},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test.py <query>")
        print("\nGenerating agent diagram...")
        generate_diagram()
        sys.exit(0)
    
    # Generate diagram first
    print("Generating agent diagram...")
    generate_diagram()
    print()
    
    query = sys.argv[1]
    result = test_agent(query)
    
    if result:
        print(result.get("response", "No response"))
    else:
        print("Failed to get response")
        sys.exit(1)

