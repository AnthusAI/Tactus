"""
Example data analysis tools for Tactus demonstrations.

These demonstrate working with structured data as tools.
"""


def analyze_numbers(numbers: str) -> str:
    """
    Analyze a list of numbers and return statistics.

    Args:
        numbers: Comma-separated list of numbers (e.g., "1,2,3,4,5")

    Returns:
        Statistical analysis of the numbers
    """
    try:
        # Parse numbers
        num_list = [float(n.strip()) for n in numbers.split(",")]

        if not num_list:
            return "Error: No numbers provided"

        # Calculate statistics
        count = len(num_list)
        total = sum(num_list)
        mean = total / count
        sorted_nums = sorted(num_list)

        # Median
        if count % 2 == 0:
            median = (sorted_nums[count // 2 - 1] + sorted_nums[count // 2]) / 2
        else:
            median = sorted_nums[count // 2]

        # Range
        minimum = min(num_list)
        maximum = max(num_list)
        range_val = maximum - minimum

        return f"""Statistical Analysis:
- Count: {count}
- Sum: {total:.2f}
- Mean: {mean:.2f}
- Median: {median:.2f}
- Minimum: {minimum:.2f}
- Maximum: {maximum:.2f}
- Range: {range_val:.2f}
"""
    except ValueError as e:
        return f"Error parsing numbers: {e}"


def sentiment_analysis(text: str) -> str:
    """
    Analyze sentiment of text (mock implementation).

    Args:
        text: Text to analyze

    Returns:
        Sentiment analysis results
    """
    # Simple mock sentiment based on keywords
    positive_words = ["good", "great", "excellent", "happy", "love", "wonderful", "amazing"]
    negative_words = ["bad", "terrible", "awful", "hate", "horrible", "disappointing"]

    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)

    if positive_count > negative_count:
        sentiment = "Positive"
        confidence = min(0.6 + (positive_count * 0.1), 0.95)
    elif negative_count > positive_count:
        sentiment = "Negative"
        confidence = min(0.6 + (negative_count * 0.1), 0.95)
    else:
        sentiment = "Neutral"
        confidence = 0.5

    return f"""Sentiment Analysis (Mock):
- Text: "{text[:100]}{'...' if len(text) > 100 else ''}"
- Sentiment: {sentiment}
- Confidence: {confidence:.2%}
- Positive indicators: {positive_count}
- Negative indicators: {negative_count}

Note: This is a mock implementation for demonstration purposes.
"""


def word_count(text: str) -> str:
    """
    Count words, characters, and sentences in text.

    Args:
        text: Text to analyze

    Returns:
        Text statistics
    """
    words = text.split()
    word_count = len(words)
    char_count = len(text)
    char_count_no_spaces = len(text.replace(" ", ""))

    # Simple sentence count (count periods, exclamation marks, question marks)
    sentence_endings = text.count(".") + text.count("!") + text.count("?")
    sentence_count = max(sentence_endings, 1)  # At least 1 sentence

    avg_word_length = char_count_no_spaces / word_count if word_count > 0 else 0

    return f"""Text Statistics:
- Characters: {char_count} (including spaces)
- Characters: {char_count_no_spaces} (excluding spaces)
- Words: {word_count}
- Sentences: {sentence_count}
- Average word length: {avg_word_length:.1f} characters
- Average words per sentence: {word_count / sentence_count:.1f}
"""
