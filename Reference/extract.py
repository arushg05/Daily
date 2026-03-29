import fitz

def extract_text(pdf_path, output_path):
    try:
        doc = fitz.open(pdf_path)
        with open(output_path, "w", encoding="utf-8") as f:
            for page in doc:
                text = page.get_text()
                f.write(text)
                f.write("\n" + "="*80 + "\n")
        print(f"Extraction successful: {output_path}")
    except Exception as e:
        print(f"Error extracting text: {e}")

if __name__ == "__main__":
    extract_text("Trading Patterns and Indicators Explained.pdf", "pdf_content.txt")
