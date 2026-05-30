import io
import os
import sys
import time
import tempfile
import cv2
import numpy as np
import tensorflow as tf
from pathlib import Path
import mimetypes
import json
import logging
import re

from pending_requests import PendingRequestsManager
from model_manager import ModelManager

# ID del administrador
ADMIN_ID = 891966079

# Suprimir warnings y logs innecesarios
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.get_logger().setLevel('ERROR')
cv2.setLogLevel(0)

# Configurar logging mínimo para producción
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)

from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from honey_segmentation_model import MultiModelProcessor
from user_config import UserConfigManager

DEBUG_DIR = os.getenv('DEBUG_DIR', '/app/debug')
USER_DATA_FILE = "users_data.json"
USER_DATA_PATH = Path(DEBUG_DIR) / USER_DATA_FILE
Path(DEBUG_DIR).mkdir(parents=True, exist_ok=True)

copyfecha = 2026
start_text = f"Graphic analysis of hives\n(c) UCO {copyfecha}"

# Inicializar gestor de solicitudes pendientes
pending_manager = PendingRequestsManager(DEBUG_DIR)

def get_actions_for_user(is_admin: bool = False) -> str:
    """Retorna la lista de comandos disponibles"""
    acciones = "The possible actions are:\n" + \
               "Send an image as a document or the following commands:\n" + \
               "`/logout`: Cancel your registration\n" + \
               "`/config`: View your configuration\n" + \
               "`/set`: Change configuration\n" + \
               "`/set_model`: Model Selection\n" + \
               "`/set_individual`: Individual results per model\n" + \
               "`/set_color`: Change model colors\n" + \
               "`/reset_config`: Reset to defaults\n" + \
               "`/width`: Set panel width (cm)\n" + \
               "`/height`: Set panel height (cm)\n" + \
               "`/frame`: Show frame dimensions\n"
    
    if is_admin:
        acciones += "\n*Admin commands:*\n"
        acciones += "`/who`: List registered users\n"
        acciones += "`/allow <id>`: Approve user registration\n"
        acciones += "`/reject <id>`: Reject user registration\n"
    
    return acciones
    
def calculate_scale_from_areas(frame_area_px, user_config):
    """
    Calcula la escala usando la relación de áreas
    frame_area_px: área del frame detectada en píxeles
    user_config: configuración con panel_dimensions (width_cm, height_cm)
    """
    if not frame_area_px or frame_area_px <= 0:
        return None
    
    real_area_cm2 = user_config['panel_dimensions']['width_cm'] * user_config['panel_dimensions']['height_cm']
    
    if real_area_cm2 <= 0:
        return None
    
    scale_cm2_per_px = real_area_cm2 / frame_area_px
    scale_cm_per_px = scale_cm2_per_px ** 0.5
    
    return {
        'scale_cm2_per_px': scale_cm2_per_px,
        'scale_cm_per_px': scale_cm_per_px,
        'frame_area_px': frame_area_px,
        'frame_area_cm2': real_area_cm2
    }

def load_users_data():
    try:
        if USER_DATA_PATH.exists():
            with open(USER_DATA_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "usuarios": {},
        "last_updated": datetime.now().isoformat(),
        "total_users": 0
    }

