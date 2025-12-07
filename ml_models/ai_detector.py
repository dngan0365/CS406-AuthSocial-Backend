import torch
import torch.nn as nn
from torchvision import transforms
from collections import OrderedDict
from PIL import Image
import io
import os
from huggingface_hub import hf_hub_download
from typing import Tuple

# -------------------------------
# BACKBONE SINGLETON + LOCAL CACHE
# -------------------------------
_BACKBONE_PATH = "./ml_models/backbone/dino_vitb14.pth"
_backbone_instance = None

def get_dino_backbone(device="cpu"):
    """
    Load DINOv2 backbone từ local nếu có.
    Nếu chưa có file -> tải 1 lần từ torch.hub và lưu lại vào đĩa.
    Giữa các request: backbone chỉ tồn tại 1 instance.
    """
    global _backbone_instance

    if _backbone_instance is not None:
        return _backbone_instance

    os.makedirs(os.path.dirname(_BACKBONE_PATH), exist_ok=True)

    print("[Backbone] Initializing DINOv2 backbone...")

    # Nếu đã có file local → load state dict
    if os.path.exists(_BACKBONE_PATH):
        print(f"[Backbone] Loading from local cache: {_BACKBONE_PATH}")

        backbone = torch.hub.load(
            'facebookresearch/dinov2', 
            'dinov2_vitb14'
        )
        state_dict = torch.load(_BACKBONE_PATH, map_location=device)
        backbone.load_state_dict(state_dict)

    else:
        # Tải backbone từ internet (1 lần duy nhất)
        print("[Backbone] Downloading from torch.hub (first time)...")

        backbone = torch.hub.load(
            'facebookresearch/dinov2', 
            'dinov2_vitb14'
        )

        print(f"[Backbone] Saving to local: {_BACKBONE_PATH}")
        torch.save(backbone.state_dict(), _BACKBONE_PATH)

    # Freeze backbone
    for p in backbone.parameters():
        p.requires_grad = False

    backbone.to(device)
    backbone.eval()

    _backbone_instance = backbone
    return backbone


# -------------------------------
# AI DETECTOR
# -------------------------------

class AIDetector:
    def __init__(self, model_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        self.model = self._load_model(model_path)
        self.preprocessor = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def _load_model(self, model_path: str):
        # Load backbone (KHÔNG BAO GIỜ tải lại)
        backbone_model = get_dino_backbone(self.device)

        # Create full model
        model = nn.Sequential(OrderedDict([
            ('backbone', backbone_model),
            ('head', nn.Sequential(
                nn.Linear(768, 512),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(512, 2)
            ))
        ]))

        # Load head weights
        head_path = hf_hub_download(
            repo_id="dngan0365/dinov2-finetune",
            filename="best_model.pth",
        )
        state_dict = torch.load(head_path, map_location=self.device)
        model.load_state_dict(state_dict, strict=False)

        model.eval()
        model.to(self.device)
        return model
    
    def predict(self, image_bytes: bytes) -> Tuple[str, float]:
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            input_tensor = self.preprocessor(image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                outputs = self.model(input_tensor)
                probs = torch.nn.functional.softmax(outputs, dim=1)
                confidence, predicted = torch.max(probs, 1)

            label = "real" if predicted.item() == 0 else "ai"
            return label, confidence.item()

        except Exception as e:
            raise Exception(f"Error during prediction: {str(e)}")
    
    def predict_batch(self, images_bytes: list) -> list:
        return [
            {"label": self.predict(b)[0], 
             "confidence": self.predict(b)[1]}
            for b in images_bytes
        ]


# -------------------------------
# SINGLETON CHO AIDETECTOR
# -------------------------------

_detector_instance = None

def get_ai_detector(model_path: str, device: str = "cpu"):
    global _detector_instance
    if _detector_instance is None:
        print("[AI Detector] Initializing detector singleton...")
        _detector_instance = AIDetector(model_path, device)
    return _detector_instance
