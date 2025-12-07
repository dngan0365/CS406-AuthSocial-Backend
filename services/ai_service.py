from ml_models.ai_detector import get_ai_detector
from config import get_settings
from typing import List
import logging

settings = get_settings()

class AIService:
    def __init__(self):
        self.detector = get_ai_detector(settings.model_path, settings.device)
        self.threshold = 0.7  # Ngưỡng confidence để coi là AI
    
    async def check_single_image(self, image_bytes: bytes) -> dict:
        """
        Kiểm tra một ảnh
        Returns: {
            "confidence": float,  # ai_perc
            "is_ai": bool,
            "label": str  # "ai" hoặc "real"
        }
        """
        try:
            # predict() returns tuple: (label, confidence)
            label, confidence = self.detector.predict(image_bytes)
            
            is_ai = label == "ai" and confidence >= self.threshold
            
            # Convert confidence to percentage and ensure it's > 0 for DB constraint
            # Use max to ensure we never store exactly 0.0
            confidence_percent = max(confidence * 100, 0.01)
            
            return {
                "confidence": confidence_percent,
                "is_ai": is_ai,
                "label": label
            }
        except Exception as e:
            logging.error(f"Error in AI detection: {e}")
            # Return safe default that passes DB constraint (ai_perc > 0)
            return {
                "confidence": 0.01,  # Minimum value to satisfy constraint
                "is_ai": False,
                "label": "unknown"
            }
    
    async def check_images(self, images_bytes: List[bytes]) -> dict:
        """
        Check multiple images (deprecated - use check_single_image for each image)
        Returns status: approved_non_ai / rejected_ai
        """
        results = []
        
        for img_bytes in images_bytes:
            result = await self.check_single_image(img_bytes)
            results.append(result)
        
        # Tính số ảnh AI
        ai_images = [r for r in results if r["is_ai"]]
        ai_percentage = (len(ai_images) / len(results)) * 100 if results else 0
        
        if ai_percentage > 50:
            avg_confidence = sum(r["confidence"] for r in ai_images) / len(ai_images) if ai_images else 0
            return {
                "status": "rejected_ai",
                "confidence": avg_confidence,
                "ai_percentage": ai_percentage,
                "message": f"Detected {len(ai_images)}/{len(results)} AI-generated image(s)"
            }
        else:
            avg_confidence = sum(r["confidence"] for r in results) / len(results) if results else 0
            return {
                "status": "approved_non_ai",
                "confidence": avg_confidence,
                "ai_percentage": ai_percentage,
                "message": f"Post approved with {ai_percentage:.1f}% AI content"
            }

def get_ai_service():
    """Dependency injection cho FastAPI"""
    return AIService()