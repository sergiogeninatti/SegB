# model_manager.py
import os
from pathlib import Path
from typing import Dict, List, Optional

class ModelManager:
    """Gestiona el descubrimiento y roles de modelos"""
    
    # Mapeo de roles por nombre de carpeta
    ROLE_MAPPING = {
        'frame': 'scale',
        'cells': 'reference',
        # Cualquier otra carpeta será 'content'
    }
    
    def __init__(self, model_root: str = '/app/model'):
        self.model_root = Path(model_root)
        self.available_models = self._discover_models()
    
    def _discover_models(self) -> Dict[str, Dict[str, str]]:
        """Descubre automáticamente la estructura de modelos"""
        models = {}
        
        if not self.model_root.exists():
            print(f"⚠️ Model root not found: {self.model_root}")
            return models
        
        for category_dir in self.model_root.iterdir():
            if not category_dir.is_dir():
                continue
            
            category = category_dir.name
            models[category] = {}
            
            for variant_dir in category_dir.iterdir():
                if not variant_dir.is_dir():
                    continue
                
                variant = variant_dir.name
                keras_files = list(variant_dir.glob("*.keras"))
                if keras_files:
                    models[category][variant] = str(keras_files[0])
        
        return models
    
    def get_categories(self) -> List[str]:
        """Retorna lista de categorías disponibles"""
        return list(self.available_models.keys())
    
    def get_variants(self, category: str) -> List[str]:
        """Retorna lista de variantes disponibles para una categoría, incluyendo 'none'"""
        variants = list(self.available_models.get(category, {}).keys())
        variants.append('none')
        return variants
    
    def get_model_path(self, category: str, variant: str) -> Optional[str]:
        """Retorna la ruta del modelo para una categoría y variante"""
        if variant == 'none':
            return None
        return self.available_models.get(category, {}).get(variant)
    
    def is_valid_selection(self, category: str, variant: str) -> bool:
        """Valida que la combinación categoría/variante sea válida"""
        # 'none' siempre es válido (desactivado)
        if variant == 'none':
            return True
        return variant in self.get_variants(category)
    
    def get_role(self, category: str) -> str:
        """Determina el rol de una categoría: 'scale', 'reference' o 'content'"""
        return self.ROLE_MAPPING.get(category, 'content')
    
    def get_summary(self) -> str:
        """Retorna resumen de modelos disponibles"""
        if not self.available_models:
            return "⚠️ No models found in /app/model"
        
        lines = ["📦 Available models:"]
        for category, variants in self.available_models.items():
            role = self.get_role(category)
            role_icon = {'scale': '📏', 'reference': '🔵', 'content': '📊'}.get(role, '📁')
            variants_list = ', '.join(variants.keys())
            lines.append(f"  {role_icon} {category} ({role}): {variants_list}")
        
        return '\n'.join(lines)
