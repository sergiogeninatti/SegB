# user_config.py
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

class UserConfigManager:
    """Gestiona la configuración personalizada de cada usuario"""
    
    DEFAULT_CONFIG = {
        "model_selection": {},           # Dinámico: se llena según categorías disponibles
        "auto_send_combined": True,      # Enviar automáticamente imagen combinada
        "individual_results_per_model": {},  # NUEVO: control por modelo
        "highlight_intensity": 0.4,      # Intensidad del resaltado (0.0 a 1.0)
        "confidence_threshold": 0.5,     # Umbral de confianza para detecciones
        "preferred_format": "photo",     # "photo" o "document"
        "verbose_mode": False,           # Mostrar información detallada
        "save_debug_images": False,      # Guardar imágenes de debug
        "panel_dimensions": {
            "width_cm": 45.0,            # Ancho del panel en centímetros
            "height_cm": 20.0,           # Alto del panel en centímetros
            "unit": "cm"                 # Unidad de medida (cm, mm, m)
        },
        "model_colors": {                # Colores personalizados por modelo
            "Frame Detection": [255, 0, 0],    # Rojo
            "Honey Detection": [0, 255, 0],    # Verde
            "Built Cells Detection": [0, 0, 255] # Azul
        },
        "notifications": {
            "on_start": True,
            "on_complete": True,
            "on_error": True
        },
        "processing_options": {
            "max_image_size": 1920,      # Tamaño máximo de imagen
            "quality": 90                 # Calidad JPEG (1-100)
        }
    }
    
    def __init__(self, config_dir: str = '/app/debug'):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "user_configs.json"
        self._configs = self._load_configs()
    
    def _load_configs(self) -> Dict:
        """Cargar todas las configuraciones de usuario"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Migrar configuraciones antiguas a la estructura actual
                    for user_id, config in data.get('users', {}).items():
                        if isinstance(config, dict):
                            # Asegurar que todas las claves por defecto existan
                            for key, default_value in self.DEFAULT_CONFIG.items():
                                if key not in config:
                                    config[key] = default_value
                    return data
        except Exception as e:
            print(f"Error cargando configuraciones: {e}")
        
        return {
            "users": {},
            "last_updated": datetime.now().isoformat(),
            "version": "1.0"
        }
    
    def _save_configs(self) -> bool:
        """Guardar todas las configuraciones de usuario"""
        try:
            self._configs['last_updated'] = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._configs, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error guardando configuraciones: {e}")
            return False
    
    def _validate_value(self, param: str, value: Any) -> Any:
        """Validar y ajustar valores según rangos permitidos"""
    
        # Parámetros que deben ser booleanos
        boolean_params = [
            'auto_send_combined',
            'verbose_mode',
            'save_debug_images',
            'notifications.on_start',
            'notifications.on_complete',
            'notifications.on_error'
        ]
    
        # Rangos numéricos
        ranges = {
            'confidence_threshold': (0.0, 1.0),
            'highlight_intensity': (0.0, 1.0),
            'processing_options.quality': (1, 100),
            'processing_options.max_image_size': (320, 4096)
        }
    
        # Opciones permitidas
        allowed_options = {
            'preferred_format': ['photo', 'document']
        }
    
        # Valores por defecto
        default_values = {
            'auto_send_combined': True,
            'verbose_mode': False,
            'save_debug_images': False,
            'notifications.on_start': True,
            'notifications.on_complete': True,
            'notifications.on_error': True,
            'preferred_format': 'photo'
        }
    
        # Validar booleanos
        if param in boolean_params or param.startswith('notifications.'):
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                value_lower = value.lower()
                if value_lower == 'true':
                    return True
                elif value_lower == 'false':
                    return False
                else:
                    # Valor inválido, devolver default
                    return default_values.get(param, False)
    
        # Validar rangos numéricos
        if param in ranges:
            min_val, max_val = ranges[param]
            if isinstance(value, (int, float)):
                return max(min_val, min(max_val, value))
            # Si no es numérico, devolver default
            return default_values.get(param, 0.5)
    
        # Validar opciones permitidas
        if param in allowed_options:
            if value in allowed_options[param]:
                return value
            else:
                return default_values.get(param, 'photo')
    
        return value

    def validate_and_notify(self, param: str, original_value: str, validated_value: Any) -> tuple:
        """
        Valida un parámetro y retorna (es_valido, mensaje_notificacion)
        """
        # Parámetros booleanos
        boolean_params = ['auto_send_combined', 'verbose_mode',
                          'notifications.on_start', 'notifications.on_complete', 'notifications.on_error']
    
        # Parámetros con opciones específicas
        options_params = {
            'preferred_format': ['photo', 'document']
        }
    
        # Rangos numéricos
        ranges = {
            'confidence_threshold': (0.0, 1.0),
            'highlight_intensity': (0.0, 1.0),
            'processing_options.quality': (1, 100),
            'processing_options.max_image_size': (320, 4096)
        }
    
        # Verificar booleanos
        if param in boolean_params or param.startswith('notifications.'):
            if original_value.lower() not in ['true', 'false']:
                return False, f"⚠️ '{original_value}' is not valid for {param.split('.')[-1]}. Valid options: true, false. Using default: {validated_value}"
            return True, None
    
        # Verificar opciones permitidas
        if param in options_params:
            if original_value not in options_params[param]:
                valid_opts = ', '.join(options_params[param])
                return False, f"⚠️ '{original_value}' is not valid for {param}. Valid options: {valid_opts}. Using default: {validated_value}"
            return True, None
    
        # Verificar rangos numéricos
        if param in ranges:
            try:
                num_value = float(original_value)
                min_val, max_val = ranges[param]
                if num_value < min_val or num_value > max_val:
                    return False, f"⚠️ '{original_value}' is outside valid range for {param} ({min_val}-{max_val}). Adjusted to: {validated_value}"
            except ValueError:
                return False, f"⚠️ '{original_value}' is not a valid number for {param}. Using default: {validated_value}"
            return True, None
    
        return True, None
    
    def get_user_config(self, user_id: str) -> Dict:
        """Obtener configuración de un usuario específico"""
        if user_id not in self._configs['users']:
            # Crear configuración por defecto para nuevo usuario
            self._configs['users'][user_id] = self.DEFAULT_CONFIG.copy()
            self._save_configs()
        
        return self._configs['users'][user_id]
    
    def update_user_config(self, user_id: str, updates: Dict) -> bool:
        """Actualizar configuración de un usuario"""
        try:
            current = self.get_user_config(user_id)
        
            for key, value in updates.items():
                # Validar valor antes de aplicarlo
                value = self._validate_value(key, value)
            
                if '.' in key:
                    # Manejar claves anidadas (ej: processing_options.quality)
                    parts = key.split('.')
                    target = current
                    for part in parts[:-1]:
                        if part not in target:
                            target[part] = {}
                        target = target[part]
                    target[parts[-1]] = value
                elif key in current:
                    if isinstance(value, dict) and isinstance(current[key], dict):
                        current[key].update(value)
                    else:
                        current[key] = value
                else:
                    current[key] = value
        
            self._configs['users'][user_id] = current
            return self._save_configs()
        except Exception:
            return False
            
    def reset_user_config(self, user_id: str) -> bool:
        """Restablecer configuración de usuario a valores por defecto"""
        try:
            self._configs['users'][user_id] = self.DEFAULT_CONFIG.copy()
            return self._save_configs()
        except Exception as e:
            print(f"Error restableciendo configuración de usuario {user_id}: {e}")
            return False
        
    def parse_config_command(self, text: str) -> Optional[Dict[str, Any]]:
        """Parsear comandos de configuración como '/set auto_combined false'"""
        parts = text.strip().split()
        if len(parts) < 3 or parts[0].lower() != '/set':
            return None
    
        param = parts[1].lower()
        original_value_str = ' '.join(parts[2:])
    
        # Mapeo de parámetros abreviados a rutas completas
        param_mapping = {
            'auto_combined': 'auto_send_combined',
            # 'individual': 'send_individual_results',  # ELIMINADO - usar /set_individual
            'intensity': 'highlight_intensity',
            'threshold': 'confidence_threshold',
            'format': 'preferred_format',
            'verbose': 'verbose_mode',
            'quality': 'processing_options.quality',
            'max_size': 'processing_options.max_image_size',
            'notify_start': 'notifications.on_start',
            'notify_complete': 'notifications.on_complete',
            'notify_error': 'notifications.on_error'
        }
    
        # Mapear parámetro
        param = param_mapping.get(param, param)
    
        # Determinar el tipo esperado
        boolean_params = ['auto_send_combined', 'verbose_mode',
                          'notifications.on_start', 'notifications.on_complete', 'notifications.on_error']
    
        # Convertir valor
        value = original_value_str
        if param in boolean_params or param.startswith('notifications.'):
            value_lower = original_value_str.lower()
            if value_lower == 'true':
                value = True
            elif value_lower == 'false':
                value = False
            else:
                value = None  # Inválido, se aplicará default
        elif original_value_str.isdigit():
            value = int(original_value_str)
        elif original_value_str.replace('.', '', 1).isdigit() and original_value_str.count('.') <= 1:
            value = float(original_value_str)
    
        # Validar valor y obtener default si es necesario
        validated_value = self._validate_value(param, value)
    
        # Guardar información para notificaciones (opcional, podría ser atributo temporal)
        self._last_validation = {
            'param': param,
            'original_value': original_value_str,
            'validated_value': validated_value,
            'was_invalid': value is None or (isinstance(value, (int, float)) and value != validated_value)
        }
    
        # Retornar dict simple para actualización
        return {param: validated_value}

    def get_last_validation(self) -> dict:
        """Obtener la última validación realizada"""
        return getattr(self, '_last_validation', {})
        
    def set_panel_width(self, user_id: str, width_cm: float) -> bool:
        """Establecer el ancho del panel en centímetros"""
        try:
            config = self.get_user_config(user_id)
            config['panel_dimensions']['width_cm'] = float(width_cm)
            self._configs['users'][user_id] = config
            return self._save_configs()
        except Exception as e:
            print(f"Error estableciendo ancho: {e}")
            return False

    def set_panel_height(self, user_id: str, height_cm: float) -> bool:
        """Establecer el alto del panel en centímetros"""
        try:
            config = self.get_user_config(user_id)
            config['panel_dimensions']['height_cm'] = float(height_cm)
            self._configs['users'][user_id] = config
            return self._save_configs()
        except Exception as e:
            print(f"Error estableciendo alto: {e}")
            return False

    def get_panel_dimensions(self, user_id: str) -> Dict:
        """Obtener las dimensiones del panel del usuario"""
        config = self.get_user_config(user_id)
        return config.get('panel_dimensions', {"width_cm": 45.0, "height_cm": 20.0, "unit": "cm"})

    def cleanup_obsolete_colors(self, user_id: str, active_categories: List[str]) -> bool:
        """Elimina colores de categorías que ya no existen en el sistema"""
        try:
            config = self.get_user_config(user_id)
            model_colors = config.get('model_colors', {})
        
            if not model_colors:
                return True
        
            # Identificar categorías obsoletas
            obsolete = [cat for cat in model_colors.keys() if cat not in active_categories]
        
            if obsolete:
                for cat in obsolete:
                    del model_colors[cat]
                config['model_colors'] = model_colors
                self._save_configs()
                print(f"🧹 Usuario {user_id}: limpiados colores obsoletos: {obsolete}")
        
            return True
        except Exception as e:
            print(f"Error limpiando colores obsoletos para {user_id}: {e}")
            return False

    def get_model_colors(self, user_id: str, categories: List[str]) -> Dict[str, List[int]]:
        """Obtiene colores para todas las categorías, limpiando obsoletos y asignando nuevos"""
        config = self.get_user_config(user_id)
        model_colors = config.get('model_colors', {})
    
        # Limpiar colores obsoletos (categorías que ya no existen)
        obsolete = [cat for cat in model_colors.keys() if cat not in categories]
        if obsolete:
            for cat in obsolete:
                del model_colors[cat]
            print(f"🧹 Limpiados colores obsoletos para usuario {user_id}: {obsolete}")
    
        # Paleta de colores por defecto
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
    
        # Asignar colores a categorías nuevas
        modified = False
        for i, category in enumerate(categories):
            if category not in model_colors:
                color = default_palette[i % len(default_palette)]
                model_colors[category] = color
                modified = True
    
        # Guardar si hubo cambios
        if modified or obsolete:
            config['model_colors'] = model_colors
            self._save_configs()
    
        return model_colors

    def get_model_selection(self, user_id: str, categories: List[str]) -> Dict[str, str]:
        """Obtiene la selección de modelos del usuario"""
        config = self.get_user_config(user_id)
        selection = config.get('model_selection', {}).copy()
    
        # Asegurar que todas las categorías tengan un valor por defecto
        for category in categories:
            if category not in selection:
                # Usar 'unet' como default si existe, sino el primero disponible
                selection[category] = 'unet'
    
        return selection

    def update_model_selection(self, user_id: str, category: str, variant: str) -> bool:
        """Actualiza la selección de modelo para una categoría"""
        try:
            config = self.get_user_config(user_id)
            if 'model_selection' not in config:
                config['model_selection'] = {}
        
            config['model_selection'][category] = variant
            self._configs['users'][user_id] = config
            return self._save_configs()
        except Exception:
            return False

    def get_individual_results_config(self, user_id: str, categories: List[str]) -> Dict[str, bool]:
        """Obtiene la configuración de resultados individuales por modelo"""
        config = self.get_user_config(user_id)
        per_model = config.get('individual_results_per_model', {})
    
        # Asegurar que todas las categorías tengan valor
        for category in categories:
            if category not in per_model:
                per_model[category] = True  # Default: true
        
        return per_model

    def update_individual_result(self, user_id: str, category: str, enabled: bool) -> bool:
        """Actualiza la configuración de resultados individuales para una categoría"""
        try:
            config = self.get_user_config(user_id)
            if 'individual_results_per_model' not in config:
                config['individual_results_per_model'] = {}
            
            config['individual_results_per_model'][category] = enabled
            self._configs['users'][user_id] = config
            return self._save_configs()
        except Exception:
            return False

    def get_config_summary(self, user_id: str, model_manager=None) -> str:
        """Obtener resumen formateado de la configuración del usuario"""
        config = self.get_user_config(user_id)
    
        summary = [
            "⚙️ Your current settings:",
            "*Submission format:*",
            f"  • Combined: {'✅' if config['auto_send_combined'] else '❌'}",
            f"  • Format: {config['preferred_format']}",
            "*Display:*",
            f"  • Intensity: {config['highlight_intensity']:.1%}",
            f"  • Threshold: {config['confidence_threshold']:.1%}",
            "*Processing:*",
            f"  • Quality: {config['processing_options']['quality']}%",
            f"  • Maximum size: {config['processing_options']['max_image_size']}px",
            f"  • Verbose mode: {'✅' if config['verbose_mode'] else '❌'}",
            "*Notifications:*",
            f"  • Start: {'✅' if config['notifications']['on_start'] else '❌'}",
            f"  • Success: {'✅' if config['notifications']['on_complete'] else '❌'}",
            f"  • Error: {'✅' if config['notifications']['on_error'] else '❌'}",
        ]
    
        # Agregar selección de modelos si hay categorías disponibles
        if model_manager and model_manager.get_categories():
#            summary.append("")
            summary.append("*Model selection:*")
            selection = config.get('model_selection', {})
            for category in model_manager.get_categories():
                current = selection.get(category, 'unet')
                role = model_manager.get_role(category)
                role_icon = {'scale': '📏', 'reference': '🔨', 'content': '🍯'}.get(role, '📁')
                if current == 'none':
                    current_display = "DISABLED"
                else:
                    current_display = current.upper()
                summary.append(f"  {role_icon} {category}: {current_display}")
            summary.append("Use /set\_model to change models")

        # Agregar configuración de colores por modelo
        if model_manager and model_manager.get_categories():
#            summary.append("")
            summary.append("*Model colors:*")
            model_colors = config.get('model_colors', {})
            for category in model_manager.get_categories():
                color = model_colors.get(category, [0, 0, 0])
                color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                summary.append(f"  • {category}: {color_hex}")
            summary.append("Use /set\_color <category> <R,G,B> to change colors")
    
        # Agregar configuración de resultados individuales por modelo
        if model_manager and model_manager.get_categories():
#            summary.append("")
            summary.append("*Individual results per model:*")
            per_model = config.get('individual_results_per_model', {})
            for category in model_manager.get_categories():
                enabled = per_model.get(category, True)
                status = "✅ enabled" if enabled else "❌ disabled"
                summary.append(f"  • {category}: {status}")
            summary.append("Use /set\_individual <category> <true/false> to change")
    
        summary.extend([
            "*Useful commands:*",
            "/config - View settings",
            "/set <parameter> <value> - Change general settings",
            "/set\_individual - Change individual results per model",
            "/set\_model - Change AI models",
            "/reset\_config - Reset all settings"
        ])
    
        return "\n".join(summary)
