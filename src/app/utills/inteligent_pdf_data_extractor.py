import base64
import httpx

import os
import base64
import os
import mimetypes
import json


def parse_extracted_data(response):
    """Parse and validate the JSON response from the LLM"""
    try:
        # Extract JSON from response text
        response_text = response.content if hasattr(response, 'content') else str(response)
        # Find JSON block in response
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end != 0:
            json_str = response_text[start:end]
            return json.loads(json_str)
        else:
            return {"error": "No JSON found in response"}
            
    except json.JSONDecodeError as e:
        return {"error": f"JSON parsing failed: {str(e)}"}
    

def pdf_data_extract(file_path, file_base64, llm):
    mime_type, _ = mimetypes.guess_type(file_path)
    filename = os.path.basename(file_path)
    # Detailed prompt for comprehensive PDF extraction
    extraction_prompt = """
Please extract ALL content from this PDF document page by page. I need a comprehensive extraction that preserves every piece of information without losing any details.

**IMPORTANT REQUIREMENTS:**

1. **Complete Content Extraction**: Extract EVERYTHING from each page including:
   - All text content (headers, body text, footnotes, captions)
   - Table data (preserve structure and formatting)
   - Image descriptions or alt text if available
   - Form fields and their values
   - Metadata visible on the page
   - Page numbers, headers, footers
   - Any annotations or comments
   - Bullet points, numbered lists with proper formatting
   - Special characters, symbols, and formatting

2. **Page-by-Page Organization**: Organize the extracted content exactly in this JSON format:
```json
{
  "1": "Complete content from page 1 including all text, tables, and descriptions...",
  "2": "Complete content from page 2 including all text, tables, and descriptions...",
  "3": "Complete content from page 3 including all text, tables, and descriptions...",
  "n": "Complete content from page n..."
}
```

3. **Content Preservation Guidelines**:
   - Maintain original text formatting and spacing where possible
   - For tables: preserve column structure using clear delimiters (like | or tabs)
   - For lists: maintain numbering or bullet formatting
   - Include any repeated headers/footers on each page
   - Preserve line breaks and paragraph structure
   - Keep special characters and symbols intact
   - Include any watermarks or background text that's readable

4. **Handling Special Content**:
   - For images: Describe what's visible if no alt text exists
   - For charts/graphs: Describe the visual data representation
   - For forms: Include field names and any filled values
   - For multi-column text: Indicate column breaks clearly

5. **Quality Assurance**:
   - Do not summarize or paraphrase - extract verbatim
   - Do not skip any readable content
   - If text is partially obscured, include what's readable and note "[partially obscured]"
   - Include page numbers as they appear in the document

**OUTPUT FORMAT**: Return ONLY the JSON object with page numbers as keys and complete page content as values. Do not include any additional commentary or explanation outside the JSON structure.

**EXAMPLE OUTPUT STRUCTURE**:
```json
{
  "1": "[Header: Company Name]\\n\\nTitle of Document\\n\\nThis is the complete first paragraph with all original formatting...\\n\\nTable:\\nColumn1 | Column2 | Column3\\nData1 | Data2 | Data3\\n\\n[Footer: Page 1]",
  "2": "[Header: Company Name]\\n\\nContinued content from page 2...\\n\\n[Footer: Page 2]"
}
```

Begin extraction now:
"""
    
    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": extraction_prompt},
            {"type": "file", "source_type": "base64", "data": file_base64, "mime_type": mime_type, "filename": filename},
        ],
    }

    response = llm.invoke([message])
    output = parse_extracted_data(response)
    return output
