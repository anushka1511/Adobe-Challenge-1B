#!/usr/bin/env python3
"""
Adobe Hackathon Round 1A - PDF Outline Extractor with Multilingual Support
Enhanced solution for extracting structured outlines from PDF documents in multiple languages
"""

import os
import json
try:
    import fitz  
except ImportError:
    print("PyMuPDF not found. This will be installed in the Docker container.")
    print("For local testing, install with: pip install PyMuPDF==1.23.26")
    fitz = None
import re
import statistics
import unicodedata
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional, Set
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultilingualPDFOutlineExtractor:
    def __init__(self):
        self.font_size_threshold_factor = 1.2
        self.min_heading_chars = 2  # Reduced for CJK characters
        self.max_heading_chars = 300  # Increased for longer multilingual headings
        
        # Language-specific patterns
        self.numbering_patterns = {
            # Latin numbers
            'latin': [
                r'^\d+\.?\s+',  # 1. 2. 1 2
                r'^[IVXLCDM]+\.?\s+',  # I. II. III.
                r'^[a-zA-Z]\.?\s+',  # a. b. A. B.
                r'^\(\d+\)\s+',  # (1) (2)
                r'^\d+\.\d+\.?\s+',  # 1.1. 1.2.
            ],
            # Chinese/Japanese numbers
            'cjk': [
                r'^[一二三四五六七八九十百千万]+[、．。]\s*',  # 一、二、
                r'^第[一二三四五六七八九十百千万]+[章节條项部分]\s*',  # 第一章
                r'^[１２３４５６７８９０]+[、．。]\s*',  # Full-width numbers
                r'^\d+[、．。]\s*',  # Regular numbers with CJK punctuation
                r'^[\u3040-\u309F\u30A0-\u30FF]+\s*',  # Hiragana/Katakana patterns
            ],
            # Arabic numbers
            'arabic': [
                r'^[٠-٩]+[\.،]\s*',  # Arabic-Indic digits
                r'^[أ-ي]\s*[\.،]\s*',  # Arabic letters
            ],
            # General patterns
            'general': [
                r'^\d+\.?\s+',
                r'^\(\d+\)\s+',
                r'^[-•▪▫]\s+',  # Bullet points
                r'^[►▶→]\s+',  # Arrow bullets
            ]
        }
        
        # Script detection patterns
        self.script_patterns = {
            'latin': r'[a-zA-ZÀ-ÿ]',
            'cjk': r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uff00-\uffef]',
            'arabic': r'[\u0600-\u06ff\u0750-\u077f]',
            'cyrillic': r'[\u0400-\u04ff]',
            'devanagari': r'[\u0900-\u097f]',
            'hebrew': r'[\u0590-\u05ff]',
        }
        
        # Language-specific heading indicators
        self.heading_keywords = {
            'english': ['chapter', 'section', 'part', 'introduction', 'conclusion', 'abstract', 'summary'],
            'chinese': ['章', '节', '部分', '概述', '总结', '摘要', '引言', '结论'],
            'japanese': ['章', '節', '部', '概要', '要約', '序論', '結論', '抄録'],
            'spanish': ['capítulo', 'sección', 'parte', 'introducción', 'conclusión', 'resumen'],
            'french': ['chapitre', 'section', 'partie', 'introduction', 'conclusion', 'résumé'],
            'german': ['kapitel', 'abschnitt', 'teil', 'einführung', 'schluss', 'zusammenfassung'],
            'arabic': ['فصل', 'قسم', 'جزء', 'مقدمة', 'خاتمة', 'ملخص'],
            'russian': ['глава', 'раздел', 'часть', 'введение', 'заключение', 'резюме'],
        }

    def detect_primary_script(self, text_blocks: List[Dict]) -> str:
        """Detect the primary script/writing system used in the document"""
        script_counts = defaultdict(int)
        
        # Sample text from first 30 blocks for speed
        sample_text = ' '.join([block['text'] for block in text_blocks[:30]])
        
        for script, pattern in self.script_patterns.items():
            matches = len(re.findall(pattern, sample_text))
            script_counts[script] = matches
        
        # Return the most common script, default to latin
        if not script_counts:
            return 'latin'
        
        return max(script_counts.items(), key=lambda x: x[1])[0]

    def detect_language(self, text_blocks: List[Dict]) -> str:
        """Simple language detection based on keyword patterns"""
        sample_text = ' '.join([block['text'].lower() for block in text_blocks[:20]])
        
        language_scores = defaultdict(int)
        
        for lang, keywords in self.heading_keywords.items():
            for keyword in keywords:
                if keyword in sample_text:
                    language_scores[lang] += 1
        
        if language_scores:
            return max(language_scores.items(), key=lambda x: x[1])[0]
        
        # Fallback based on script
        script = self.detect_primary_script(text_blocks)
        if script == 'cjk':
            # Simple heuristic: if more Japanese characters, likely Japanese
            japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', sample_text))
            return 'japanese' if japanese_chars > 10 else 'chinese'
        elif script == 'arabic':
            return 'arabic'
        elif script == 'cyrillic':
            return 'russian'
        else:
            return 'english'

    def normalize_text(self, text: str) -> str:
        """Normalize text for consistent processing across languages"""
        # Normalize unicode characters
        text = unicodedata.normalize('NFKC', text)
        
        # Convert full-width characters to half-width for CJK
        text = re.sub(r'[０-９]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
        text = re.sub(r'[Ａ-Ｚａ-ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def extract_text_with_formatting(self, pdf_path: str) -> List[Dict]:
        """Extract text blocks with formatting information from PDF"""
        doc = fitz.open(pdf_path)
        text_blocks = []
        
        # Limit to 50 pages as per constraint
        max_pages = min(len(doc), 50)
        
        for page_num in range(max_pages):
            page = doc.load_page(page_num)
            blocks = page.get_text("dict")
            
            for block in blocks["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text and len(text) > 1:  # Skip single characters for speed
                                normalized_text = self.normalize_text(text)
                                if normalized_text:  # Only add non-empty normalized text
                                    text_blocks.append({
                                        "text": normalized_text,
                                        "original_text": text,
                                        "page": page_num + 1,
                                        "font_size": span["size"],
                                        "font_flags": span["flags"],
                                        "bbox": span["bbox"],
                                        "font": span["font"]
                                    })
        
        doc.close()
        return text_blocks

    def analyze_font_sizes(self, text_blocks: List[Dict]) -> Dict:
        """Analyze font sizes to determine heading thresholds"""
        font_sizes = [block["font_size"] for block in text_blocks]
        font_size_counts = Counter(font_sizes)
        
        # Get the most common font size (likely body text)
        body_font_size = font_size_counts.most_common(1)[0][0]
        
        # Calculate statistics
        unique_sizes = sorted(set(font_sizes), reverse=True)
        
        return {
            "body_font_size": body_font_size,
            "max_font_size": max(font_sizes),
            "unique_sizes": unique_sizes,
            "font_size_counts": font_size_counts
        }

    def has_numbering_pattern(self, text: str, script: str, language: str) -> bool:
        """Check if text starts with a numbering pattern appropriate for the language"""
        patterns_to_check = []
        
        # Add script-specific patterns
        if script in self.numbering_patterns:
            patterns_to_check.extend(self.numbering_patterns[script])
        
        # Add general patterns
        patterns_to_check.extend(self.numbering_patterns['general'])
        
        # Check each pattern
        for pattern in patterns_to_check:
            if re.match(pattern, text):
                return True
        
        return False

    def is_title_case_multilingual(self, text: str, script: str) -> bool:
        """Check if text is in title case, considering different scripts"""
        if script == 'latin':
            # Traditional title case check for Latin scripts
            return text.istitle() or text.isupper()
        elif script == 'cjk':
            # For CJK, check for specific formatting patterns
            # Look for mixed case in any Latin characters present
            latin_chars = re.findall(r'[a-zA-Z]+', text)
            if latin_chars:
                return any(word.istitle() or word.isupper() for word in latin_chars)
            # For pure CJK text, consider it "title case" if it's not all punctuation
            return bool(re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text))
        elif script in ['arabic', 'hebrew']:
            # Right-to-left scripts don't have traditional case
            # Check if text contains meaningful content
            return len(text.strip()) > 2
        else:
            # For other scripts, fall back to Latin rules if applicable
            return text.istitle() or text.isupper()

    def contains_heading_keywords(self, text: str, language: str) -> bool:
        """Check if text contains language-specific heading keywords"""
        text_lower = text.lower()
        
        if language in self.heading_keywords:
            return any(keyword in text_lower for keyword in self.heading_keywords[language])
        
        return False

    def calculate_text_complexity(self, text: str) -> float:
        """Calculate text complexity score for different languages"""
        # Character diversity
        unique_chars = len(set(text))
        total_chars = len(text)
        char_diversity = unique_chars / total_chars if total_chars > 0 else 0
        
        # Word count (approximate for CJK)
        if re.search(r'[\u4e00-\u9fff]', text):
            # For Chinese, each character is roughly a word
            word_count = len(re.findall(r'[\u4e00-\u9fff]', text))
        else:
            # For other languages, split by whitespace
            word_count = len(text.split())
        
        # Punctuation ratio
        punctuation_count = len(re.findall(r'[.,;:!?。、；：！？]', text))
        punct_ratio = punctuation_count / total_chars if total_chars > 0 else 0
        
        # Combine factors
        complexity = (char_diversity * 0.4) + (min(word_count / 10, 1) * 0.4) + (punct_ratio * 0.2)
        
        return complexity

    def is_likely_heading(self, text_block: Dict, font_stats: Dict, script: str, language: str) -> bool:
        """Determine if a text block is likely a heading with multilingual support"""
        text = text_block["text"]
        font_size = text_block["font_size"]
        font_flags = text_block["font_flags"]
        
        # Basic text validation with language-aware length limits
        min_chars = 1 if script == 'cjk' else self.min_heading_chars
        if len(text) < min_chars or len(text) > self.max_heading_chars:
            return False
        
        # Skip pure numbers or overly complex text
        if text.isdigit():
            return False
        
        # Calculate complexity and skip if too high (likely body text)
        complexity = self.calculate_text_complexity(text)
        if complexity > 0.8:
            return False
        
        # Font size check - should be larger than body text
        if font_size <= font_stats["body_font_size"]:
            return False
        
        # Check for bold formatting (flag 16 indicates bold)
        is_bold = font_flags & 16
        
        # Multilingual heuristics
        is_title_case = self.is_title_case_multilingual(text, script)
        has_numbering = self.has_numbering_pattern(text, script, language)
        has_keywords = self.contains_heading_keywords(text, language)
        has_colon_ending = text.endswith(':') or text.endswith('：')  # Include CJK colon
        
        # Word count check (adapted for different languages)
        if script == 'cjk':
            # For CJK, count characters instead of words
            word_count = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text))
            reasonable_length = word_count <= 20
        else:
            # For other languages, count words
            word_count = len(text.split())
            reasonable_length = word_count <= 12
        
        # Combined scoring with language-aware weights
        score = 0
        
        # Font size importance
        if font_size > font_stats["body_font_size"] * 1.3:
            score += 3
        elif font_size > font_stats["body_font_size"] * 1.1:
            score += 2
        
        # Formatting importance
        if is_bold:
            score += 2
        
        # Language-specific indicators
        if is_title_case:
            score += 2 if script == 'latin' else 1  # Less reliable for non-Latin
        
        if has_numbering:
            score += 2
        
        if has_keywords:
            score += 3
        
        if reasonable_length:
            score += 1
        
        if has_colon_ending:
            score -= 1  # Often not headings
        
        # Script-specific bonuses
        if script == 'cjk' and re.search(r'第[一二三四五六七八九十百千万]+[章节條项]', text):
            score += 2  # Strong CJK heading pattern
        
        # Threshold varies by script
        threshold = 4 if script == 'latin' else 3
        
        return score >= threshold

    def determine_heading_level(self, text_block: Dict, font_stats: Dict, script: str) -> str:
        """Determine the hierarchical level of a heading"""
        font_size = text_block["font_size"]
        text = text_block["text"]
        unique_sizes = font_stats["unique_sizes"]
        
        # Find position of this font size in the sorted list
        try:
            size_rank = unique_sizes.index(font_size)
        except ValueError:
            size_rank = len(unique_sizes) - 1
        
        # Check for explicit level indicators
        if script == 'cjk':
            if re.search(r'第[一二三四五六七八九十]+章', text):
                return "H1"  # Chapter level
            elif re.search(r'第[一二三四五六七八九十]+节', text):
                return "H2"  # Section level
        
        # Check for numbering patterns that indicate level
        if re.match(r'^\d+\s+', text) or re.match(r'^[IVXLCDM]+\.?\s+', text):
            return "H1"
        elif re.match(r'^\d+\.\d+\s+', text):
            return "H2"
        elif re.match(r'^\d+\.\d+\.\d+\s+', text):
            return "H3"
        
        # Map to heading levels based on font size ranking
        if size_rank == 0:  # Largest font
            return "H1"
        elif size_rank <= 2:  # Second or third largest
            return "H2" 
        else:  # Smaller fonts
            return "H3"

    def extract_title(self, text_blocks: List[Dict], font_stats: Dict, script: str) -> str:
        """Extract the document title with multilingual support"""
        # Look for the largest, most prominent text on first few pages
        first_page_blocks = [b for b in text_blocks if b["page"] <= 3]
        
        if not first_page_blocks:
            return "Untitled Document" if script == 'latin' else "无标题文档"
        
        # Find blocks with maximum font size
        max_font_size = max(b["font_size"] for b in first_page_blocks)
        title_candidates = [
            b for b in first_page_blocks 
            if b["font_size"] == max_font_size and len(b["text"]) > 2
        ]
        
        if title_candidates:
            # Return the first substantial text with maximum font size
            for candidate in title_candidates:
                text = candidate["text"]
                if not text.isdigit():
                    # For CJK, even single "words" can be meaningful titles
                    if script == 'cjk' or len(text.split()) >= 2:
                        return text
        
        # Fallback: look for first heading-like text
        for block in first_page_blocks[:10]:  # Check first 10 blocks
            if len(block["text"]) > 5 and not block["text"].isdigit():
                return block["text"]
        
        return "Untitled Document" if script == 'latin' else "无标题文档"

    def extract_outline(self, pdf_path: str) -> Dict:
        """Extract structured outline from PDF with multilingual support"""
        try:
            # Extract text with formatting
            text_blocks = self.extract_text_with_formatting(pdf_path)
            
            if not text_blocks:
                return {"title": "Empty Document", "outline": [], "language": "unknown", "script": "unknown"}
            
            # Detect language and script
            script = self.detect_primary_script(text_blocks)
            language = self.detect_language(text_blocks)
            
            logger.info(f"Detected script: {script}, language: {language}")
            
            # Analyze font sizes
            font_stats = self.analyze_font_sizes(text_blocks)
            
            # Extract title
            title = self.extract_title(text_blocks, font_stats, script)
            
            # Find headings
            headings = []
            seen_headings = set()  # To avoid duplicates
            
            for block in text_blocks:
                if self.is_likely_heading(block, font_stats, script, language):
                    text = block["text"]
                    
                    # Skip duplicates (case-insensitive for Latin, exact match for others)
                    if script == 'latin':
                        text_key = text.lower()
                    else:
                        text_key = text
                    
                    if text_key in seen_headings:
                        continue
                    seen_headings.add(text_key)
                    
                    level = self.determine_heading_level(block, font_stats, script)
                    
                    headings.append({
                        "level": level,
                        "text": text,
                        "page": block["page"]
                    })
            
            # Sort by page number and maintain hierarchical order
            headings.sort(key=lambda x: (x["page"], -ord(x["level"][-1])))
            
            return {
                "title": title,
                "outline": headings,
                "language": language,
                "script": script,
                "total_headings": len(headings)
            }
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {str(e)}")
            return {
                "title": "Error Processing Document", 
                "outline": [], 
                "language": "unknown", 
                "script": "unknown",
                "error": str(e)
            }

