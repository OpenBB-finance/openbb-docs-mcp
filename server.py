"""
OpenBB Documentation MCP Server

This server exposes OpenBB documentation as structured, callable tools through the Model Context Protocol.
It provides two main functionalities:
1. Discovering available documentation sections from the table of contents
2. Fetching specific documentation content from the full docs file
"""

import os
import re
import logging
import traceback
from typing import List, Dict, Any, Optional
import httpx
import uvicorn
from fastmcp import FastMCP
from fastapi.middleware.cors import CORSMiddleware

# Configure logging to only show errors
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="OpenBB Docs Server",
    instructions="""
    This server provides access to OpenBB Workspace documentation.
    Use 'discover_openbb_sections' to find available documentation sections,
    then use 'fetch_openbb_content' to retrieve specific section content.
    """
)

# Get the Starlette app and add CORS middleware
# Use http_app() with 'http' transport (recommended for production)
app = mcp.http_app()

origins = [
    "https://pro.openbb.co",
    "https://pro.openbb.dev",
    "http://localhost:1420"
]

# Add CORS middleware with proper header exposure for MCP session management
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Configure this more restrictively in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id", "mcp-protocol-version"],  # Allow client to read session ID
    max_age=86400,
)

# URLs for OpenBB documentation
TOC_URL = "https://docs.openbb.co/workspace/llms.txt"
FULL_DOCS_URL = "https://docs.openbb.co/workspace/llms-full.txt"


