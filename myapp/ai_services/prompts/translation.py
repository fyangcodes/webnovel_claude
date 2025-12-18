"""
Translation prompt builder for chapter translation with entity consistency.
"""

from typing import Dict, List, Optional
from .base import BasePromptBuilder


class TranslationPromptBuilder(BasePromptBuilder):
    """
    Builds prompts for chapter translation with entity consistency.
    """

    def build(
        self,
        title: str,
        content: str,
        source_language: str,
        target_language: str,
        entities: Optional[Dict] = None,
        new_entities: Optional[Dict] = None,
        previous_chapters: Optional[List[Dict]] = None,
    ) -> str:
        """
        Build translation prompt.

        Args:
            title: Chapter title to translate
            content: Chapter content to translate
            source_language: Source language name (e.g., "Chinese")
            target_language: Target language name (e.g., "English")
            entities: Dict with 'found' (existing translations) and 'new' (need translation)
            new_entities: Dict of entities that need translation (by category)
            previous_chapters: List of dicts with chapter context

        Returns:
            Formatted prompt string
        """
        entities = entities or {}
        previous_chapters = previous_chapters or []

        prompt_parts = []

        # Task header
        prompt_parts.extend([
            "# TRANSLATION TASK",
            f"Translate this chapter from **{source_language}** to **{target_language}**.",
            "Preserve paragraph breaks and dialogue formatting.",
            "Maintain the original meaning, tone, and style.",
            "",
        ])

        # Translation Rules
        prompt_parts.extend(self.format_section("TRANSLATION RULES"))

        # Consistency
        prompt_parts.extend(self.format_subsection("CONSISTENCY", "\n".join([
            "- Use translations from the FOUND ENTITIES section if available.",
            "- Translate entities in NEW ENTITIES section consistently with the established style.",
            "- Reference the CONTEXT section to maintain consistency with previous translations and ensure story continuity.",
            "- For Chinese proper nouns (names, places), use simple Pinyin WITHOUT tone marks/diacritics (e.g., 陆飞 → Lu Fei, NOT Lù Fēi; 鲲邪 → Kun Xie, NOT Kūn Xié).",
            "- For place names, use standard English names when available (e.g., 广州 → Guangzhou, 北京 → Beijing).",
        ])))

        # Cultural considerations
        prompt_parts.extend(self.format_subsection("CULTURAL CONSIDERATIONS", "\n".join([
            f"- For idiomatic expressions or culturally specific terms, provide a natural {target_language} equivalent that conveys the same meaning.",
            "- If a term is untranslatable, use transliteration or a descriptive phrase and explain in the ENTITY_MAPPINGS section.",
        ])))

        # Formatting guidelines
        prompt_parts.extend(self.format_subsection("FORMATTING GUIDELINES", "\n".join([
            "- Preserve paragraph breaks and use quotation marks for dialogue.",
            "- Format the translated text as plain text with clear paragraph separation.",
            "- Do not add markup (e.g., HTML, Markdown) unless specified.",
        ])))

        # Error handling
        prompt_parts.extend(self.format_subsection("ERROR HANDLING", "\n".join([
            '- If a term is ambiguous, select the most contextually appropriate translation and note the choice in the ENTITY_MAPPINGS section (e.g., {"老板": "Boss (assumed to be employer)"}).',
            "- For untranslatable terms, provide a transliteration or description and explain in the ENTITY_MAPPINGS.",
            "- Use TRANSLATOR_NOTES to document assumptions, clarifications, cultural context, or translation challenges encountered.",
            "- Include any important decisions made during translation that future translators should be aware of.",
        ])))

        # Response format
        prompt_parts.extend(self.format_subsection("RESPONSE FORMAT", "\n".join([
            "**CRITICAL: You MUST respond with valid JSON only. No additional text, explanations, or markdown formatting.**",
            "",
            "Required JSON structure:",
            "{",
            '  "title": "Translated chapter title",',
            '  "content": "Full translated chapter content with preserved paragraph breaks",',
            '  "entity_mappings": {',
            '    "source_entity1": "translated_entity1",',
            '    "source_entity2": "translated_entity2"',
            "  },",
            '  "translator_notes": "Any assumptions, clarifications, or issues encountered"',
            "}",
            "",
            "Important:",
            "- Start your response with '{' and end with '}'",
            "- entity_mappings must be a JSON object (use {} if no mappings)",
            '- For Chinese names in entity_mappings, use simple Pinyin WITHOUT tone marks (e.g., "鲲邪": "Kun Xie", NOT "Kūn Xié")',
            '- translator_notes should be a string (use empty string "" if no notes)',
            "- Preserve paragraph breaks in content using \\n\\n",
        ])))

        # Entities section
        prompt_parts.extend(self.format_section("ENTITIES"))

        # Found entities (existing translations)
        found_entities = entities.get('found', '')
        if found_entities:
            prompt_parts.extend(self.format_subsection(
                "FOUND ENTITIES",
                "Previously translated entities to use:\n\n" + found_entities
            ))

        # New entities (need translation)
        new_entities_formatted = entities.get('new', '')
        if new_entities_formatted:
            prompt_parts.extend(self.format_subsection(
                "NEW ENTITIES",
                "Key entities in current chapter that need translation:\n" + new_entities_formatted
            ))
        elif found_entities:
            prompt_parts.extend(self.format_subsection(
                "NEW ENTITIES",
                "All entities in current chapter already have established translations."
            ))
        else:
            prompt_parts.extend(self.format_subsection(
                "NEW ENTITIES",
                "No entities identified in current chapter."
            ))

        # Context section (previous chapters)
        prompt_parts.extend(self.format_section("CONTEXT"))
        prompt_parts.append("**Title and summary of previous chapters**")
        prompt_parts.append("")

        if previous_chapters:
            for chapter_info in previous_chapters:
                if chapter_info.get("translated_title"):
                    title_line = (
                        f"**{chapter_info['original_title']}** → "
                        f"**{chapter_info['translated_title']}** "
                        f"(Chapter {chapter_info['number']})"
                    )
                else:
                    title_line = (
                        f"**{chapter_info['original_title']}** "
                        f"(Chapter {chapter_info['number']})"
                    )

                prompt_parts.extend([
                    title_line,
                    chapter_info.get('summary', 'No summary available'),
                    "",
                ])
        else:
            prompt_parts.extend([
                "No previous chapters available.",
                "",
            ])

        # Source text section
        prompt_parts.extend(self.format_section("SOURCE TEXT"))
        prompt_parts.extend([
            f"**Title:** {title}",
            "",
            "**Content:**",
            content,
        ])

        return self.join_parts(prompt_parts)