def process_pdfs():
    """Main function to process all PDFs in input directory"""
    # Check if running in Docker or locally
    if os.path.exists("/app/input"):
        input_dir = "/app/input"
        output_dir = "/app/output"
    else:
        # Local development paths
        input_dir = "./input"
        output_dir = "./output"
        print("Running in local development mode")
        print(f"Input directory: {os.path.abspath(input_dir)}")
        print(f"Output directory: {os.path.abspath(output_dir)}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create input directory if it doesn't exist (for local dev)
    os.makedirs(input_dir, exist_ok=True)
    
    # Check if input directory exists and has PDFs
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist!")
        print("Please create the input directory and add PDF files.")
        return
    
    # Process all PDF files in input directory
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in '{input_dir}'")
        print("Please add PDF files to the input directory.")
        return
    
    extractor = MultilingualPDFOutlineExtractor()
    print(f"Found {len(pdf_files)} PDF file(s): {pdf_files}")
    
    for pdf_file in pdf_files:
        try:
            pdf_path = os.path.join(input_dir, pdf_file)
            output_file = os.path.splitext(pdf_file)[0] + ".json"
            output_path = os.path.join(output_dir, output_file)
            
            logger.info(f"Processing: {pdf_file}")
            
            # Extract outline
            outline = extractor.extract_outline(pdf_path)
            
            # Save to JSON with proper Unicode handling
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(outline, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Output saved: {output_file}")
            logger.info(f"Detected language: {outline.get('language', 'unknown')}")
            logger.info(f"Detected script: {outline.get('script', 'unknown')}")
            logger.info(f"Found {outline.get('total_headings', 0)} headings")
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_file}: {str(e)}")
            # Create error output
            error_output = {
                "title": f"Error processing {pdf_file}",
                "outline": [],
                "language": "unknown",
                "script": "unknown",
                "error": str(e)
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(error_output, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    process_pdfs()