@mcp.tool()
async def identify_openbb_docs_sections(user_query: str) -> Dict[str, Any]:
    """
    Identify the most relevant OpenBB documentation sections based on a user's query.

    This tool provides the COMPLETE table of contents from OpenBB documentation and expects
    the LLM to analyze it intelligently to select the most relevant sections.

    RETURN VALUE:
    Returns a dictionary containing:
    - raw_toc_content: The complete table of contents with all sections and descriptions
    - section_urls: A mapping of section titles to their URLs
    - query: The original user query for reference

    ANALYSIS INSTRUCTIONS FOR THE LLM:
    1. **Carefully read** both the title AND description of each section in raw_toc_content. 
       Titles give primary signals. Descriptions clarify scope (setup vs. concept vs. workflow vs. integration).
    2. **Understand intent**: Match the semantic meaning of the user's query, not just keywords
    3. **Evaluate relevance**: Consider which sections would most likely contain the information needed
    4. **Prioritize quality**: Only select sections that are truly relevant to the query
    5. **Rank by relevance**: Select up to 3 sections, ordered from most to least relevant
    6. **Be selective**: If no sections are genuinely relevant, return an empty list - do NOT force matches

    SELECTION CRITERIA:
    - Does the section title/description directly address the user's question?
    - Would this section likely contain detailed information about the query topic?
    - Is this section more relevant than other available options?
    - Consider both exact matches AND semantically related topics

    NEXT STEPS:
    After analyzing the TOC, call fetch_openbb_content with:
    - A list of up to 3 exact section titles (copy them exactly as they appear in raw_toc_content)
    - The original user_query
    - Maximum 3 sections (can be 0, 1, 2, or 3), ranked by relevance
    - Empty list if truly no relevant sections exist

    Args:
        user_query: The user's question or information request
    
    Returns:
        Dict with 'success', 'query', 'raw_toc_content', and 'section_urls' fields
    """
    try:
        result = await _identify_sections_async(user_query)
        return result
    except Exception as e:
        logger.error(f"[TOOL ERROR] identify_openbb_docs_sections failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise


@mcp.tool()
async def fetch_openbb_content(section_titles: List[str], user_query: str) -> Dict[str, Any]:
    """

    Fetch specific documentation content from OpenBB docs based on section titles.

    You MUST call 'identify_openbb_docs_sections' first to obtain the exact section titles
    before calling this tool. Use the section titles identified from that process.

    Workflow:
    1. Call 'identify_openbb_docs_sections' with the user's query
    2. The LLM analyzes the raw TOC and identifies up to 3 relevant section titles
    3. Pass those exact section titles AND the original user query to this function
    4. Use the returned content to answer the user's question

    RETURN VALUE:
    Returns a dictionary containing:
    - extracted_content: Dict mapping section titles to their content and URLs
    - user_query: The original user query
    - sections_found: Number of sections successfully extracted

    RESPONSE GUIDELINES FOR THE LLM:
    
    1. Answer only if relevant:
       - Use only information from extracted_content, DO NOT used data where you were previously trained on.
       - If no sections are relevant (low similarity or no direct keyword overlap), respond:
         "No relevant documentation found for this topic. Please contact support@openbb.co for further assistance."
         (This is the only case where support should be mentioned.)
       - Provide answers to what is asked only (e.g. if users ask for Installation guideline, please don't provide detailed related to its features)
    
    2. Prioritize by Section Name:
       - Strongly weight sections whose titles closely or exactly match the query 
         (e.g. query = "Data integration" → section = "Data Integration")
       - Prefer precision over coverage — only merge multiple sections if they directly 
         address the same concept or function
    
    3. Detailed instructions and structured output:
       - Begin with a clear, actionable explanation or steps
       - Provide detailed and elaborated instructions, not just 2-3 sentences
       - Avoid unnecessary preambles or repetition of the user query
       - Keep tone factual, clean, and instructional
       - When users ask questions starting with “How to…” or “Show me…”, you must provide step-by-step instructions — not just refer them to a documentation URL.
       - Your responses should be comprehensive and actionable, allowing users to complete the task solely by following your answer, without needing to open external links.
       - If the extracted_content includes examples or code snippets, please return it to illustrate your explanation.
       - Identify code blocks by triple backticks (```) followed optionally by a language tag, e.g., ```python. Please make sure to return IT!!
       - Prioritize providing examples: code block, screenshots, and actual examples!
       - Avoid giving only brief bullet points. Instead, write clear, sequential steps that are easy to follow, with enough context and explanation for users to understand why each step is necessary.
    
    4. Citations and URLs:
       - If documentation is clearly relevant and you're referencing it, include the 
         exact section URL in this format: Section Name: [URL]
       - If you can confidently answer without direct citation (content is already inline), 
         you don't need to cite it
       - Do not include any "References" list at the end
    
    5. Exactness:
       - Preserve all parameter names, options, and syntax exactly as shown in docs
       - Use code blocks for commands, configuration, or API syntax (specify language)
       - Quote exact phrases when necessary
    
    6. Language:
       - Respond in the same language as the user's query
       - Maintain a professional and neutral tone
    
    7. Output format:
       - Headings: use for subtopics or feature names
       - Bullets: for options, parameters, or steps
       - Code blocks: for syntax or examples
       - Inline URLs: only when you actually reference the source
       - Avoid filler like "according to the documentation" or "as stated above"

    Args:
        section_titles: List of exact section titles identified from 'identify_openbb_docs_sections'
        user_query: The original user's question/query
    
    Returns:
        Dict with 'success', 'user_query', 'extracted_content', and 'sections_found' fields
    """
    try:
        result = await _fetch_content_async(section_titles, user_query)
        return result
    except Exception as e:
        logger.error(f"[TOOL ERROR] fetch_openbb_content failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise


async def _identify_sections_async(user_query: str) -> Dict[str, Any]:
    """
    Async implementation for identifying relevant sections.
    Returns the raw TOC content for LLM to analyze and select relevant sections.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(TOC_URL)
            response.raise_for_status()
            toc_content = response.text

        # Parse TOC to extract section titles and URLs
        parsed_sections = _parse_toc(toc_content)

        # Create a mapping of section titles to URLs for easy lookup
        section_url_map = {
            section["title"]: section["url"]
            for section in parsed_sections
        }

        return {
            "success": True,
            "query": user_query,
            "raw_toc_content": toc_content,
            "section_urls": section_url_map
        }

    except Exception as e:
        logger.error(f"ERROR in _identify_sections_async: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "query": user_query,
            "raw_toc_content": ""
        }


async def _fetch_content_async(section_titles: List[str], user_query: str) -> Dict[str, Any]:
    """
    Fetch full documentation and extract only the relevant sections.
    Returns extracted content with the original user query and instructions for the LLM.
    """
    try:
        # Fetch both the TOC (for URLs) and full documentation
        async with httpx.AsyncClient(timeout=60.0) as client:
            toc_response = await client.get(TOC_URL)
            toc_response.raise_for_status()
            toc_content = toc_response.text

            docs_response = await client.get(FULL_DOCS_URL)
            docs_response.raise_for_status()
            full_docs = docs_response.text

        # Parse TOC to get section URLs
        parsed_sections = _parse_toc(toc_content)
        section_url_map = {
            section["title"]: section["url"]
            for section in parsed_sections
        }

        # Extract only the relevant sections from the full docs
        # This prevents sending the entire docs which would exceed context limits
        content_sections = _extract_sections_from_docs(full_docs, section_titles)

        # Build section content with URLs
        sections_with_urls = {}
        for title, content in content_sections.items():
            url = section_url_map.get(title, "URL not found")
            sections_with_urls[title] = {
                "url": url,
                "content": content
            }

        return {
            "success": True,
            "user_query": user_query,
            "extracted_content": sections_with_urls,
            "sections_found": len(content_sections)
        }

    except Exception as e:
        logger.error(f"ERROR in _fetch_content_async: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "user_query": user_query,
            "extracted_content": {}
        }


def _parse_toc(toc_content: str, query: Optional[str] = None) -> List[Dict[str, str]]:
    """Parse the table of contents and extract section information."""
    sections = []
    lines = toc_content.strip().split('\n')

    current_category = ""

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Detect category headers (lines that don't start with - or *)
        if not line.startswith(('-', '*', '1.', '2.', '3.', '4.', '5.')):
            # Check if it's a main section header
            if line and not line.startswith('#') and not line.startswith('http'):
                current_category = line.replace('#', '').strip()
            continue

        # Extract markdown links
        link_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', line)
        if link_match:
            title = link_match.group(1).strip()
            url = link_match.group(2).strip()

            # Filter by query if provided
            if query and query.lower() not in title.lower() and query.lower() not in current_category.lower():
                continue

            sections.append({
                "title": title,
                "category": current_category,
                "url": url,
                "description": f"{current_category}: {title}" if current_category else title
            })

    return sections


def _extract_sections_from_docs(full_docs: str, section_titles: List[str]) -> Dict[str, str]:
    """Extract specific sections from the full documentation."""
    content_sections = {}

    for title in section_titles:
        try:
            section_content = _find_section_content(full_docs, title)
            if section_content:
                content_sections[title] = section_content
            else:
                content_sections[title] = f"Section '{title}' not found in documentation."
        except Exception as e:
            logger.error(f"Error extracting section '{title}': {str(e)}")
            logger.error(traceback.format_exc())
            content_sections[title] = f"Error extracting section '{title}': {str(e)}"

    return content_sections


def _find_section_content(full_docs: str, title: str) -> Optional[str]:
    """Find content for a specific section title in the full docs.

    Sections are in YAML frontmatter format:
    ---
    title: Section Name
    sidebar_position: 1
    ---
    content here
    ---

    ---
    title: Next Section
    ---
    """
    lines = full_docs.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for "title: <title>" pattern
        if line.lower().startswith('title:'):
            # Extract the title from this line
            section_title = line[6:].strip()  # Remove "title:" prefix

            # Check if this matches our search title (case-insensitive)
            if section_title.lower() == title.lower():
                # Found it! Skip the frontmatter first
                j = i + 1

                # Skip until we find the closing --- of frontmatter
                while j < len(lines) and lines[j].strip() != '---':
                    j += 1

                # Now j is at the closing ---, move past it
                j += 1

                # Collect content until we hit the next section (--- followed by blank line and ---)
                content_lines = []
                while j < len(lines):
                    # Check if we're at the start of next section
                    # Pattern is: ---\n\n--- or ---\n---
                    if (lines[j].strip() == '---' and
                        j + 1 < len(lines) and
                        (lines[j + 1].strip() == '---' or lines[j + 1].strip() == '')):
                        break

                    content_lines.append(lines[j])
                    j += 1

                return '\n'.join(content_lines)

        i += 1

    return None


if __name__ == "__main__":
    # Use PORT environment variable
    port = int(os.environ.get("PORT", 8000))

    print("=" * 80)
    print("Starting FastMCP OpenBB Docs server...")
    print(f"MCP server will be available at: http://0.0.0.0:{port}/mcp")
    print("Tools available: identify_openbb_docs_sections, fetch_openbb_content")
    print("=" * 80)

    # Run the MCP server with HTTP transport using uvicorn
    # Set log_level to "error" to only show errors
    uvicorn.run(
        app,
        host="0.0.0.0",  # Listen on all interfaces for containerized deployment
        port=port,
        log_level="error"
    )
