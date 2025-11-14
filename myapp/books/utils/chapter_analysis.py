"""
AI-powered chapter analysis service for entity extraction and summarization.
"""

import json
import logging
from django.conf import settings
from django.core.exceptions import ValidationError

from .base_ai_service import BaseAIService

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Base exception for chapter analysis errors"""
    pass


class APIError(AnalysisError):
    """OpenAI API related error"""
    pass


class ChapterAnalysisService(BaseAIService):
    """AI-based entity extraction service for chapter analysis"""

    # Settings configuration
    MODEL_SETTING_NAME = 'ANALYSIS_MODEL'
    MAX_TOKENS_SETTING_NAME = 'ANALYSIS_MAX_TOKENS'
    TEMPERATURE_SETTING_NAME = 'ANALYSIS_TEMPERATURE'

    def __init__(self):
        """Initialize the chapter analysis service"""
        try:
            super().__init__()
        except ValueError as e:
            raise APIError(str(e))

    def extract_entities_and_summary(self, content, language_code="zh"):
        """
        Extract entities and summary from chapter content using AI

        Args:
            content (str): Chapter content to analyze
            language_code (str): Source language code (default: zh for Chinese)

        Returns:
            dict: Extracted entities and summary with keys:
                - characters: list of character names
                - places: list of place names
                - terms: list of special terms
                - summary: brief chapter summary
        """
        try:
            prompt = self._build_extraction_prompt(content, language_code)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},  # Force JSON response
            )

            response_text = response.choices[0].message.content.strip()
            logger.debug(f"Raw extraction response: {response_text}")

            # Parse JSON response
            try:
                # Clean the response text
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                self._validate_extraction_result(result)

                # Clean entity names (safety net to remove decorative punctuation)
                result = self._clean_entity_names(result)

                logger.info(
                    f"Successfully extracted entities: {len(result.get('characters', []))} chars, "
                    f"{len(result.get('places', []))} places, {len(result.get('terms', []))} terms"
                )
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse extraction JSON: {e}")
                logger.error(f"Raw response: {response_text}")
                return self._get_fallback_result(content)

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._get_fallback_result(content)

    def _build_extraction_prompt(self, content, language_code):
        """Build the AI prompt for entity extraction"""
        from books.models import Language

        try:
            language = Language.objects.get(code=language_code)
            language_name = language.name
        except Language.DoesNotExist:
            language_name = language_code

        prompt_parts = []
        prompt_parts.extend(
            [
                f"You are a text analysis expert. Analyze the provided {language_name} text and extract key entities for translation consistency. You must respond with valid JSON only—no additional text, explanations, prefixes, or logs. Start your response with '{{' and end with '}}'.",
                "",
                "Your task:",
                "1. Extract CHARACTER names: Only unique proper names of people or beings. Do not include professions, descriptors or generic terms.",
                "2. Extract PLACE names: Only specific named locations, buildings, or realms. Do not include generic places.",
                "3. Extract TERM names: Only special concepts, techniques, items, or titles that need consistent translation. Exclude common words.",
                f"4. Create a brief summary: 2-3 sentences max, in {language_name}, covering the chapter's content and key events.",
                "",
                "Rules:",
                "- Only extract proper nouns and named entities that appear in the text.",
                "- Exclude common words, generic terms, and descriptors.",
                "- Focus on entities central to the plot that need consistent translation.",
                "- Limit each category to the top 10 most important entities (or fewer if not applicable).",
                "- Prioritize entities mentioned multiple times.",
                "",
                "IMPORTANT - Clean Entity Names:",
                "- Remove ALL decorative punctuation and wrapper characters from entity names",
                "- Chinese book/document titles: Extract WITHOUT 《》 markers (e.g., extract '朱阳策' NOT '《朱阳策》')",
                "- Quotation marks: Extract WITHOUT \" or ' marks",
                "- Brackets/parentheses: Extract WITHOUT ( ), [ ], { }, 「」, 『』",
                "- Extract only the core entity name itself",
                "- Example: If text contains '《沧海拾遗》', extract as '沧海拾遗'",
                "- Example: If text contains '\"John Smith\"', extract as 'John Smith'",
                "",
                "You must respond with valid JSON only. No additional text or explanations.",
                "",
                "Required JSON format:",
                "{",
                '"characters": ["name1", "name2"],',
                '"places": ["place1", "place2"],',
                '"terms": ["term1", "term2"],',
                f'"summary": "Brief summary in {language_name}"',
                "}",
                "",
                "Text to analyze:",
                f"{content}",
            ]
        )

        return "\n".join(prompt_parts)

    def _clean_json_response(self, response_text):
        """Clean and prepare JSON response for parsing"""
        # Remove any markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        # Strip whitespace
        response_text = response_text.strip()

        # Try to find JSON object bounds if there's extra text
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            response_text = response_text[start_idx : end_idx + 1]

        return response_text

    def _validate_extraction_result(self, result):
        """Validate the extraction result structure"""
        required_keys = ["characters", "places", "terms", "summary"]

        for key in required_keys:
            if key not in result:
                raise ValidationError(f"Missing required key: {key}")

        # Ensure lists are actually lists
        for key in ["characters", "places", "terms"]:
            if not isinstance(result[key], list):
                raise ValidationError(f"{key} must be a list")

        # Ensure summary is string
        if not isinstance(result["summary"], str):
            raise ValidationError("summary must be a string")

    def _clean_entity_names(self, result):
        """Clean entity names by removing decorative punctuation (safety net)"""
        # Decorative characters to remove
        decorative_chars = {
            '《': '', '》': '',  # Chinese book title markers
            '「': '', '」': '',  # Japanese quotes
            '『': '', '』': '',  # Japanese double quotes
            '"': '', '"': '',    # Smart quotes
            '"': '', "'": '',    # Regular quotes
        }

        for category in ["characters", "places", "terms"]:
            if category in result and isinstance(result[category], list):
                cleaned = []
                for entity in result[category]:
                    if isinstance(entity, str):
                        # Remove decorative characters
                        cleaned_entity = entity
                        for old, new in decorative_chars.items():
                            cleaned_entity = cleaned_entity.replace(old, new)

                        # Strip whitespace
                        cleaned_entity = cleaned_entity.strip()

                        # Only add if non-empty after cleaning
                        if cleaned_entity:
                            cleaned.append(cleaned_entity)

                result[category] = cleaned

        return result

    def _get_fallback_result(self, content):
        """Return fallback result when AI extraction fails"""
        return {
            "characters": [],
            "places": [],
            "terms": [],
            "summary": content[:200] + "..." if len(content) > 200 else content,
        }
