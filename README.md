# Adobe Hackathon Round 1B - Persona-Driven Document Analyzer

## Overview

This solution analyzes PDF documents and extracts the most relevant content based on a user's persona and their goal ("job to be done"). It performs section extraction and relevance scoring using a local LLM via Ollama, and generates a final summarized JSON report tailored to the user context.

---

## Approach

### Phase 1: Content Extraction

- **Uses PyPDF2** to extract content from PDFs.
- **Section Detection** uses a multi-tier fallback:
  1. **PDF Bookmarks** (if present)
  2. **Heading Detection** via text heuristics
  3. **Page-by-page fallback** if no headings are found

### Phase 2: Relevance Scoring

- Uses **TinyLLaMA via Ollama** to rate section relevance
- Prompt-based scoring from 1.0 (not relevant) to 10.0 (highly relevant)
- Persona context and goal are passed in the prompt

### Phase 3: Summary Generation

- Generates narrative summaries (no bullets or headings)
- Extracts top 5 most relevant sections
- Adds page numbers, original title, and document metadata

---

## Input Format

A JSON file (`challenge1b_input.json`) in this format:

```json
{
  "persona": {
    "role": "Travel Planner"
  },
  "job_to_be_done": {
    "task": "Plan a vacation for a group of college friends"
  },
  "documents": [
    { "filename": "South of France - Cities.pdf" },
    { "filename": "Budget Guide Europe.pdf" }
  ]
}
```

Place all PDFs inside a folder named `PDFs` next to the input JSON.

---

## Output Format

A JSON file (`challenge1b_output.json`) saved inside the `output/` folder:

```json
{
  "metadata": {
    "input_documents": [...],
    "persona": "Travel Planner",
    "job_to_be_done": "Plan a vacation for...",
    "processing_timestamp": "..."
  },
  "extracted_sections": [
    {
      "document": "South of France - Cities.pdf",
      "section_title": "Nightlife & Events",
      "importance_rank": 1,
      "page_number": 12
    }
  ],
  "subsection_analysis": [
    {
      "document": "South of France - Cities.pdf",
      "refined_text": "This section offers...",
      "page_number": 12
    }
  ]
}
```

---

## Docker Setup

### Build the Docker Image

Run this inside the folder that contains the Dockerfile:

```bash
docker build --platform=linux/amd64 -t persona-doc-analyzer .
```

### Run the Docker Container

#### PowerShell (Windows)

```powershell
docker run --rm `
  -v "${PWD}\PDFs:/app/PDFs" `
  -v "${PWD}\challenge1b_input.json:/app/challenge1b_input.json" `
  -v "${PWD}\output:/app/output" `
  persona-doc-analyzer
```

#### Bash (Linux/macOS)

```bash
docker run --rm \
  -v "$(pwd)/PDFs:/app/PDFs" \
  -v "$(pwd)/challenge1b_input.json:/app/challenge1b_input.json" \
  -v "$(pwd)/output:/app/output" \
  persona-doc-analyzer
```

---

## Dependencies (installed via Docker)

- Python 3.9
- PyPDF2
- requests
- Ollama (for local LLM serving)

---

## Output Location

Output will be written to:

```
/output/challenge1b_output.json
```

---

## Notes

- Ollama is automatically installed and launched inside the container.
- Model `tinyllama` is pulled and served.
- All processing is local and private.
- In case of long startup, the container waits and retries connecting to Ollama.




