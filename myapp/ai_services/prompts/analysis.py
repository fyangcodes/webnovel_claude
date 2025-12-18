"""
Analysis prompt builder for entity extraction and summarization.
"""

from typing import List
from .base import BasePromptBuilder


class AnalysisPromptBuilder(BasePromptBuilder):
    """
    Builds prompts for chapter analysis (entity extraction and summarization).
    """

    def build(self, content: str, language_code: str = "zh") -> str:
        """
        Build analysis prompt for entity extraction.

        Args:
            content: Chapter content to analyze
            language_code: Source language code

        Returns:
            Formatted prompt string
        """
        # Map language codes to names
        language_names = {
            "zh": "Chinese",
            "en": "English",
            "ja": "Japanese",
            "ko": "Korean",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
        }
        language_name = language_names.get(language_code, language_code)

        prompt_parts = []

        # Introduction
        prompt_parts.extend([
            f"You are a text analysis expert. Analyze the provided {language_name} text and extract key entities for translation consistency. You must respond with valid JSON only—no additional text, explanations, prefixes, or logs. Start your response with '{{' and end with '}}'.",
            "",
        ])

        # Task description
        prompt_parts.extend(self.format_section("Your Task", "\n".join([
            "1. Extract CHARACTER names: Only unique proper names of people or beings. Do not include professions, descriptors or generic terms.",
            "2. Extract PLACE names: Only specific named locations, buildings, or realms. Do not include generic places.",
            "3. Extract TERM names: Only special concepts, techniques, items, or titles that need consistent translation. Exclude common words.",
            f"4. Create a brief summary: 2-3 sentences max, in {language_name}, covering the chapter's content and key events.",
        ])))

        # Rules
        prompt_parts.extend(self.format_section("Rules", "\n".join([
            "- Only extract proper nouns and named entities that appear in the text.",
            "- Exclude common words, generic terms, and descriptors.",
            "- Focus on entities central to the plot that need consistent translation.",
            "- Limit each category to the top 10 most important entities (or fewer if not applicable).",
            "- Prioritize entities mentioned multiple times.",
        ])))

        # Clean entity names section
        prompt_parts.extend(self.format_section("IMPORTANT - Clean Entity Names", "\n".join([
            "- Remove ALL decorative punctuation and wrapper characters from entity names",
            "- Chinese book/document titles: Extract WITHOUT 《》 markers (e.g., extract '朱阳策' NOT '《朱阳策》')",
            '- Quotation marks: Extract WITHOUT " or \' marks',
            "- Brackets/parentheses: Extract WITHOUT ( ), [ ], { }, 「」, 『』",
            "- Extract only the core entity name itself",
            "- Example: If text contains '《沧海拾遗》', extract as '沧海拾遗'",
            '- Example: If text contains \'"John Smith"\', extract as \'John Smith\'',
        ])))

        # Response format
        prompt_parts.extend(self.format_section("Required JSON Format", "\n".join([
            "You must respond with valid JSON only. No additional text or explanations.",
            "",
            "{",
            '  "characters": ["name1", "name2"],',
            '  "places": ["place1", "place2"],',
            '  "terms": ["term1", "term2"],',
            f'  "summary": "Brief summary in {language_name}"',
            "}",
        ])))

        # Text to analyze
        prompt_parts.extend(self.format_section("Text to Analyze", content))

        return self.join_parts(prompt_parts)