def save_users_data(data):
    try:
        data['last_updated'] = datetime.now().isoformat()
        data['total_users'] = len(data['usuarios'])
        with open(USER_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

users_data = load_users_data()
config_manager = UserConfigManager(DEBUG_DIR)
model_manager = ModelManager('/app/model')

async def send_image_result(context, chat_id, image_bytes, filename, caption, preferred_format, parse_mode=None):
    """Envía una imagen como foto o documento según configuración"""
    if preferred_format == 'photo':
        return await context.bot.send_photo(
            chat_id=chat_id, 
            photo=image_bytes,
            caption=caption,
            parse_mode=parse_mode
        )
    else:
        return await context.bot.send_document(
            chat_id=chat_id, 
            document=io.BytesIO(image_bytes),
            filename=filename,
            caption=caption,
            parse_mode=parse_mode
        )

async def process_image_in_memory(image_bytes, update, context):
    user = update.message.from_user
    identificacion = str(user.id)
    
    debug_dir = os.getenv('DEBUG_DIR', '/app/debug')
    debug_path = Path(debug_dir)
    if not debug_path.exists():
        debug_path.mkdir(parents=True, exist_ok=True)

    user_config = config_manager.get_user_config(identificacion)

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            await update.message.reply_text("Error: Could not decode image.")
            return

        # Guardar dimensiones originales
        original_height, original_width = img.shape[:2]
        original_max_dim = max(original_height, original_width)
        max_size = user_config['processing_options']['max_image_size']
    
        # Redimensionar si es necesario
        if original_max_dim > max_size:
            scale = max_size / original_max_dim
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            img = cv2.resize(img, (new_width, new_height))
            image_bytes = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, user_config['processing_options']['quality']])[1].tobytes()

        if user_config['verbose_mode']:
            info_msg = (
                f" Image received\n"
                f"• Resolution: {original_width}×{original_height} px"
            )
            
            if original_max_dim > max_size:
                new_h, new_w = img.shape[:2]
                info_msg += f"\n• Resized to: {new_w}×{new_h} (limit: {max_size}px)"
            
            info_msg += f"\n• Models: {len(model_manager.get_categories())}"
            await update.message.reply_text(info_msg)
                
        # Crear procesador con los modelos del usuario
        processor = MultiModelProcessor(model_manager, user_config)

        if len(processor.models) == 0:
            await update.message.reply_text(
                "⚠️ No models enabled for processing.\n"
                "Use `/set_model` to enable at least one model category.",
                parse_mode='Markdown'
            )
            return            
            
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name

        try:
            # Mensaje de inicio - simplificado
            start_msg = f"Processing with {len(processor.models)} models..."
            if user_config['notifications']['on_start']:
                start_msg += f"\nThreshold of trust: {user_config['confidence_threshold']:.0%}"
            await update.message.reply_text(start_msg)
            
            start_time = time.time()
            
            result = processor.process_image(
                temp_file_path, 
                user_config=user_config
            )            
                        
            process_time = time.time() - start_time
            models_processed = result['total_models_processed']
            individual_results = result.get('individual_results', [])
                        
            # Mensaje de completado - con roles dinámicos
            # Separar resultados por rol
            frame_result = None
            cells_result = None
            content_results = []

            for res in individual_results:
                model_name = res.get('model_name', '').lower()
                if 'frame' in model_name:
                    frame_result = res
                elif 'cells' in model_name or 'built' in model_name:
                    cells_result = res
                else:
                    content_results.append(res)

            # Obtener áreas
            frame_area_px = None
            cells_area_px = None
            frame_info = None

            if frame_result:
                frame_info = frame_result.get('frame_info')
                if frame_info:
                    frame_area_px = frame_info.get('area_px', 0)

            if cells_result:
                cells_area_px = cells_result.get('metrics', {}).get('honey_pixels', 0)

            # Calcular escala (solo si hay frame válido)
            scale_info = None
            if frame_area_px and frame_area_px > 0:
                if frame_info and frame_info.get('is_valid'):
                    scale_info = calculate_scale_from_areas(frame_area_px, user_config)

            # Construir mensaje de completado
            status_text = "Processing completed"
            status_msg = f"✅ {status_text}\n• Time: {process_time:.1f}s"

            # Frame (escala)
            if scale_info:
                status_msg += f"\n📏 Frame: {scale_info['frame_area_cm2']:.0f} cm²"
            elif frame_area_px and frame_area_px > 0:
                status_msg += f"\n📏 Frame detected (area: {frame_area_px:,} px²)"

            # Cells (referencia)
            if cells_area_px and cells_area_px > 0:
                if frame_area_px and frame_area_px > 0:
                    cells_pct_of_frame = (cells_area_px / frame_area_px) * 100
                    if scale_info:
                        cells_cm2 = (cells_pct_of_frame / 100) * scale_info['frame_area_cm2']
                        status_msg += f"\n🔨 Cells: {cells_cm2:.0f} cm² ({cells_pct_of_frame:.1f}% of frame)"
                    else:
                        status_msg += f"\n🔨 Cells: {cells_pct_of_frame:.1f}% of frame"
                else:
                    status_msg += f"\n Cells detected (area: {cells_area_px:,} px²)"

            # Contenido (honey, larvae, pollen, etc.)
            emoji_map = {
                'honey': '🍯',
                'larvae': '🐛',
                'pollen': '🌼',
                'eggs': '🥚',
                'empty': '⬜'
            }

            for content in content_results:
                model_name = content.get('model_name', '').replace(' Detection', '').lower()
                metrics = content.get('metrics', {})
                area_px = metrics.get('honey_pixels', 0)
                
                if area_px == 0:
                    continue
                
                emoji = emoji_map.get(model_name, '📊')
                display_name = model_name.capitalize()
                
                # Calcular métricas disponibles
                metrics_parts = []
                
                # Porcentaje sobre celdas (referencia)
                if cells_area_px and cells_area_px > 0:
                    pct_of_cells = (area_px / cells_area_px) * 100
                    metrics_parts.append(f"{pct_of_cells:.1f}% of cells")
                
                # Porcentaje sobre frame y cm²
                if frame_area_px and frame_area_px > 0:
                    pct_of_frame = (area_px / frame_area_px) * 100
                    if scale_info:
                        area_cm2 = (pct_of_frame / 100) * scale_info['frame_area_cm2']
                        metrics_parts.append(f"{area_cm2:.0f} cm² ({pct_of_frame:.1f}% of frame)")
                    else:
                        metrics_parts.append(f"{pct_of_frame:.1f}% of frame")
                
                if metrics_parts:
                    status_msg += f"\n{emoji} {display_name}: {', '.join(metrics_parts)}"
                elif area_px > 0:
                    status_msg += f"\n{emoji} {display_name}: detected"

            # Advertencias
            if frame_info and not frame_info.get('is_valid'):
                status_msg += f"\n\n⚠️ Frame: {frame_info.get('num_regions', 0)} regions detected"
            
            if not frame_area_px and not cells_area_px and not content_results:
                status_msg += f"\n\n⚠️ No detections made"
                
            if user_config['notifications']['on_complete']:
                status_msg = status_msg.replace(status_text, f"*{status_text}*")
                await update.message.reply_text(status_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(status_msg)
        
            # Obtener configuración individual por modelo
            categories_list = []
            for res in individual_results:
                name = res.get('model_name', '').replace(' Detection', '').lower()
                categories_list.append(name)
            
            per_model = config_manager.get_individual_results_config(identificacion, categories_list)
            
            for i, model_result in enumerate(individual_results, 1):
                model_name = model_result.get('model_name', f'Modelo {i}')
                category = model_name.lower().replace(' detection', '')
                
                # Verificar si este modelo debe enviarse
                if not per_model.get(category, True):
                    continue
                
                highlighted_img = model_result['highlighted_image']
                
                _, highlighted_bytes = cv2.imencode(
                    '.jpg', 
                    cv2.cvtColor(highlighted_img, cv2.COLOR_RGB2BGR), 
                    [cv2.IMWRITE_JPEG_QUALITY, user_config['processing_options']['quality']]
                )
                
                metrics = model_result.get('metrics', {})
                caption = f"{'*' if user_config['verbose_mode'] else ''}{model_name}{'*' if user_config['verbose_mode'] else ''}\n"
                caption += f"Regions: {metrics.get('num_regions', 0)}"
                
                try:
                    await send_image_result(
                        context, 
                        update.effective_chat.id, 
                        highlighted_bytes.tobytes(),
                        f"resultado_{model_name.replace(' ', '_')}.jpg",
                        caption,
                        user_config['preferred_format'],
                        'Markdown' if user_config['verbose_mode'] else None
                    )
                except Exception:
                    # Fallback a documento si hay error
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id, 
                        document=io.BytesIO(highlighted_bytes),
                        filename=f"resultado_{model_name.replace(' ', '_')}.jpg",
                        caption=caption
                    )
                
                time.sleep(0.5)

            if user_config['auto_send_combined']:
                combined_result = result.get('combined_result')
                if combined_result and combined_result.get('highlighted_image') is not None:
                    combined_img = combined_result['highlighted_image']
                    
                    _, combined_bytes = cv2.imencode(
                        '.jpg', 
                        cv2.cvtColor(combined_img, cv2.COLOR_RGB2BGR), 
                        [cv2.IMWRITE_JPEG_QUALITY, user_config['processing_options']['quality']]
                    )
                    
                    combined_caption = "🎨 Combined image with all detections:\n"
                    colors = ["🔴 Frame", "🟢 Honey", "🔵 Built Cells"]
                    for i, color in enumerate(colors[:len(individual_results)]):
                        combined_caption += f"{color} • "
                    combined_caption = combined_caption.rstrip(" • ")
                    
                    if user_config['verbose_mode']:
                        combined_caption = f"*{combined_caption}*"
                                    
                    try:
                        await send_image_result(
                            context,
                            update.effective_chat.id,
                            combined_bytes.tobytes(),
                            "resultado_combinado.jpg",
                            combined_caption,
                            user_config['preferred_format'],
                            'Markdown' if user_config['verbose_mode'] else None
                        )
                    except Exception:
                        await context.bot.send_document(
                            chat_id=update.effective_chat.id, 
                            document=io.BytesIO(combined_bytes),
                            filename="resultado_combinado.jpg",
                            caption=combined_caption
                        )

        finally:
            os.unlink(temp_file_path)

    except Exception:
        error_msg = (
            "❌ Ocurrió un error al procesar la imagen.\n"
            "Por favor, inténtelo de nuevo."
        )
        if user_config['notifications']['on_error']:
            error_msg += "\n\nPosibles causas:\n• La imagen puede estar corrupta\n• Los modelos no están cargados correctamente\n• Problema de memoria"
        
        await update.message.reply_text(error_msg)


