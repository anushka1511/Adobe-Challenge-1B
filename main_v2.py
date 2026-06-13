import os
import json
import time
import requests
import PyPDF2
import re
from typing import Dict, List, Any
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFParser:
    """
    Handles robust extraction of content and sections from PDF files.
    This version includes multiple fallback strategies for section detection.
    """
    def _get_page_number(self, pdf_reader, page_object):
        try:
            return pdf_reader.get_page_number(page_object) + 1
        except Exception:
            for i, page in enumerate(pdf_reader.pages):
                if page.get_object() == page_object.get_object():
                    return i + 1
        return None

    def _is_heading(self, line: str) -> bool:
        """Determines if a line of text is likely a heading."""
        line = line.strip()
        if not line or len(line) > 150:
            return False
        # Ends with no punctuation, is title case, short
        if not line.endswith(('.', ',', ';')) and line.istitle() and len(line.split()) < 10:
            return True
        # Is all caps, short
        if line.isupper() and len(line.split()) < 8:
            return True
        # Starts with a number pattern like "1." or "1.1"
        if re.match(r'^\d+(\.\d+)*\.\s', line):
            return True
        return False

    def extract_sections(self, pdf_reader, pages_content) -> List[Dict]:
        sections = []
        # --- METHOD 1: Use the PDF Outline (Most Reliable) ---
        if pdf_reader.outline:
            logger.info("Strategy 1: Found PDF outline. Extracting sections from bookmarks.")
            bookmarks = self._flatten_outline(pdf_reader.outline)
            for i, bookmark in enumerate(bookmarks):
                try:
                    page_num = self._get_page_number(pdf_reader, bookmark.page)
                    if not page_num: continue
                    
                    content = self._get_section_content(i, page_num, bookmarks, pages_content, pdf_reader)
                    if len(content.strip()) > 100:
                        sections.append({'text': bookmark.title, 'page': page_num, 'content': content})
                except Exception: continue
        
        # --- METHOD 2: Fallback to text-based heading detection ---
        if not sections:
            logger.warning("Strategy 2: No usable outline. Falling back to text-based heading detection.")
            current_section = None
            for page_data in pages_content:
                lines = page_data['text'].split('\n')
                for line in lines:
                    if self._is_heading(line):
                        if current_section: sections.append(current_section)
                        current_section = {'text': line.strip(), 'page': page_data['page'], 'content': ''}
                    elif current_section:
                        current_section['content'] += line + '\n'
            if current_section: sections.append(current_section)
        
        # --- METHOD 3: Final fallback to page-by-page ---
        if not sections:
            logger.error("Strategy 3: No headings found. Treating each page as a section.")
            for page_data in pages_content:
                if page_data['text'] and len(page_data['text'].strip()) > 100:
                    sections.append({'text': f"Page {page_data['page']} - Overview", 'page': page_data['page'], 'content': page_data['text']})
        
        # Filter out sections with very little content
        return [s for s in sections if s.get('content') and len(s['content'].strip()) > 200]

    def _flatten_outline(self, outline_items):
        flat_list = []
        for item in outline_items:
            if isinstance(item, list): flat_list.extend(self._flatten_outline(item))
            else: flat_list.append(item)
        return flat_list
        
    def _get_section_content(self, current_index, current_page_num, bookmarks, pages_content, pdf_reader):
        start_page_idx = current_page_num - 1
        end_page_idx = len(pdf_reader.pages)
        if current_index + 1 < len(bookmarks):
            next_bookmark = bookmarks[current_index + 1]
            next_page_num = self._get_page_number(pdf_reader, next_bookmark.page)
            if next_page_num and next_page_num > current_page_num:
                end_page_idx = next_page_num - 1
        
        content = ""
        for page_idx in range(start_page_idx, end_page_idx):
            if page_idx < len(pages_content):
                content += pages_content[page_idx]['text'] + "\n"
        return content.strip()

    def extract_title(self, pdf_reader) -> str:
        # Same as before, it's good.
        if pdf_reader.metadata and pdf_reader.metadata.get('/Title'):
            return str(pdf_reader.metadata['/Title'])
        if pdf_reader.pages:
            first_page_text = pdf_reader.pages[0].extract_text()
            if first_page_text:
                lines = first_page_text.split('\n')
                for line in lines[:5]:
                    if line.strip() and len(line.strip()) > 5:
                        return line.strip()
        return "Untitled Document"

    def extract_content(self, pdf_path: str) -> Dict[str, Any]:
        # Same as before, it's good.
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                if pdf_reader.is_encrypted:
                    logger.warning(f"Skipping encrypted PDF: {pdf_path}")
                    return None

                title = self.extract_title(pdf_reader)
                pages_content = [{'page': i+1, 'text': p.extract_text() or ""} for i, p in enumerate(pdf_reader.pages)]
                sections = self.extract_sections(pdf_reader, pages_content)
                
                return {'title': title, 'total_pages': len(pdf_reader.pages), 'sections': sections}
        except Exception as e:
            logger.error(f"Fatal error parsing PDF {pdf_path}: {e}", exc_info=True)
            return None


