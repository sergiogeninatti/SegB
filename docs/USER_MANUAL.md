# Manual de Usuario: SegB

**SegB** es un bot de Telegram para el análisis automático de imágenes de panales de abejas. Proporciona a apicultores e investigadores estimaciones cuantitativas de:

- Área de miel operculada (cm² y porcentaje)
- Área de celdas construidas
- Cálculo automático de escala a partir de las dimensiones del cuadro

---

## 1. Requisitos

- Aplicación Telegram instalada ([Android](https://play.google.com/store/apps/details?id=org.telegram.messenger) | [iOS](https://apps.apple.com/app/telegram/id686449807))
- Cuenta de Telegram activa
- Conexión a internet para el envío de imágenes

---

## 2. Primeros pasos

### 2.1. Localizar el bot

Abra Telegram y busque: **`@abejagraficabot`**

### 2.2. Iniciar la conversación

Presione **"Iniciar"** o envíe el comando `/start`

### 2.3. Solicitar registro

Envíe el comando: **`/login`**

### 2.4. Esperar la aprobación

El administrador del sistema recibirá su solicitud y le notificará una vez aprobada.

### 2.5. Configurar las dimensiones del cuadro

Una vez aprobado, envíe los siguientes comandos (valores en centímetros):
/width 45
/height 20

text

Verifique la configuración con:
/frame

text

> **Nota:** Las dimensiones se almacenan de forma permanente. Este paso solo es necesario una vez por apiario, siempre que todos los cuadros tengan las mismas dimensiones.

---

## 3. Uso del bot

### 3.1. Envío de una imagen para análisis

**Importante:** Envíe la imagen como **documento**, no como foto. Telegram comprime las fotos, lo que reduce la resolución y puede afectar la precisión del análisis.

**Procedimiento:**

1. Abra el chat con `@abejagraficabot`
2. Toque el icono de adjuntar (📎) → **"Documento"** (o "File")
3. Seleccione la imagen del cuadro de panal desde su galería
4. Envíe

El bot procesará la imagen y devolverá los resultados en pocos segundos.

> Si envía la imagen como foto, el bot la procesará pero mostrará una advertencia sobre la posible pérdida de precisión.

---

## 4. Referencia de comandos

### 4.1. Comandos generales

| Comando | Descripción |
|---------|-------------|
| `/start` | Mensaje de bienvenida e información del sistema |
| `/login` | Solicitar registro de usuario |
| `/logout` | Eliminar su registro del bot |
| `/config` | Mostrar la configuración actual |
| `/reset_config` | Restaurar la configuración por defecto |
| `/stats` | Mostrar estadísticas del sistema (modelos disponibles, etc.) |

### 4.2. Comandos de configuración

| Comando | Descripción |
|---------|-------------|
| `/set <parámetro> <valor>` | Modificar parámetros de configuración (ver Sección 5) |
| `/set_model <categoría> <variante>` | Cambiar el modelo de IA para una categoría |
| `/set_individual <categoría> <true/false>` | Activar/desactivar resultados individuales por modelo |
| `/set_color <categoría> <R,G,B>` | Cambiar el color de la máscara de superposición para una categoría |

### 4.3. Comandos de dimensiones

| Comando | Descripción |
|---------|-------------|
| `/width <cm>` | Establecer el ancho del cuadro en centímetros (ej. `/width 50`) |
| `/height <cm>` | Establecer el alto del cuadro en centímetros |
| `/frame` | Mostrar las dimensiones actuales del cuadro |

---

## 5. Parámetros de configuración (`/set`)

| Parámetro | Valores | Descripción |
|-----------|---------|-------------|
| `auto_combined` | `true` / `false` | Enviar automáticamente la imagen combinada con todas las detecciones |
| `intensity` | `0.0` – `1.0` | Intensidad del resaltado en las imágenes de resultado |
| `threshold` | `0.0` – `1.0` | Umbral de confianza para las detecciones (recomendado: `0.5`) |
| `format` | `photo` / `document` | Formato de salida para las imágenes de resultado |
| `verbose` | `true` / `false` | Mostrar información detallada del procesamiento |
| `quality` | `1` – `100` | Calidad JPEG de las imágenes de salida |
| `max_size` | `320` – `4096` | Tamaño máximo de la imagen en píxeles |
| `notify_start` | `true` / `false` | Enviar notificación cuando comienza el análisis |
| `notify_complete` | `true` / `false` | Enviar notificación cuando finaliza el análisis |
| `notify_error` | `true` / `false` | Enviar notificación si ocurre un error |

**Ejemplos:**
/set auto_combined false
/set intensity 0.6
/set threshold 0.7
/set format document

text

---

## 6. Personalización de colores

Utilice `/set_color` para cambiar los colores de las máscaras de superposición:
/set_color frame 255,0,0 # Rojo para el marco
/set_color cells 0,0,255 # Azul para celdas construidas
/set_color honey 0,255,0 # Verde para la miel

text

Los valores RGB van de 0 a 255.

---

## 7. Interpretación de los resultados

Tras enviar una imagen, el bot devuelve:

### 7.1. Resumen de texto (ejemplo)
✅ Procesamiento completado
• Tiempo: 3.2s
📏 Marco: 900 cm²
🔨 Celdas: 720 cm² (80.0% del marco)
🍯 Miel: 450 cm² (50.0% de las celdas)

text

### 7.2. Imágenes con máscaras (colores por defecto)

- **Rojo**: Marco (FrameModel)
- **Azul**: Celdas construidas (BuiltModel)
- **Verde**: Miel operculada (HoneyModel)

### 7.3. Imagen combinada (si `auto_combined` está activado)

Una única imagen que muestra todas las detecciones superpuestas.

---

## 8. Preguntas frecuentes (FAQ)

**8.1. ¿El bot almacena mis imágenes?**

Sí. Las imágenes se almacenan de forma anónima exclusivamente para fines de investigación (validación de modelos, ampliación del conjunto de datos). Puede solicitar la eliminación de sus datos contactando al administrador.

**8.2. ¿Qué debo hacer si el bot no responde?**

1. Verifique su conexión a internet.
2. Si pasa más de un minuto, reenvíe la imagen.
3. Si el problema persiste, contacte al administrador por correo electrónico.

**8.3. ¿Puedo enviar varias imágenes a la vez?**

Sí. El bot procesa las imágenes de forma secuencial y devuelve los resultados para cada una.

**8.4. ¿Por qué aparece el mensaje "You are not registered"?**

Aún no ha completado el registro. Envíe `/login` y espere la aprobación del administrador.

**8.5. ¿Qué significa "Frame not valid"?**

El modelo de detección de marco identificó más de una región como límite del marco. Asegúrese de que la imagen incluya el marco completo, sin sombras ni oclusiones que puedan dividirlo.

**8.6. ¿Puedo usar el bot sin conexión a internet?**

No. El bot requiere conexión a internet para transmitir las imágenes al servidor de procesamiento.

**8.7. ¿Qué precisión tienen los resultados?**

La precisión depende de la calidad de la imagen. En condiciones óptimas (buena iluminación, enfoque nítido, marco completo), la precisión de segmentación supera el 90%.

**8.8. ¿Puedo cambiar el modelo de IA?**

Sí. Utilice `/set_model <categoría> <variante>` para seleccionar entre las arquitecturas disponibles (ej. `unet`, `fpn`, `linknet`). El valor por defecto es `unet`.

---

## 9. Soporte técnico

Para incidencias o sugerencias:

- **Correo electrónico:** `foco@fceia.unr.edu.ar`
- **Gestor de incidencias en GitHub:** `https://github.com/sergiogeninatti/SegB/issues`

---

## 10. Historial de versiones

| Versión | Fecha | Resumen de cambios |
|---------|-------|---------------------|
| v1.0.0 | Mayo 2026 | Versión inicial estable. Modelos Frame, Built y Honey con comandos configurables. |

---

**© 2026 Proyecto SegB**

