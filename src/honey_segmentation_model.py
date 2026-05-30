import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
from pathlib import Path
import os
import time

# Suprimir warnings de TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.get_logger().setLevel('ERROR')

# Definición simplificada de FixedDropout
from tensorflow import keras
from tensorflow.keras import backend as K

from typing import Dict

class FixedDropout(keras.layers.Dropout):
    def _get_noise_shape(self, inputs):
        if self.noise_shape is None:
            return self.noise_shape
        symbolic_shape = K.shape(inputs)
        return tuple(symbolic_shape[axis] if shape is None else shape
                    for axis, shape in enumerate(self.noise_shape))

def get_segmentation_models_custom_objects():
    """
    Obtiene los objetos personalizados de segmentation_models
    necesarios para cargar los modelos entrenados.
    """
    custom_objects = {'FixedDropout': FixedDropout}
    
    try:
        import segmentation_models as sm
        
        if hasattr(sm.losses, 'binary_focal_dice_loss'):
            custom_objects['binary_focal_loss_plus_dice_loss'] = sm.losses.binary_focal_dice_loss
            custom_objects['binary_focal_dice_loss'] = sm.losses.binary_focal_dice_loss
        
        if hasattr(sm.metrics, 'iou_score'):
            custom_objects['iou_score'] = sm.metrics.iou_score
        
        if hasattr(sm.metrics, 'f1_score'):
            custom_objects['f1-score'] = sm.metrics.f1_score
            custom_objects['f1_score'] = sm.metrics.f1_score
        
        if hasattr(sm.losses, 'binary_crossentropy'):
            custom_objects['binary_crossentropy'] = sm.losses.binary_crossentropy
        
    except ImportError:
        # Funciones de fallback simplificadas
        def binary_focal_dice_loss_fallback(y_true, y_pred):
            return tf.keras.losses.binary_crossentropy(y_true, y_pred)
        
        def iou_score_fallback(y_true, y_pred):
            y_pred = tf.cast(y_pred > 0.5, tf.float32)
            intersection = tf.reduce_sum(y_true * y_pred)
            union = tf.reduce_sum(y_true) + tf.reduce_sum(y_pred) - intersection
            return intersection / (union + tf.keras.backend.epsilon())
        
        def f1_score_fallback(y_true, y_pred):
            y_pred = tf.cast(y_pred > 0.5, tf.float32)
            tp = tf.reduce_sum(y_true * y_pred)
            fp = tf.reduce_sum((1 - y_true) * y_pred)
            fn = tf.reduce_sum(y_true * (1 - y_pred))
            precision = tp / (tp + fp + tf.keras.backend.epsilon())
            recall = tp / (tp + fn + tf.keras.backend.epsilon())
            return 2 * (precision * recall) / (precision + recall + tf.keras.backend.epsilon())
        
        custom_objects['binary_focal_loss_plus_dice_loss'] = binary_focal_dice_loss_fallback
        custom_objects['binary_focal_dice_loss'] = binary_focal_dice_loss_fallback
        custom_objects['iou_score'] = iou_score_fallback
        custom_objects['f1-score'] = f1_score_fallback
        custom_objects['f1_score'] = f1_score_fallback
    
    return custom_objects

