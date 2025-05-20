import re
from datetime import datetime
from typing import Any, Dict, Optional

import fitz  # PyMuPDF
from fastapi import UploadFile


class InitialDocumentClassifier:
    
    
    def __init__(self):
        
        self.direct_patterns = {
            "W2": [
                r"W-?2\s+Wage\s+and\s+Tax\s+Statement",
                r"\bForm\s+W-?2\b"
            ],
            "1040": [
                r"Form\s+1040\s+.*?Individual\s+Income\s+Tax\s+Return",
                r"Form\s+1040\s+U\.S\.\s+Individual\s+Income\s+Tax\s+Return",
                r"1040.*U\.S\.\s+Individual\s+Income\s+Tax\s+Return"
            ],
            "1099": [
                r"Form\s+1099-DIV",
                r"Form\s+1099-INT",
                r"Dividends\s+and\s+Distributions",
                r"Interest\s+Income"
            ],
            "ID Card": [
                r"ID\s*CARD",
                r"IDCARD"
            ],
            "Handwritten note": [
                r"The\s+Farm\s+and\s+Fisherman"
            ]
        }
        
       
        self.form_1098_patterns = [
            r"Form\s+1098\b", 
            r"Mortgage\s+Interest\s+Statement",
            r"RECIPIENT'S/LENDER'S"
        ]
        
    async def extract_text_from_pdf(self, file_content: bytes) -> str:
        
        try:
           
            doc = fitz.open(stream=file_content, filetype="pdf")
            
            # Extract text from each page
            text = ""
            for page in doc:
                text += page.get_text() # type: ignore
                
            return text
        except Exception as e:
            #print(f"Error extracting text from PDF: {e}")
            return ""
    
    def is_form_1098(self, text: str) -> bool:
       
        if "Form 1098" in text and "Mortgage Interest Statement" in text:
            #print("Found Form 1098")
            return True
            
        
        matches = 0
        for pattern in self.form_1098_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
                if matches >= 2:  # Require at least 2 matches to confirm 1098
                    print("Found multiple Form 1098 patterns")
                    return True
        return False
    
    def is_form_1040(self, text: str) -> bool:
        
        # First check for the key identifiers of Form 1040
        if (("Form 1040" in text or "1040" in text[:200]) and 
            ("U.S. Individual Income Tax Return" in text or "Individual Income Tax Return" in text[:300])):
            #print("Found Form 1040 markers")
            return True
            
        # Check for unique Form 1040 sections
        form_1040_sections = [
            "Filing Status",
            "Standard Deduction",
            "Presidential Election Campaign",
            "Digital Assets",
            "taxable income"
        ]
        
        # Count how many Form 1040 sections are present
        section_count = sum(1 for section in form_1040_sections if section in text)
        if section_count >= 2:
            #print(f"Found {section_count} Form 1040 sections")
            return True
            
        return False
    
    def determine_document_type(self, text: str) -> str:
        
        #print(f"Text starts with: {text[:50].strip()}")
        
        
        if self.is_form_1040(text):
            
            return "1040"
        
        
        if self.is_form_1098(text):
            
            return "OTHER"
        
       
        
       
        if ("Form 1099-INT" in text and "Interest Income" in text) or \
           ("Form 1099-DIV" in text and "Dividends and Distributions" in text):
            
            return "1099"
            
        
        if ("Form W-2" in text or "Form W2" in text) and "Wage and Tax Statement" in text:
            #print("Detected W2 with key phrases")
            return "W2"
        
       
        if "IDCARD" in text or "ID CARD" in text:
            #print("Detected ID Card")
            return "ID Card"
            
        
        for doc_type, patterns in self.direct_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    #print(f"Found pattern match for {doc_type}: {pattern}")
                    
                    
                    if doc_type == "W2" and "U.S. Individual Income Tax Return" in text:
                        #print("Skipping W2 match because document contains 1040 indicators")
                        continue
                    
                    return doc_type
        
        
        if "social security" in text and "Medicare wages and tips" in text and "W-2" in text:
            return "W2"
        
        return "OTHER"
    
    def extract_year_from_w2(self, text: str) -> Optional[str]:
        
        pattern1 = r"Wage\s+and\s+Tax\s+Statement\s+(\d{4})"
        match1 = re.search(pattern1, text)
        if match1:
            #print(f"Found W2 year with pattern 1: {match1.group(1)}")
            return match1.group(1)
            
        
        pattern2 = r"Form\s+W-?2\s+(\d{4})"
        match2 = re.search(pattern2, text)
        if match2:
            #print(f"Found W2 year with pattern 2: {match2.group(1)}")
            return match2.group(1)
            
        
        pattern3 = r"Treasury.*?Internal\s+Revenue\s+Service\s+(\d{4})"
        match3 = re.search(pattern3, text)
        if match3:
            #print(f"Found W2 year with pattern 3: {match3.group(1)}")
            return match3.group(1)
            
        
        pattern4 = r"W-?2\s+Wage\s+and\s+Tax\s+Statement\s+(\d{4})\s+Department\s+of\s+the\s+Treasury"
        match4 = re.search(pattern4, text)
        if match4:
            #print(f"Found W2 year with pattern 4: {match4.group(1)}")
            return match4.group(1)
            
        return None
        
    def extract_year_from_1098(self, text: str) -> Optional[str]:
       
        pattern1 = r"Form\s+1098\s+\(Rev\.\s+\d+-(\d{4})\)"
        match1 = re.search(pattern1, text)
        if match1:
            #print(f"Found 1098 year with pattern 1: {match1.group(1)}")
            return match1.group(1)
            
        
        pattern2 = r"For\s+calendar\s+year\s+20\s+(\d{2})"
        match2 = re.search(pattern2, text)
        if match2:
            year = "20" + match2.group(1)
            #print(f"Found 1098 year with pattern 2: {year}")
            return year
            
        
        pattern3 = r"For\s+calendar\s+year\s+(\d{4})"
        match3 = re.search(pattern3, text)
        if match3:
            #print(f"Found 1098 year with pattern 3: {match3.group(1)}")
            return match3.group(1)
            
        return None
    
    def extract_year(self, text: str, doc_type: str) -> Optional[str]:
        
        #print(f"Extracting year for document type: {doc_type}")
        
        
        if doc_type == "W2":
            w2_year = self.extract_year_from_w2(text)
            if w2_year:
                return w2_year
        
       
        if doc_type == "OTHER" and self.is_form_1098(text):
            form_1098_year = self.extract_year_from_1098(text)
            if form_1098_year:
                return form_1098_year
        
        # For 1099 forms
        if doc_type == "1099":
            
            year_match = re.search(r"Form\s+1099-(?:INT|DIV).*?(\d{4})", text)
            if year_match:
                return year_match.group(1)
                
            
            rev_match = re.search(r"Rev\.\s+January\s+(\d{4})", text)
            if rev_match:
                return rev_match.group(1)
                
           
            calendar_match = re.search(r"For\s+calendar\s+year\s+(\d{4})", text)
            if calendar_match:
                return calendar_match.group(1)
                
           
            calendar_match2 = re.search(r"For\s+calendar\s+year\s+20\s+(\d{2})", text)
            if calendar_match2:
                return "20" + calendar_match2.group(1)
        
        
        elif doc_type == "1040":
           
            first_page_match = re.search(r"Form\s+1040\s+(\d{4})", text[:1000])
            if first_page_match:
                return first_page_match.group(1)
                
            
            form_match = re.search(r"Form 1040 \((\d{4})\)", text)
            if form_match:
                return form_match.group(1)
                
           
            header_match = re.search(r"1040\s+(\d{4})", text[:500])
            if header_match:
                return header_match.group(1)
                
            
            visual_match = re.search(r"([12][09][0-9]{2})\s+OMB No\.", text)
            if visual_match:
                return visual_match.group(1)
        
        
        elif doc_type == "ID Card":
            expiration_match = re.search(r"Expiration\s+Date\s+\d{2}/\d{2}/(\d{4})", text)
            if expiration_match:
                return expiration_match.group(1)
        
        
        all_years = re.findall(r"\b(19|20)\d{2}\b", text)
        if all_years:
            return max(all_years)
            
        return None
    
    async def classify_document(self, file: UploadFile) -> Dict[str, Any]:
       
        file_content = await file.read()
        
        
        text = await self.extract_text_from_pdf(file_content)
        
        
        #print(f"Text sample {text[:200]}...")
        
        
        document_type = self.determine_document_type(text)
        #print(f"Final document type: {document_type}")
        
       
        year = self.extract_year(text, document_type)
        #print(f"Extracted year: {year}")
        
        return {
            "document_type": document_type,
            "year": year if year else "NOT IMPLEMENTED"
        }