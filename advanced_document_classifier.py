import re
from typing import Any, Dict, List, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
from fastapi import UploadFile


class AdvancedDocumentClassifier:
    
    def __init__(self):
        # Tax form keywords (just for info/debugging)
        self.tax_form_keywords = [
            "FORM 1099", "FORM 1040", "FORM W-2", "FORM W2", 
            "TAX RETURN", "INTERNAL REVENUE SERVICE", 
            "DEPARTMENT OF THE TREASURY", "FORM 1098"
        ]

    async def extract_text_from_pdf(self, file_content: bytes) -> str:
        
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            full_text = "\n".join([page.get_text() for page in doc]) # type: ignore
            
            # Print a sample of the extracted text for debugging
            if full_text:
                sample = full_text[:100].replace('\n', ' ')
                #print(f"Text extraction sample: {sample}...")
            else:
                print("No text extracted from document")
                
            return full_text
        except Exception as e:
            print(f"Text extraction error: {e}")
            return ""

    def extract_images_from_pdf(self, file_content: bytes) -> List[np.ndarray]:
        images = []
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # type: ignore
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                images.append(img)
        except Exception as e:
            print(f"Image extraction error: {e}")
        return images
    
    def is_id_card(self, image: np.ndarray) -> Tuple[bool, float]:
    
        try:
            # Get image dimensions and check aspect ratio
            h, w = image.shape[:2]
            aspect_ratio = w / h
            
            # Most ID cards have aspect ratios
            aspect_score = 1.4 <= aspect_ratio <= 1.9
            #print(f"ID card aspect ratio: {aspect_ratio:.2f}, within range: {aspect_score}")
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            # Divide the image into a 3x3 grid
            h_step = h // 3
            w_step = w // 3
            regions = []
            
            for i in range(3):
                for j in range(3):
                    region = gray[i*h_step:(i+1)*h_step, j*w_step:(j+1)*w_step]
                    regions.append(np.mean(region)) # type: ignore
             
            # different areas like photo, text, etc.
            region_variance = np.var(regions)
            distinct_regions = region_variance > 300
            
            #edge detection
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            
            #detect straight lines
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=w/4, maxLineGap=20)
            has_straight_lines = lines is not None and len(lines) >= 4
            pixel_std = np.std(gray) # type: ignore
            structured_layout = pixel_std < 70 
            features = [aspect_score, distinct_regions, has_straight_lines, structured_layout]
            id_card_score = sum(1 for feature in features if feature)
            #print(f"ID card total score: {id_card_score}/4")
            
            # Calculate confidence score (0-1)
            confidence = id_card_score / 4
            
            
            return id_card_score >= 3, confidence
            
        except Exception as e:
            #print(f"ID card detection error: {e}")
            return False, 0.0
    
    def is_handwritten(self, image: np.ndarray) -> Tuple[bool, float]:
       
        try:
            #to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY_INV, 11, 2)
            
            #contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            
            if len(contours) < 20:
                
                return False, 0.0
            
            areas = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 10]
            if not areas:
                return False, 0.0
                
            
            area_variation = np.std(areas) / (np.mean(areas) + 1e-5)
            high_variation = area_variation > 2.0
            
            
            
            #bounding boxes 
            angles = []
            for contour in contours:
                if cv2.contourArea(contour) < 10:
                    continue
                    
                rect = cv2.minAreaRect(contour)
                
                angle = abs(rect[2]) % 90
                if angle > 45:
                    angle = 90 - angle
                angles.append(angle)
            
            if not angles:
                return False, 0.0
                
            
            angle_variation = np.std(angles)
            irregular_angles = angle_variation > 10
            
            
            
            y_centers = []
            for contour in contours:
                if cv2.contourArea(contour) < 10:
                    continue
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    y_centers.append(int(M["m01"] / M["m00"]))
            
            if not y_centers:
                return False, 0.0
                
            
            alignment_variation = np.std(y_centers) / gray.shape[0] 
            poor_alignment = alignment_variation > 0.08
            #print(f"Alignment variation: {alignment_variation:.2f}, poor alignment: {poor_alignment}")
            
            
            contour_density = len(contours) / (gray.shape[0] * gray.shape[1])
            sparse_distribution = contour_density < 0.01 
            #print(f"Contour density: {contour_density:.5f}, sparse distribution: {sparse_distribution}")
            
            
            features = [high_variation, irregular_angles, poor_alignment, sparse_distribution]
            handwriting_score = sum(1 for feature in features if feature)
            #print(f"Handwriting total score: {handwriting_score}/4")
            
            
            confidence = handwriting_score / 4
            
            
            return handwriting_score >= 3, confidence
            
        except Exception as e:
            #print(f"Handwriting detection error: {e}")
            return False, 0.0
    
    def extract_year(self, text: str) -> str:
        """Extract year from document text."""
        try:
            #regex pattern
            match = re.search(r"(19|20)\d{2}", text)
            if match:
                return match.group(0)
            return "NOT IMPLEMENTED"
        except Exception as e:
            #print(f"Year extraction error: {e}")
            return "NOT IMPLEMENTED"

    async def classify_document(self, file: UploadFile) -> Dict[str, Any]:
    
        try:
            # Read file content
            content = await file.read()
            
            # Extract text and check length
            text = await self.extract_text_from_pdf(content)
            text_length = len(text.strip())
            #print(f"Extracted text length: {text_length} chars")
            
            
            if text_length > 300:
                #print("Document has significant text content - classifying as OTHER (tax form)")
                return {"document_type": "OTHER", "year": self.extract_year(text)}
            
           
            images = self.extract_images_from_pdf(content)
            #print(f"Extracted {len(images)} images for visual analysis")
            
            if images:
                
                main_image = images[0]
                
                #id vs handwritten
                is_id, id_confidence = self.is_id_card(main_image)
                is_handwritten, handwriting_confidence = self.is_handwritten(main_image)
                
                #print(f"ID card classification: {is_id} (confidence: {id_confidence:.2f})")
                #print(f"Handwriting classification: {is_handwritten} (confidence: {handwriting_confidence:.2f})")
                
                if is_id and not is_handwritten:
                    #print("Document classified as ID Card")
                    return {"document_type": "ID Card", "year": self.extract_year(text)}
                elif is_handwritten and not is_id:
                    #print("Document classified as Handwritten note")
                    return {"document_type": "Handwritten note", "year": self.extract_year(text)}
                elif is_id and is_handwritten:
                    
                    if id_confidence > handwriting_confidence:
                        #print(f"Document classified as ID Card (confidence: {id_confidence:.2f} > {handwriting_confidence:.2f})")
                        return {"document_type": "ID Card", "year": self.extract_year(text)}
                    else:
                        #print(f"Document classified as Handwritten note (confidence: {handwriting_confidence:.2f} > {id_confidence:.2f})")
                        return {"document_type": "Handwritten note", "year": self.extract_year(text)}
                
                
                h, w = main_image.shape[:2]
                aspect_ratio = w / h
                if aspect_ratio < 1.0:
                    
                    flipped_image = cv2.rotate(main_image, cv2.ROTATE_90_CLOCKWISE)
                    is_id_flipped, id_confidence_flipped = self.is_id_card(flipped_image)
                    
                    if is_id_flipped:
                        #print(f"Document classified as ID Card (portrait orientation) with confidence: {id_confidence_flipped:.2f}")
                        return {"document_type": "ID Card", "year": self.extract_year(text)}
            
            #print("Classification uncertain - defaulting to OTHER")
            return {"document_type": "OTHER", "year": self.extract_year(text)}
            
        except Exception as e:
            #print(f"Document classification error: {e}")
            return {"document_type": "OTHER", "year": "NOT IMPLEMENTED"}