class HoneySegmentationModel:
    
    def __init__(self, model_path, model_name="model"):
        self.model_name = model_name
        
        # Configurar límite de memoria para TensorFlow
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            try:
                tf.config.experimental.set_memory_growth(gpus[0], True)
                print(f"✅ GPU: {gpus[0]} - Memory growth enabled")
            except RuntimeError as e:
                print(f"⚠️ GPU config error: {e}")
        
        custom_objects = get_segmentation_models_custom_objects()
        
        with tf.device('/CPU:0'):
            self.model = load_model(model_path, custom_objects=custom_objects, compile=False)
        
        # Inferencia de calentamiento
        dummy_input = np.zeros((1, 640, 640, 3), dtype=np.float32)
        with tf.device('/CPU:0'):
            _ = self.model.predict(dummy_input, verbose=0, batch_size=1)
        
        self.IMG_HEIGHT = 640
        self.IMG_WIDTH = 640
        self.IMG_CHANNELS = 3
    
    def validate_and_get_frame_area(self, mask):
        """Valida que la máscara del frame tenga solo una región y calcula su área"""
        if len(mask.shape) == 3:
            mask_gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        else:
            mask_gray = mask
        
        mask_binary = (mask_gray > 0).astype(np.uint8)
        
        num_labels, labels = cv2.connectedComponents(mask_binary)
        num_regions = num_labels - 1
        
        is_valid = (num_regions == 1)
        area_px = np.sum(mask_binary)
        
        return {
            'area_px': area_px,
            'is_valid': is_valid,
            'num_regions': num_regions
        }

    def _resize_and_pad_image(self, image):
        h, w, _ = image.shape
        original_shape = (h, w)
        
        scale = min(self.IMG_HEIGHT / h, self.IMG_WIDTH / w)
        new_h, new_w = int(h * scale), int(w * scale)
        
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        pad_h = self.IMG_HEIGHT - new_h
        pad_w = self.IMG_WIDTH - new_w
        
        if pad_h > 0 or pad_w > 0:
            top, bottom = pad_h // 2, pad_h - (pad_h // 2)
            left, right = pad_w // 2, pad_w - (pad_w // 2)
            resized = cv2.copyMakeBorder(
                resized, top, bottom, left, right, 
                cv2.BORDER_CONSTANT, value=[0, 0, 0]
            )
            padding = (top, bottom, left, right)
        else:
            padding = None
        
        return resized, scale, {
            'original_shape': original_shape,
            'resized_shape': (new_h, new_w),
            'padding': padding,
            'scale': scale
        }
    
    def _remove_padding_and_resize(self, mask, resize_info):
        original_h, original_w = resize_info['original_shape']
        
        if resize_info['padding']:
            top, bottom, left, right = resize_info['padding']
            new_h, new_w = resize_info['resized_shape']
            
            if top > 0 or bottom > 0:
                mask = mask[top:top+new_h, :]
            if left > 0 or right > 0:
                mask = mask[:, left:left+new_w]
        
        if mask.shape[0] != original_h or mask.shape[1] != original_w:
            mask = cv2.resize(mask, (original_w, original_h), interpolation=cv2.INTER_NEAREST)
        
        return mask
    
    def calculate_segmentation_metrics(self, mask, original_img):
        mask_gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if len(mask.shape) == 3 else mask
        mask_binary = (mask_gray > 0).astype(np.uint8)
        
        total_pixels = mask_binary.size
        honey_pixels = np.sum(mask_binary)
        honey_percentage = (honey_pixels / total_pixels) * 100
        
        num_labels, labels = cv2.connectedComponents(mask_binary)
        num_components = num_labels - 1
        
        if num_components > 0:
            component_sizes = [np.sum(labels == i) for i in range(1, num_labels)]
            avg_component_size = np.mean(component_sizes)
            max_component_size = np.max(component_sizes)
        else:
            avg_component_size = max_component_size = 0
        
        return {
            'area_percentage': round(honey_percentage, 2),
            'honey_pixels': int(honey_pixels),
            'total_pixels': int(total_pixels),
            'num_regions': num_components,
            'avg_region_size': int(avg_component_size),
            'largest_region': int(max_component_size)
        }
    
    def _get_model_color(self, user_config, category: str):
        """Retorna el color asociado a la categoría desde la configuración del usuario"""
        # Intentar usar color de la configuración del usuario
        if user_config and 'model_colors' in user_config:
            model_colors = user_config.get('model_colors', {})
            if category in model_colors:
                return np.array(model_colors[category], dtype='uint8')
    
        # Fallback: paleta basada en hash de la categoría
        default_palette = [
            [255, 0, 0],    # Rojo
            [0, 255, 0],    # Verde
            [0, 0, 255],    # Azul
            [255, 255, 0],  # Amarillo
            [255, 0, 255],  # Magenta
            [0, 255, 255],  # Cian
            [255, 165, 0],  # Naranja
            [128, 0, 128],  # Púrpura
            [255, 192, 203],# Rosa
            [165, 42, 42],  # Marrón
        ]
        hash_val = abs(hash(category)) % len(default_palette)
        return np.array(default_palette[hash_val], dtype='uint8')    

    def process_single_image(self, image_path, user_config=None, category=None):
        if user_config is None:
            user_config = {"confidence_threshold": 0.5, "highlight_intensity": 0.4}
    
        threshold = user_config.get('confidence_threshold', 0.5)
        intensity = user_config.get('highlight_intensity', 0.4)
    
        start_total = time.time()
        timing_info = {}
    
        start_time = time.time()
        original_img = cv2.imread(str(image_path))
        if original_img is None:
            raise ValueError(f"No se pudo leer la imagen: {image_path}")
        
        original_img_rgb = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)
        img_h, img_w = original_img_rgb.shape[:2]
        timing_info['load_image'] = time.time() - start_time
    
        start_time = time.time()
        resized_img, scale, resize_info = self._resize_and_pad_image(original_img_rgb)
        timing_info['resize_image'] = time.time() - start_time
    
        start_time = time.time()
        model_input = np.expand_dims(resized_img.astype(np.float32) / 255.0, axis=0)
        timing_info['prepare_input'] = time.time() - start_time
    
        start_time = time.time()
        prediction = self.model.predict(model_input, verbose=0, batch_size=1)
        mask_resized = (prediction[0] > threshold).astype(np.uint8) * 255
        timing_info['model_inference'] = time.time() - start_time
    
        # Asegurar que mask tenga 3 canales
        if len(mask_resized.shape) == 2:
            mask_resized = cv2.cvtColor(mask_resized, cv2.COLOR_GRAY2BGR)
        elif mask_resized.shape[2] == 1:
            mask_resized = cv2.cvtColor(mask_resized, cv2.COLOR_GRAY2BGR)
    
        start_time = time.time()
        final_mask = self._remove_padding_and_resize(mask_resized, resize_info)
        timing_info['resize_mask'] = time.time() - start_time
    
        if final_mask.shape[:2] != original_img_rgb.shape[:2]:
            final_mask = cv2.resize(final_mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
    
        start_time = time.time()
        # Usar categoría para obtener el color (si no hay categoría, usar 'content')
        color = self._get_model_color(user_config, category if category else 'content')
        mask_gray = cv2.cvtColor(final_mask, cv2.COLOR_BGR2GRAY)
        mask_bool = mask_gray > 0
    
        masked_img = np.where(np.stack([mask_bool]*3, axis=2), color, original_img_rgb)
        # Usar intensidad configurable
        alpha = 1.0 - intensity
        beta = intensity
        highlighted = cv2.addWeighted(original_img_rgb, alpha, masked_img, beta, 0)
        timing_info['create_highlighted'] = time.time() - start_time
    
        metrics = self.calculate_segmentation_metrics(final_mask, original_img_rgb)
        timing_info['total_time'] = time.time() - start_total

        frame_info = None
        if "Frame" in self.model_name:
            frame_info = self.validate_and_get_frame_area(final_mask)
    
        return {
            'mask': final_mask,
            'highlighted_image': highlighted,
            'processing_info': timing_info,
            'resize_info': resize_info,
            'model_name': self.model_name,
            'metrics': metrics,
            'frame_info': frame_info
        }



class MultiModelProcessor:
    def __init__(self, model_manager, user_config: Dict):
        """
        Crea un procesador con los modelos seleccionados por el usuario
        """
        self.model_manager = model_manager
        self.models = []
        self.model_categories = {}  # Mapea display_name -> categoria (frame, cells, honey, etc.)
        
        categories = model_manager.get_categories()
        model_selection = user_config.get('model_selection', {})
        
        for category in categories:
            variant = model_selection.get(category, 'unet')
            # Saltar si está desactivado
            if variant == 'none':
                continue
            model_path = model_manager.get_model_path(category, variant)
            
            if model_path:
                display_name = category.capitalize() + " Detection"
                self.models.append(HoneySegmentationModel(model_path, display_name))
                self.model_categories[display_name.lower()] = category
                    

    def process_image(self, image_path, user_config=None):
        """Procesa una imagen con todos los modelos cargados"""
        all_results = []
        for model in self.models:
            category = self.model_categories.get(model.model_name.lower(), 'content')
            result = model.process_single_image(image_path, user_config=user_config, category=category)
            all_results.append(result)
    
        # Crear imagen combinada
        combined_result = None
        if all_results:
            try:
                original_img = cv2.imread(str(image_path))
                original_img_rgb = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)
                combined_img = original_img_rgb.copy()
            
                # Colores por defecto según rol (para imagen combinada)
                default_colors = {
                    'scale': np.array([255, 0, 0], dtype='uint8'),     # Rojo: frame
                    'reference': np.array([0, 0, 255], dtype='uint8'), # Azul: cells
                    'content': np.array([0, 255, 0], dtype='uint8'),   # Verde: contenido
                }
            
                for result in all_results:
                    model_name = result['model_name'].lower()
                    category = self.model_categories.get(model_name, 'content')
                    # Obtener rol de la categoría
                    role = self.model_manager.get_role(category)
                    color = default_colors.get(role, np.array([255, 255, 0], dtype='uint8'))
                
                    mask_gray = cv2.cvtColor(result['mask'], cv2.COLOR_BGR2GRAY)
                    mask_bool = mask_gray > 0
                    masked_img = np.where(np.stack([mask_bool]*3, axis=2), color, combined_img)
                    combined_img = cv2.addWeighted(combined_img, 0.6, masked_img, 0.4, 0)
            
                combined_result = {'highlighted_image': combined_img}
            except Exception:
                pass
    
        return {
            'individual_results': all_results,
            'combined_result': combined_result,
            'total_models_processed': len(all_results)
        }
