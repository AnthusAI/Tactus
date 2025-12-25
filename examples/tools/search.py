"""
Example search tools for Tactus demonstrations.

These are mock tools that return fake data for testing and examples.
"""


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for information (mock implementation).

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Search results as formatted text
    """
    # Mock search results
    results = [
        f"Result 1: Information about '{query}' from example.com",
        f"Result 2: Article discussing '{query}' on news.example.org",
        f"Result 3: Research paper on '{query}' from scholar.example.edu",
    ]

    # Limit to max_results
    results = results[:max_results]

    return "\n".join(f"{i+1}. {result}" for i, result in enumerate(results))


def wikipedia_lookup(topic: str) -> str:
    """
    Look up information on Wikipedia (mock implementation).

    Args:
        topic: Topic to look up

    Returns:
        Wikipedia article summary
    """
    return f"""Wikipedia Summary: {topic}

This is a mock Wikipedia article about {topic}. In a real implementation, 
this would fetch actual content from Wikipedia's API.

Key points:
- {topic} is an important concept
- It has various applications and uses
- Further research is recommended for detailed information

For more information, visit: https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}
"""
