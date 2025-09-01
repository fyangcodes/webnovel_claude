import os
import logging
import re

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

try:
    from charset_normalizer import detect

    CHARSET_NORMALIZER_AVAILABLE = True
except ImportError:
    CHARSET_NORMALIZER_AVAILABLE = False
    logger.warning(
        "charset_normalizer not available, falling back to basic encoding detection"
    )


def decode_text(input_data, encoding=None, fallback_encodings=None):
    """
    Intelligently decodes bytes or str to Unicode string using charset-normalizer.

    Args:
        input_data: Bytes or string to decode
        encoding: Preferred encoding (if None, will auto-detect)
        fallback_encodings: List of encodings to try if auto-detection fails

    Returns:
        Decoded Unicode string

    Raises:
        TypeError: If input is not bytes or str
        UnicodeDecodeError: If decoding fails with all attempted encodings
    """
    if isinstance(input_data, str):
        return input_data

    if not isinstance(input_data, bytes):
        raise TypeError("Input must be bytes or str")

    # If no encoding specified, try auto-detection
    if encoding is None:
        if CHARSET_NORMALIZER_AVAILABLE:
            try:
                # Use charset-normalizer for intelligent detection
                result = detect(input_data)
                detected_encoding = result["encoding"]
                confidence = result["confidence"]

                if detected_encoding and confidence > 0.7:  # High confidence threshold
                    logger.info(
                        f"Auto-detected encoding: {detected_encoding} (confidence: {confidence:.2f})"
                    )
                    return input_data.decode(detected_encoding)
                else:
                    logger.warning(
                        f"Low confidence encoding detection: {detected_encoding} (confidence: {confidence:.2f})"
                    )
            except Exception as e:
                logger.warning(f"Charset detection failed: {str(e)}")

        # Fallback to common encodings if auto-detection fails or unavailable
        fallback_encodings = fallback_encodings or [
            "utf-8",
            "gbk",
            "gb2312",
            "gb18030",
            "big5",
            "utf-16",
            "utf-16le",
            "utf-16be",
            "latin-1",
        ]

        for enc in fallback_encodings:
            try:
                decoded = input_data.decode(enc)
                logger.info(f"Successfully decoded with {enc}")
                return decoded
            except UnicodeDecodeError:
                continue

        # If all fallbacks fail, try with error handling
        try:
            return input_data.decode("utf-8", errors="replace")
        except Exception:
            return input_data.decode("latin-1", errors="replace")

    else:
        # Use specified encoding
        try:
            return input_data.decode(encoding)
        except UnicodeDecodeError as e:
            logger.warning(f"Failed to decode with {encoding}: {str(e)}")

            # Try fallback encodings
            fallback_encodings = fallback_encodings or ["utf-8", "gbk", "latin-1"]
            for enc in fallback_encodings:
                if enc != encoding:
                    try:
                        decoded = input_data.decode(enc)
                        logger.info(
                            f"Successfully decoded with fallback encoding {enc}"
                        )
                        return decoded
                    except UnicodeDecodeError:
                        continue

            # Last resort: decode with error handling
            return input_data.decode(encoding, errors="replace")


class TextExtractor:
    """Utility class for extracting text from various file formats - MVP version"""

    @staticmethod
    def extract_text_from_file(file_obj):
        """
        Extract text from uploaded file object - MVP version supports only TXT files.

        Args:
            file_obj: Django uploaded file object

        Returns:
            Extracted text as string

        Raises:
            ValidationError: If file format is unsupported or extraction fails
        """
        if not hasattr(file_obj, "name"):
            raise ValidationError("Invalid file object")

        filename = file_obj.name
        _, ext = os.path.splitext(filename.lower())

        if ext == ".txt":
            return TextExtractor._extract_from_txt(file_obj)
        else:
            raise ValidationError(
                f"Unsupported file format: {ext}. Only TXT files are supported in this MVP version."
            )

    @staticmethod
    def _extract_from_txt(file_obj):
        """Extract text from TXT file with intelligent encoding detection"""
        try:
            content_bytes = file_obj.read()
            file_obj.seek(0)
            return decode_text(content_bytes)
        except Exception as e:
            raise ValidationError(f"Error reading TXT file: {str(e)}")


