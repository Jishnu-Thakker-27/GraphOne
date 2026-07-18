"""
Content Normalizer.

Strips boilerplate, ads, scripts, navigation, headers, and footers from HTML
to extract only meaningful, dense text, minimizing LLM token cost.
"""

import re
from bs4 import BeautifulSoup

class ContentNormalizer:
    """Cleans raw HTML/XML content to extract core semantically dense text."""

    @staticmethod
    def normalize_html(html_content: str) -> str:
        """
        Removes scripts, styles, navigation, headers, footers, and other boilerplate.
        Returns a cleaned, compact text string.
        """
        if not html_content or html_content.strip().startswith("ERROR:"):
            return html_content

        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Decompose standard non-content HTML elements
        ignore_tags = [
            "script", "style", "noscript", "iframe", "svg", "canvas",
            "header", "footer", "nav", "aside", "form", "button",
            "select", "option", "textarea", "dialog", "menu", "head",
            "footer", "nav", "aside"
        ]
        for tag in soup(ignore_tags):
            tag.decompose()

        # 2. Decompose container elements matching common ads/navigation/cookie banner selectors
        boilerplate_patterns = re.compile(
            r"cookie|consent|banner|menu|nav|footer|sidebar|ads|ad-box|social-share|navbar|head-bar",
            re.IGNORECASE
        )
        for element in soup.find_all(attrs={"class": boilerplate_patterns}):
            element.decompose()
        for element in soup.find_all(attrs={"id": boilerplate_patterns}):
            element.decompose()

        # 3. Extract clean text
        text = soup.get_text(separator="\n")

        # 4. Clean whitespace and filter line length
        cleaned_lines = []
        for line in text.splitlines():
            line_str = line.strip()
            # Skip empty lines or single-character noise (like commas, dots left over)
            if len(line_str) > 1:
                cleaned_lines.append(line_str)

        # Re-join and clean up excessive newlines
        cleaned_text = "\n".join(cleaned_lines)
        cleaned_text = re.sub(r"\n+", "\n", cleaned_text)

        return cleaned_text.strip()

    @classmethod
    def normalize(cls, content: str, content_type: str = "HTML") -> str:
        """Entrypoint for normalizing raw text based on source content type."""
        if content_type.upper() == "HTML":
            return cls.normalize_html(content)
        # Returns XML or text formats trimmed but otherwise raw
        return content.strip()
