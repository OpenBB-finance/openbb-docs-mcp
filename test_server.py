#!/usr/bin/env python3
"""
Test script for the OpenBB Documentation MCP Server
"""

import asyncio
from fastmcp import Client
from server import mcp

async def test_server():
    """Test the OpenBB docs MCP server functionality."""
    print("🧪 Testing OpenBB Documentation MCP Server...")

    async with Client(mcp) as client:
        # Test 1: Identify sections (get raw TOC)
        print("\n1️⃣ Testing section identification...")
        try:
            tool_result = await client.call_tool("identify_openbb_docs_sections", {"user_query": "copilot features"})
            result = tool_result.data  # Get the actual result data

            if result.get('success'):
                toc_content = result.get('raw_toc_content', '')
                print(f"✅ Section identification successful")
                print(f"   📋 Received TOC with {len(toc_content)} characters")
                print(f"   ℹ️  Instructions provided for LLM to analyze and select relevant sections")
            else:
                print(f"❌ Section identification failed: {result.get('error', 'Unknown error')}")
                return

        except Exception as e:
            print(f"❌ Section identification failed: {e}")
            return

        # Test 2: Fetch content for specific sections
        print("\n2️⃣ Testing content fetching...")
        try:
            # Test with example section titles (these should exist in OpenBB docs)
            test_sections = ["Copilot Basics", "OpenBB Copilot"]

            print(f"   🎯 Fetching content for: {', '.join(test_sections)}")
            content_tool_result = await client.call_tool("fetch_openbb_content", {
                "section_titles": test_sections,
                "user_query": "How do I use the copilot?"
            })
            content_result = content_tool_result.data  # Get the actual result data

            if content_result.get('success'):
                sections_found = content_result.get('sections_found', 0)
                print(f"✅ Content fetch successful: Got {sections_found} section(s)")

                # Show preview of content
                extracted_content = content_result.get('extracted_content', {})
                for title, text in extracted_content.items():
                    preview = text[:150] + "..." if len(text) > 150 else text
                    print(f"   📖 {title}: {preview}")
            else:
                print(f"❌ Content fetch failed: {content_result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"❌ Content fetching failed: {e}")

    print("\n🎉 Testing completed!")

if __name__ == "__main__":
    asyncio.run(test_server())