BOT_TOKEN = os.getenv("TELEGRAM_BOTTOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_msg = start_text + "\n\n"
    
    if model_manager.get_categories():
        total_variants = 0
        for category in model_manager.get_categories():
            total_variants += len(model_manager.get_variants(category))
        
        welcome_msg += f"✅ Active system with {total_variants} model variants:\n"
        for category in model_manager.get_categories():
            variants = model_manager.get_variants(category)
            welcome_msg += f"   • {category}: {', '.join(variants)}\n"
        welcome_msg += "\n• Send an image as a document to be processed\n"
        welcome_msg += "\n Custom configuration:\n"
        welcome_msg += "• /config - View your current settings\n"
        welcome_msg += "• /set <parameter> <value> - To modify config\n"
        welcome_msg += "• /set_individual - Individual results per model\n"
        welcome_msg += "• /set_color - Change model colors\n"
        welcome_msg += "• /reset_config - Reset to default values\n"
        welcome_msg += "• /set_model - Change AI models\n"
    else:
        welcome_msg += "⚠️ **Warning:** No models loaded. Processing will not work."
    
    await update.message.reply_text(welcome_msg)
    
async def baja(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data
    user = update.message.from_user
    apellido = user.last_name or ""
    nombre = user.first_name or ""
    identificacion = user.id
    
    if str(identificacion) in users_data["usuarios"]:
        del users_data["usuarios"][str(identificacion)]
        save_users_data(users_data)
        await update.message.reply_text(
            f"{nombre} {apellido}\nThank you for trusting us\nWe hope to see you soon!"
        )
    else:
        await update.message.reply_text(
            f"Hi {nombre} {apellido}\nYou are not registered, please request registration with the command:\n/login"
        )

async def alta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data, pending_manager
    user = update.message.from_user
    apellido = user.last_name or ""
    nombre = user.first_name or ""
    identificacion = str(user.id)
    username = user.username or ""
    
    if identificacion in users_data["usuarios"]:
        await update.message.reply_text("You are already registered as a user")
        return
    
    # Verificar si ya tiene solicitud pendiente
    pending = pending_manager.get_pending(identificacion)
    if pending and pending.get('status') == 'pending':
        await update.message.reply_text(
            "⏳ Your registration request is pending approval.\n"
            "Please wait for administrator confirmation."
        )
        return
    
    # Crear solicitud pendiente
    user_info = {
        "nombre_completo": f"{nombre} {apellido}",
        "nombre": nombre,
        "apellido": apellido,
        "username": username,
        "user_id": identificacion
    }
    
    if pending_manager.add_request(identificacion, user_info):
        # Notificar al administrador
        admin_msg = (
            f" *New registration request*\n\n"
            f" *User:* {nombre} {apellido}\n"
            f" *ID:* `{identificacion}`\n"
            f" *Username:* @{username if username else 'None'}\n\n"
            f"Reply with:\n"
            f"`/allow {identificacion}` - to approve\n"
            f"`/reject {identificacion}` - to reject"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode='Markdown')
        
        await update.message.reply_text(
            f"✅ Request sent to administrator.\n"
            "You will be notified when your registration is approved."
        )
    else:
        await update.message.reply_text("❌ Error processing your request. Please try again.")

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Aprobar solicitud de registro (solo administrador)"""
    global users_data, pending_manager
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    try:
        args = context.args
        if not args:
            # Listar solicitudes pendientes
            pending = pending_manager.list_pending()
            if not pending:
                await update.message.reply_text("No pending requests.")
                return
            
            msg = " *Pending requests:*\n\n"
            for uid, data in pending.items():
                msg += f"• {data.get('nombre_completo', 'Unknown')} (ID: `{uid}`)\n"
                msg += f"  @{data.get('username', 'no username')}\n"
            msg += "\nUse:\n`/allow <id>` - to approve\n`/reject <id>` - to reject"
            await update.message.reply_text(msg, parse_mode='Markdown')
            return
        
        user_id = args[0]
        pending_data = pending_manager.get_pending(user_id)
        
        if not pending_data:
            await update.message.reply_text(f"No pending request for ID: {user_id}")
            return
        
        # Registrar usuario
        users_data["usuarios"][user_id] = {
            "nombre_completo": pending_data.get('nombre_completo', ''),
            "nombre": pending_data.get('nombre', ''),
            "apellido": pending_data.get('apellido', ''),
            "username": pending_data.get('username', ''),
            "fecha_registro": datetime.now().isoformat(),
            "ultima_conexion": datetime.now().isoformat()
        }
        
        if save_users_data(users_data) and pending_manager.approve(user_id):
            await update.message.reply_text(f"✅ User {pending_data.get('nombre_completo')} approved.")
            
            # Notificar al usuario
            try:
                is_admin = (int(user_id) == ADMIN_ID)
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"✅ Your registration has been approved!\n\n{get_actions_for_user(is_admin)}"
                )
            except Exception:
                pass
        else:
            await update.message.reply_text("❌ Error approving user.")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rechazar solicitud de registro (solo administrador)"""
    global pending_manager
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    try:
        args = context.args
        if not args:
            await update.message.reply_text("Usage: `/reject <user_id>`", parse_mode='Markdown')
            return
        
        user_id = args[0]
        pending_data = pending_manager.get_pending(user_id)
        
        if not pending_data:
            await update.message.reply_text(f"No pending request for ID: {user_id}")
            return
        
        if pending_manager.reject(user_id):
            await update.message.reply_text(f"❌ User {pending_data.get('nombre_completo')} rejected.")
            
            # Notificar al usuario
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text="❌ Your registration request has been rejected by the administrator."
                )
            except Exception:
                pass
        else:
            await update.message.reply_text("❌ Error rejecting user.")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data
    user = update.message.from_user
    apellido = user.last_name or ""
    nombre = user.first_name or ""
    identificacion = user.id

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return
        
    if str(identificacion) in users_data["usuarios"]:
        usuarios = users_data["usuarios"]
        if usuarios:
            usr_list = f"Registered users ({len(usuarios)}):\n"
            usr_list += "-" * 40 + "\n"
            
            for user_id, user_data in usuarios.items():
                nombre_completo = user_data.get('nombre_completo', 'Unknown')
                fecha_reg = user_data.get('fecha_registro', 'Unknown')[:10]
                usr_list += f"• {nombre_completo} (ID: {user_id}) - Registered: {fecha_reg}\n"
            
            usr_list += "-" * 40
        else:
            usr_list = "No registered users yet."
        
        await update.message.reply_text(usr_list)
    else:
        await update.message.reply_text(
            f"Hi {nombre} {apellido}\nYou are not registered, please request registration with the command:\n/login"
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data
    
    user = update.message.from_user
    identificacion = user.id
    
    if str(identificacion) in users_data["usuarios"]:
        total_usuarios = len(users_data["usuarios"])
        
        stats_text = f" System Statistics\n"
        stats_text += "=" * 40 + "\n"
        stats_text += f"Registered users: {total_usuarios}\n"
        stats_text += f"Latest update: {users_data.get('last_updated', 'Unknown')[:19]}\n\n"
        
        if model_manager.get_categories():
            total_variants = sum(len(model_manager.get_variants(cat)) for cat in model_manager.get_categories())
            stats_text += f"✅ Models available: {total_variants} variants\n"
            for category in model_manager.get_categories():
                variants = model_manager.get_variants(category)
                stats_text += f"   • {category}: {', '.join(variants)}\n"
        else:
            stats_text += "⚠️ No models loaded\n"
        
        stats_text += "=" * 40
        
        await update.message.reply_text(stats_text)
    else:
        await update.message.reply_text("You need to be registered to view statistics. Use /login first.")

async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data, config_manager, model_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion in users_data["usuarios"]:
        summary = config_manager.get_config_summary(identificacion, model_manager)
        await update.message.reply_text(summary, parse_mode='Markdown')
    else:
        await update.message.reply_text("You must first register with /login")
        
async def set_panel_width(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data, config_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    try:
        args = context.args
        if not args:
            dimensions = config_manager.get_panel_dimensions(identificacion)
            await update.message.reply_text(
                f" Width: {dimensions['width_cm']} cm\n"
                f" Use: /width <value> example: /width 50"
            )
            return
        
        width = float(args[0])
        if width <= 0:
            await update.message.reply_text("❌ The width must be greater than 0")
            return
        
        if config_manager.set_panel_width(identificacion, width):
            await update.message.reply_text(f"✅ Width updated to {width} cm")
        else:
            await update.message.reply_text("❌ Error saving")
    except ValueError:
        await update.message.reply_text("❌ Use: /width 45")

async def set_panel_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data, config_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    try:
        args = context.args
        if not args:
            dimensions = config_manager.get_panel_dimensions(identificacion)
            await update.message.reply_text(
                f" Height: {dimensions['height_cm']} cm\n"
                f" Use: /height <value> example: /height 20"
            )
            return
        
        height = float(args[0])
        if height <= 0:
            await update.message.reply_text("❌ The height must be greater than 0")
            return
        
        if config_manager.set_panel_height(identificacion, height):
            await update.message.reply_text(f"✅ Height updated to {height} cm")
        else:
            await update.message.reply_text("❌ Error saving")
    except ValueError:
        await update.message.reply_text("❌ Use: /height 20")
        
async def show_dimensions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data, config_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    dims = config_manager.get_panel_dimensions(identificacion)
    
    msg = f""" Frame dimensions

• Width: {dims['width_cm']} cm
• Height: {dims['height_cm']} cm
• Area: {dims['width_cm'] * dims['height_cm']:.1f} cm²

If you want to modify:
• /width 50 - to change width
• /height 25 - to change height"""
    
    await update.message.reply_text(msg)

async def set_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data, config_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    text = update.message.text.strip()
    
    # Si solo es "/set" sin parámetros, mostrar ayuda
    if text == '/set' or text == '/set@' + context.bot.username:
        help_text = (
            "⚙️ *Configuration options*\n\n"
            "Usage: `/set <parameter> <value>`\n\n"
            "*Parameters:*\n"
            "• `auto_combined` - Send combined image (true/false)\n"
            "• `intensity` - Highlight intensity (0.0-1.0)\n"
            "• `threshold` - Confidence threshold (0.0-1.0)\n"
            "• `format` - Send format (photo/document)\n"
            "• `verbose` - Verbose mode (true/false)\n"
            "• `quality` - JPEG quality (1-100)\n"
            "• `max_size` - Max image size in pixels (320-4096)\n"
            "• `notify_start` - Notify on start (true/false)\n"
            "• `notify_complete` - Notify on complete (true/false)\n"
            "• `notify_error` - Notify on error (true/false)\n\n"
            "*Examples:*\n"
            "• `/set auto_combined false`\n"
            "• `/set intensity 0.6`\n"
            "• `/set format document`\n"
            "• `/set threshold 0.7`\n\n"
            "Use `/config` to view your current settings."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    config_update = config_manager.parse_config_command(text)
    
    if config_update is None:
        await update.message.reply_text(
            "❌ Incorrect format.\n"
            "Use `/set` alone to see available options.",
            parse_mode='Markdown'
        )
        return
    
    # Obtener información de validación
    validation = config_manager.get_last_validation()
    if validation and validation.get('was_invalid'):
        param_display = validation.get('param', '').split('.')[-1]
        original = validation.get('original_value', '')
        validated = validation.get('validated_value', '')
        await update.message.reply_text(
            f"⚠️ Invalid value '{original}' for {param_display}.\n"
            f"Using: {validated}"
        )
    
    # Actualizar configuración
    success = config_manager.update_user_config(identificacion, config_update)
    
    if success:
        # Mostrar nombre amigable del parámetro
        param = list(config_update.keys())[0]
        value = list(config_update.values())[0]
        param_display = {
            'auto_send_combined': 'auto_combined',
            'highlight_intensity': 'intensity',
            'confidence_threshold': 'threshold',
            'preferred_format': 'format',
            'verbose_mode': 'verbose',
            'processing_options.quality': 'quality',
            'processing_options.max_image_size': 'max_size',
            'notifications.on_start': 'notify_start',
            'notifications.on_complete': 'notify_complete',
            'notifications.on_error': 'notify_error'
        }.get(param, param.split('.')[-1])
        
        await update.message.reply_text(
            f"✅ Configuration updated:\n• {param_display} = {value}\n\n"
            f"Use `/config` to see all values.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Error saving configuration.")
                
async def reset_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data, config_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    success = config_manager.reset_user_config(identificacion)
    
    if success:
        await update.message.reply_text(
            "✅ Configuration reset to default values.\n"
            "Use `/config` to see the new values.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Error resetting configuration.")

async def anytxt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data
    
    user = update.message.from_user
    apellido = user.last_name or ""
    nombre = user.first_name or ""
    identificacion = user.id
    
    if str(identificacion) in users_data["usuarios"]:
        users_data["usuarios"][str(identificacion)]["ultima_conexion"] = datetime.now().isoformat()
        
        if update.update_id % 10 == 0:
            save_users_data(users_data)
        
        # Determinar si es administrador
        is_admin = (identificacion == ADMIN_ID)
        acciones = get_actions_for_user(is_admin)
        
        model_info = ""
        if model_manager.get_categories():
            total_variants = sum(len(model_manager.get_variants(cat)) for cat in model_manager.get_categories())
            model_info = f"\n✅ Active system with {total_variants} model variants\nSend an image as a document for processing."
        else:
            model_info = "\n⚠️ Warning: No models loaded. Processing will not work."
        
        await update.message.reply_text(
            f"Hi {nombre} {apellido}\n"
            "You are already registered as a user\n" +
            acciones +
            model_info,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"Hi {nombre} {apellido}\nYou are not registered, please request registration with the command:\n/login"
        )

async def fotoin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data
    
    user = update.message.from_user
    nombre = user.first_name or ""
    identificacion = user.id
    apellido = user.last_name or ""
    
    if str(identificacion) not in users_data["usuarios"]:
        await update.message.reply_text(
            f"Hi {nombre} {apellido}\nYou are not registered, please request registration with the command:\n/login"
        )
        return
    
    if not model_manager.get_categories():
        await update.message.reply_text(
            "❌ Error: No models available for processing.\n"
            "Please contact the system administrator."
        )
        return
    
    # Mensaje corto advirtiendo sobre compresión
    await update.message.reply_text(
        f"📷 Photo received (compressed).\n"
        f"⚠️ Send as **DOCUMENT** for better accuracy.\n"
        f"Processing...",
        parse_mode='Markdown'
    )
    
    # Obtener la foto de mayor resolución disponible
    photo = update.message.photo[-1]  # [-1] es la de mayor resolución
    file = await context.bot.getFile(photo.file_id)
    image_bytes = await file.download_as_bytearray()
    
    # Procesar la imagen
    await process_image_in_memory(image_bytes, update, context)

async def doc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global users_data
    user = update.message.from_user
    nombre = user.first_name or ""
    apellido = user.last_name or ""
    identificacion = user.id
    
    if str(identificacion) not in users_data["usuarios"]:
        await update.message.reply_text(
            f"Hi {nombre} {apellido}\nYou are not registered, please request registration with the command:\n/login"
        )
        return
    
    if not model_manager.get_categories():
        await update.message.reply_text(
            "❌ Error: There are no models loaded for processing.\n"
            "Please contact the system administrator."
        )
        return
    
    mime_type = update.message.document.mime_type
    
    if not mime_type or not mime_type.startswith('image/'):
        await update.message.reply_text(
            "The file you submitted is not an image. Please submit an image file."
        )
        return
    
    await update.message.reply_text("✅ Image received as document")
    
    file = await context.bot.getFile(update.message.document.file_id)
    image_bytes = await file.download_as_bytearray()
    
    await process_image_in_memory(image_bytes, update, context)

async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cambiar la selección de modelo para una categoría"""
    global users_data, config_manager, model_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    args = context.args
    
    if not args:
        categories = model_manager.get_categories()
        
        if not categories:
            await update.message.reply_text("⚠️ No models available in /app/model")
            return
        
        help_text = " *Model Selection*\n\n"
        help_text += "Usage: `/set_model <category> <variant>`\n\n"
        help_text += "*Available categories:*\n"
        
        for category in categories:
            variants = model_manager.get_variants(category)
            role = model_manager.get_role(category)
            role_icon = {'scale': '📏', 'reference': '🔨', 'content': '🍯'}.get(role, '📁')
            current = config_manager.get_model_selection(identificacion, [category]).get(category, 'unet')
            if current == 'none':
                current_display = "DISABLED"
            else:
                current_display = current.upper()
            help_text += f"  {role_icon} `{category}`: {', '.join(variants)} (current: {current_display})\n"
        help_text += "\n*Examples:*\n"
        help_text += "  `/set_model frame fpn`\n"
        help_text += "  `/set_model honey unet`\n"
        help_text += "  `/set_model cells fpn`"
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    if len(args) != 2:
        await update.message.reply_text(
            "❌ Invalid format.\n"
            "Usage: `/set\_model <category> <variant>`",
            parse_mode='Markdown'
        )
        return
    
    category = args[0].lower()
    variant = args[1].lower()
    
    if category not in model_manager.get_categories():
        available = ', '.join(model_manager.get_categories())
        await update.message.reply_text(
            f"❌ Invalid category: '{category}'\n"
            f"Available: {available}"
        )
        return
    
    if not model_manager.is_valid_selection(category, variant):
        available = ', '.join(model_manager.get_variants(category))
        await update.message.reply_text(
            f"❌ Invalid variant: '{variant}' for '{category}'\n"
            f"Available: {available}"
        )
        return
    
    if config_manager.update_model_selection(identificacion, category, variant):
        await update.message.reply_text(
            f"✅ Model for '{category}' changed to: {variant.upper()}\n\n"
            f"Use `/config` to see all settings.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Error saving model selection.")

async def set_individual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configurar envío de resultados individuales por modelo"""
    global users_data, config_manager, model_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    args = context.args
    
    # Sin argumentos: mostrar ayuda
    if not args:
        categories = model_manager.get_categories()
        if not categories:
            await update.message.reply_text("⚠️ No models available")
            return
        
        help_text = "🎛️ *Individual Results Configuration*\n\n"
        help_text += "Usage: `/set_individual <category> <true/false>`\n\n"
        help_text += "*Available categories:*\n"
        
        per_model = config_manager.get_individual_results_config(identificacion, categories)
        for category in categories:
            current = per_model.get(category, True)
            status = "✅ enabled" if current else "❌ disabled"
            help_text += f"  • `{category}`: {status}\n"
        
        # Usar la primera categoría disponible como ejemplo
        example_category = categories[0]
        help_text += "\n*Examples:*\n"
        help_text += f"  `/set_individual {example_category} false`\n"
        help_text += f"  `/set_individual {example_category} true`"
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    # Validar argumentos
    if len(args) != 2:
        await update.message.reply_text(
            "❌ Invalid format.\n"
            "Usage: `/set\_individual <category> <true/false>`",
            parse_mode='Markdown'
        )
        return
    
    category = args[0].lower()
    value = args[1].lower()
    
    # Validar categoría
    if category not in model_manager.get_categories():
        available = ', '.join(model_manager.get_categories())
        await update.message.reply_text(
            f"❌ Invalid category: '{category}'\n"
            f"Available: {available}"
        )
        return
    
    # Validar valor
    if value not in ['true', 'false']:
        await update.message.reply_text(
            f"❌ Invalid value: '{value}'\n"
            "Use `true` or `false`"
        )
        return
    
    enabled = (value == 'true')
    
    # Actualizar configuración
    if config_manager.update_individual_result(identificacion, category, enabled):
        status = "enabled" if enabled else "disabled"
        await update.message.reply_text(
            f"✅ Individual results for '{category}': {status}\n\n"
            f"Use `/config` to see all settings.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Error saving configuration.")

async def set_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cambiar el color de visualización para una categoría (primer nivel)"""
    global users_data, config_manager, model_manager
    
    user = update.message.from_user
    identificacion = str(user.id)
    
    if identificacion not in users_data["usuarios"]:
        await update.message.reply_text("You must first register with /login")
        return
    
    args = context.args
    
    # Sin argumentos o argumentos incorrectos: mostrar ayuda
    if not args or len(args) != 2:
        categories = model_manager.get_categories()
        
        if not categories:
            await update.message.reply_text("⚠️ No models available")
            return
        
        help_text = "🎨 *Color Configuration*\n\n"
        help_text += "Usage: `/set_color <category> <R,G,B>`\n\n"
        help_text += "*Available categories (first level):*\n"
        
        # Obtener colores actuales
        user_config = config_manager.get_user_config(identificacion)
        model_colors = user_config.get('model_colors', {})
        
        for category in categories:
            color = model_colors.get(category, [0, 0, 0])
            color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            color_rgb = f"{color[0]},{color[1]},{color[2]}"
            # Mostrar también el rol de cada categoría
            role = model_manager.get_role(category)
            role_icon = {'scale': '📏', 'reference': '🔨', 'content': '🍯'}.get(role, '📁')
            help_text += f"  {role_icon} `{category}`: {color_hex}  ({color_rgb})\n"
        
        # Usar la primera categoría disponible como ejemplo
        example_category = categories[0]
        help_text += f"\n*Example:*\n"
        help_text += f"  `/set_color {example_category} 255,0,0`"
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    category = args[0].lower()
    color_str = args[1]
    
    # Validar categoría (debe existir en primer nivel)
    if category not in model_manager.get_categories():
        available = ', '.join(model_manager.get_categories())
        await update.message.reply_text(
            f"❌ Invalid category: '{category}'\n"
            f"Available categories: {available}"
        )
        return
    
    # Parsear color (formato: "255,0,0" o "255 0 0")
    color_str = color_str.replace(',', ' ')
    parts = color_str.split()
    
    if len(parts) != 3:
        await update.message.reply_text(
            "❌ Invalid color format.\n"
            "Use: `<R,G,B>` with values 0-255\n"
            "Example: `255,0,0` for red"
        )
        return
    
    try:
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            raise ValueError("Values out of range")
        color = [r, g, b]
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid color values.\n"
            "Use numbers between 0 and 255.\n"
            "Example: `255,0,0` for red"
        )
        return
    
    # Actualizar color en la configuración del usuario
    user_config = config_manager.get_user_config(identificacion)
    if 'model_colors' not in user_config:
        user_config['model_colors'] = {}
    
    user_config['model_colors'][category] = color
    
    if config_manager.update_user_config(identificacion, {'model_colors': user_config['model_colors']}):
        color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        color_rgb = f"{color[0]},{color[1]},{color[2]}"
        await update.message.reply_text(
            f"✅ Color for category '{category}' changed to: {color_hex}  ({color_rgb})\n\n"
            f"Use `/config` to see all settings.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Error saving color configuration.")
    
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    # Comandos específicos (todos los que empiezan con /)

    #Comandos del administrador
    application.add_handler(CommandHandler("allow", approve_user))
    application.add_handler(CommandHandler("reject", reject_user))
    application.add_handler(CommandHandler("who", listar))

    # Comandos generales
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", alta))
    application.add_handler(CommandHandler("logout", baja))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("config", show_config))
    application.add_handler(CommandHandler("set", set_config))
    application.add_handler(CommandHandler("reset_config", reset_config))
    application.add_handler(CommandHandler("width", set_panel_width))
    application.add_handler(CommandHandler("height", set_panel_height))
    application.add_handler(CommandHandler("frame", show_dimensions))    
    application.add_handler(CommandHandler("set_model", set_model))
    application.add_handler(CommandHandler("set_individual", set_individual))
    application.add_handler(CommandHandler("set_color", set_color))

    # Handlers genéricos (al final)
    application.add_handler(MessageHandler(filters.TEXT, anytxt))
    application.add_handler(MessageHandler(filters.PHOTO, fotoin))
    application.add_handler(MessageHandler(filters.Document.ALL, doc_handler))
    application.run_polling()

if __name__ == "__main__":
    main()