class OllamaClient:
    # This class is good, no changes needed.
    def __init__(self, model="tinyllama", host="http://localhost:11434"):
        self.model = model
        self.host = host
        self.api_url = f"{host}/api/generate"
        
    def is_ready(self) -> bool:
        try:
            response = requests.get(f"{self.host}/", timeout=5)
            return response.status_code == 200
        except requests.ConnectionError:
            return False
    
    def generate(self, prompt: str, max_tokens: int) -> str:
        try:
            payload = {
                "model": self.model, "prompt": prompt, "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.1, "top_p": 0.9}
            }
            response = requests.post(self.api_url, json=payload, timeout=90)
            response.raise_for_status()
            return response.json().get('response', '').strip()
        except requests.RequestException as e:
            logger.error(f"Ollama API request failed: {e}")
            return ""

class PersonaDrivenAnalyzer:
    def __init__(self):
        self.pdf_parser = PDFParser()
        self.ollama = OllamaClient()
        # Rest of __init__ is good, no changes needed.
        max_retries = 5
        for i in range(max_retries):
            if self.ollama.is_ready():
                logger.info("Ollama service is ready.")
                break
            logger.warning(f"Waiting for Ollama service... ({i+1}/{max_retries})")
            time.sleep(3)
        else:
            raise ConnectionError("Ollama service not available after multiple retries.")
    
    def analyze_section_relevance(self, section: Dict, persona: Dict, job: Dict) -> float:
        # This prompt is good, no changes needed.
        prompt = f"""You are an expert analyst. Your task is to rate the relevance of a document section for a specific user.

**USER PROFILE:**
- **Role:** {persona.get('role')}
- **Goal:** {job.get('task')}

**DOCUMENT SECTION TO EVALUATE:**
- **Title:** "{section.get('text')}"
- **Content Summary:** "{section.get('content', '')[:800].strip()}..."

**INSTRUCTIONS:**
1.  **Reasoning:** First, in a short sentence, explain your reasoning. Think step-by-step: Does this section directly help the user achieve their specific goal? For a "Travel Planner" planning a trip for "college friends," sections on nightlife, budget activities, and logistics are highly relevant. A section on ancient history is not.
2.  **Scoring:** Then, on a new line, give a relevance score from 1.0 (not relevant) to 10.0 (critically important).

**EXAMPLE:**
Reasoning: This section on nightlife and entertainment is highly relevant for planning a trip for college friends.
Score: 9.5

**YOUR ANALYSIS:**
"""
        response = self.ollama.generate(prompt, max_tokens=150)
        return self.parse_relevance_score(response)
    
    def parse_relevance_score(self, response: str) -> float:
        # This method is good, no changes needed.
        try:
            score_match = re.search(r'Score:\s*(\d+(?:\.\d+)?)', response, re.IGNORECASE)
            if score_match: return float(score_match.group(1))
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', response)
            if numbers: return float(numbers[-1])
            return 1.0
        except Exception: return 1.0

    def extract_key_insights(self, section: Dict, persona: Dict, job: Dict) -> str:
        # A refined prompt for better summaries.
        prompt = f"""You are an expert travel writer. Your task is to create a summary of the provided text for a user.

**User Persona:** {persona.get('role')}
**User's Goal:** {job.get('task')}

**SOURCE TEXT:**
---
{section.get('content', '')[:2500]}
---

**Your Task:**
Synthesize the most important information from the source text into a single, cohesive, and helpful paragraph. Your summary must be written in a narrative style.
- Focus exclusively on details that help the user achieve their goal (e.g., for college friends, mention nightlife, activities, budget-friendly options, and places to see).
- Extract and weave in specific names of places, activities, or practical tips.
- **Strictly prohibit** the use of bullet points, numbered lists, or any formatting that breaks the paragraph flow.
- The entire response should be one fluid paragraph. Do not add introductory phrases like "As a helpful AI...". Start directly with the information.
- If the source text is not relevant to the user's task, simply write: "This section does not provide relevant details for the specified task."
"""
        return self.ollama.generate(prompt, max_tokens=400)
    
    def process_document_collection(self, input_file: str, output_file: str):
        # This method is good, no changes needed.
        with open(input_file, 'r') as f:
            input_data = json.load(f)
        
        base_dir = os.path.dirname(input_file) or '.'
        pdf_dir = os.path.join(base_dir, "PDFs")
        logger.info(f"Looking for PDFs in: {pdf_dir}")

        all_sections = []
        for doc in input_data['documents']:
            pdf_path = os.path.join(pdf_dir, doc['filename'])
            if os.path.exists(pdf_path):
                logger.info(f"Parsing document: {doc['filename']}")
                parsed_data = self.pdf_parser.extract_content(pdf_path)
                if parsed_data and parsed_data['sections']:
                    for section in parsed_data['sections']:
                        section['document'] = doc['filename']
                        all_sections.append(section)
            else:
                logger.warning(f"PDF not found: {pdf_path}")
        
        if not all_sections:
            logger.error("No sections were extracted from any PDF. Aborting analysis.")
            return

        logger.info(f"Analyzing relevance of {len(all_sections)} sections...")
        scored_sections = []
        for section in all_sections:
            score = self.analyze_section_relevance(section, input_data['persona'], input_data['job_to_be_done'])
            section['relevance_score'] = score
            scored_sections.append(section)
            logger.info(f"  - Scored '{section['text'][:50]}...' from {section['document']} with relevance: {score:.1f}")
        
        scored_sections.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_sections_for_output = scored_sections[:5]
        
        logger.info("Generating detailed subsection analysis for top 5 sections...")
        subsection_analysis = []
        for section_data in top_sections_for_output:
            insights = self.extract_key_insights(section_data, input_data['persona'], input_data['job_to_be_done'])
            subsection_analysis.append({'document': section_data['document'], 'refined_text': insights, 'page_number': section_data['page']})
        
        output_data = {
            'metadata': {'input_documents': [d['filename'] for d in input_data['documents']], 'persona': input_data['persona']['role'], 'job_to_be_done': input_data['job_to_be_done']['task'], 'processing_timestamp': datetime.now().isoformat()},
            'extracted_sections': [{'document': s['document'], 'section_title': s['text'], 'importance_rank': i + 1, 'page_number': s['page']} for i, s in enumerate(top_sections_for_output)],
            'subsection_analysis': subsection_analysis
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=4)
        
        logger.info(f"Analysis complete. Output saved to: {output_file}")

def main():
    # This function is good, no changes needed.
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
    input_file = os.path.join(current_dir, 'challenge1b_input.json')
    output_file = os.path.join(current_dir, 'output', 'challenge1b_output.json')
    
    if not os.path.exists(input_file):
        logger.error(f"FATAL: Input file not found at {input_file}")
        return
    
    try:
        analyzer = PersonaDrivenAnalyzer()
        analyzer.process_document_collection(input_file, output_file)
        logger.info("Processing completed successfully!")
    except Exception as e:
        logger.critical(f"A critical error stopped the program: {e}", exc_info=True)

if __name__ == "__main__":
    main()