def extract_text_from_file(uploaded_file, include_chapters=False):
    """
    Main function to extract text from uploaded file - MVP version
    
    Args:
        uploaded_file: Django uploaded file object
        include_chapters: If True, also performs chapter division
        
    Returns:
        str or dict: Text content, or dict with text and chapters if include_chapters=True
    """
    text = TextExtractor.extract_text_from_file(uploaded_file)
    
    if include_chapters:
        chapters = divide_text_into_chapters(text)
        return {
            'text': text,
            'chapters': chapters,
            'word_count': len(text.split()),
            'character_count': len(text),
            'chapter_count': len(chapters)
        }
    
    return text


def _format_content_for_markdown(lines):
    """
    Format content lines for markdown compliance with proper paragraph separation.
    Handles both Chinese and Western text appropriately.
    
    Args:
        lines: List of content lines
        
    Returns:
        str: Markdown-formatted content with double newlines for paragraph separation
    """
    if not lines:
        return ""
    
    paragraphs = []
    
    for line in lines:
        line = line.strip()
        if line:  # Non-empty line
            paragraphs.append(line)
    
    # Join all lines with double newlines for proper markdown paragraph separation
    # This treats each non-empty line as a separate paragraph
    return "\n\n".join(paragraphs)


def divide_text_into_chapters(text):
    """
    Simple chapter division for MVP - uses basic pattern matching.
    
    Args:
        text: Full text content
        
    Returns:
        list: List of chapter dictionaries with title and markdown-compliant content
    """
    chapters = []
    
    # Common chapter patterns
    chapter_patterns = [
        r"^第[\d一二三四五六七八九十百千万零壹贰叁肆伍陆柒捌玖拾佰仟萬]+章.*$",
        r"^\d+\.\s+.*$",
        r"^Chapter\s+\d+.*$",
        r"^[IVX]+\.\s+.*$",
    ]
    
    # Try to find chapters using patterns
    lines = text.split("\n")
    current_chapter = None
    current_content = []
    chapter_number = 1
    
    for line in lines:
        line = line.strip()
        
        # Check if this line matches any chapter pattern
        is_chapter_start = any(
            re.match(pattern, line, re.IGNORECASE | re.MULTILINE)
            for pattern in chapter_patterns
        )
        
        if is_chapter_start:
            # Save previous chapter if it exists
            if current_chapter is not None:
                formatted_content = _format_content_for_markdown(current_content)
                chapters.append(
                    {
                        "title": current_chapter,
                        "content": formatted_content,
                        "chapter_number": len(chapters) + 1,
                        "word_count": len(formatted_content.split()),
                        "character_count": len(formatted_content),
                    }
                )
            
            # Start new chapter
            current_chapter = line if line else f"Chapter {chapter_number}"
            current_content = []
            chapter_number += 1
        else:
            # Add line to current chapter content
            current_content.append(line)
    
    # Add the last chapter
    if current_chapter is not None:
        formatted_content = _format_content_for_markdown(current_content)
        chapters.append(
            {
                "title": current_chapter,
                "content": formatted_content,
                "chapter_number": len(chapters) + 1,
                "word_count": len(formatted_content.split()),
                "character_count": len(formatted_content),
            }
        )
    
    # If no chapters were found, create a single chapter
    if not chapters:
        # Format the entire text for markdown compliance
        formatted_text = _format_content_for_markdown(text.split('\n'))
        chapters = [
            {
                "title": "Full Text",
                "content": formatted_text,
                "chapter_number": 1,
                "word_count": len(formatted_text.split()),
                "character_count": len(formatted_text),
            }
        ]
    
    return chapters
