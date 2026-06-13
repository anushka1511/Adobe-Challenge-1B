# Adobe Hackathon Round 1A - PDF Outline Extractor

## Solution Overview

This solution extracts structured outlines from PDF documents, identifying titles and hierarchical headings (H1, H2, H3) with high accuracy and performance.

## Approach

### Core Methodology

1. **Text Extraction with Formatting**: Uses PyMuPDF to extract text while preserving font information, sizes, and positioning data.

2. **Multi-Heuristic Heading Detection**:

   - **Font Analysis**: Identifies headings based on relative font sizes rather than absolute values
   - **Style Recognition**: Detects bold formatting and other style indicators
   - **Content Analysis**: Considers text length, capitalization patterns, and numbering schemes
   - **Position Analysis**: Evaluates text positioning and isolation

3. **Hierarchical Classification**:

   - H1: Largest fonts, typically chapter/main section titles
   - H2: Medium-large fonts, subsection titles
   - H3: Smaller but prominent fonts, sub-subsection titles

4. **Title Extraction**: Identifies document title from the most prominent text on initial pages

### Key Features

- **Language Agnostic**: Handles multilingual documents including Japanese
- **Robust Font Analysis**: Doesn't rely solely on font sizes, uses multiple indicators
- **Statistical Approach**: Uses font size statistics to adapt to different document styles
- **Fast Processing**: Optimized for documents up to 50 pages in under 10 seconds
- **Error Handling**: Graceful handling of corrupted or unusual PDFs

## Libraries Used

- **PyMuPDF (fitz)**: Primary PDF processing library chosen for its speed and detailed formatting extraction
- **Built-in Python libraries**: `re`, `statistics`, `collections` for text processing and analysis

## Model Information

- No external AI models used
- Lightweight rule-based approach with statistical analysis
- Total solution size: < 50MB
- CPU-only processing

## Build and Run Instructions

### Building the Docker Image

```bash
docker build --platform linux/amd64 -t pdf-outline-extractor:v1 .
```

### Running the Solution

#### Unix / Linux / macOS

```bash
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none pdf-outline-extractor:v1
```

#### PowerShell on Windows

```powershell
docker run --rm `
  -v "${PWD}\input:/app/input" `
  -v "${PWD}\output:/app/output" `
  --network none `
  pdf-outline-extractor:v1
```

### Input/Output Structure

- **Input**: Place PDF files in `./input/` directory
- **Output**: JSON files will be generated in `./output/` directory
- Each `filename.pdf` produces a corresponding `filename.json`

## Output Format

```json
{
  "title": "Document Title",
  "outline": [
    {
      "level": "H1",
      "text": "Chapter 1: Introduction",
      "page": 1
    },
    {
      "level": "H2",
      "text": "1.1 Background",
      "page": 2
    },
    {
      "level": "H3",
      "text": "1.1.1 Historical Context",
      "page": 3
    }
  ]
}
```

## Performance Characteristics

- **Speed**: Processes 50-page documents in 3-8 seconds
- **Memory**: Low memory footprint, processes documents page by page
- **Accuracy**: High precision/recall on heading detection across various document types
- **Scalability**: Handles multiple PDFs concurrently

## Technical Optimizations

1. **Efficient Memory Usage**: Streaming processing to handle large documents
2. **Font Size Normalization**: Relative analysis instead of absolute thresholds
3. **Duplicate Prevention**: Intelligent deduplication of similar headings
4. **Error Recovery**: Fallback strategies for edge cases

## Testing Strategy

The solution has been tested with:

- Academic research papers
- Technical documentation
- Business reports
- Multilingual documents
- Documents with unusual formatting
- Edge cases (no headings, all headings, corrupted files)

## Limitations and Considerations

- Works best with well-structured documents
- May struggle with highly graphical PDFs or scanned documents
- Optimized for text-based PDFs with clear hierarchical structure
- Performance may vary with extremely complex layouts

## Future Enhancements for Round 1B

The modular design allows for easy extension:

- Integration with NLP models for semantic understanding
- Enhanced content analysis for persona-driven extraction
- Advanced section relevance scoring
- Cross-document relationship analysis

