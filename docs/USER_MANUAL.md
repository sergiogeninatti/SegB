# SegB User Manual

**SegB** is a Telegram bot for the automatic analysis of images of honeycombs. It provides beekeepers and researchers with quantitative estimates of:

- Area of capped honey (cm² and percentage)
- Area of built comb
- Automatic scale calculation based on the frame dimensions

---

## 1. Requirements

- Telegram App ([Android](https://play.google.com/store/apps/details?id=org.telegram.messenger) | [iOS](https://apps.apple.com/app/telegram/id686449807))
- Active Telegram account
- Internet connection for sending images

---

## 2. Getting Started

### 2.1. Search for the bot

Open Telegram and search for: **`@abejagraficabot`**

### 2.2. Start the conversation

Press **“Start”** or enter the command `/start`

### 2.3. Request Registration

Enter the command: **`/login`**

### 2.4. Wait for approval

The system administrator will receive your request and notify you once it has been approved.

### 2.5. Set the dimensions of the frame

Once the administrator has approved the use of the bot, send the following commands (values in centimeters):
/width 45
/height 20

Check the settings using:
/frame



> **Note:** The dimensions are stored permanently. This step is only necessary once per apiary, provided that all frames have the same dimensions.

---

## 3. Using the bot

### 3.1. Submitting an Image for Analysis

**Important:** Send the image as a **document**, not as a photo. Telegram compresses photos, which reduces the resolution and may affect the accuracy of the analysis.

**Steps:**

1. Open the chat with `@abejagraficabot`
2. Tap the attach icon (📎) → **“Document”** (or “File”)
3. Select the image of the honeycomb from your gallery
4. Upload the image

The bot will process the image and return the results in a few seconds.

> If the user submits the image as a photo, the bot will process it but display a warning about the potential loss of accuracy.

---

## 4. Command Reference

### 4.1. General Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and system information |
| `/login` | Request user registration |
| `/logout` | Remove your registration from the bot |
| `/config` | Show current settings |
| `/reset_config` | Restore default settings |
| `/stats` | Show system statistics (available models, etc.) |

### 4.2. Configuration Commands

| Command | Description |
|---------|-------------|
| `/set <parameter> <value>` | Modify configuration parameters (see Section 5) |
| `/set_model <category> <variant>` | Change the AI model for a category |
| `/set_individual <category> <true/false>` | Enable/disable individual results per model |
| `/set_color <category> <R,G,B>` | Change the color of the overlay mask for a category |

### 4.3. Dimension Commands

| Command | Description |
|---------|-------------|
| `/width <cm>` | Set the frame width in centimeters (e.g., `/width 50`) |
| `/height <cm>` | Set the frame height in centimeters |
| `/frame` | Display the current frame dimensions |

---

## 5. Configuration Parameters (`/set`)

| Parameter | Values | Description |
|-----------|---------|-------------|
| `auto_combined` | `true` / `false` | Automatically send the combined image with all detections |
| `intensity` | `0.0` – `1.0` | Highlight intensity in the result images |
| `threshold` | `0.0` – `1.0` | Confidence threshold for detections (recommended: `0.5`) |
| `format` | `photo` / `document` | Output format for result images |
| `verbose` | `true` / `false` | Show detailed processing information |
| `quality` | `1` – `100` | JPEG quality of the output images |
| `max_size` | `320` – `4096` | Maximum image size in pixels |
| `notify_start` | `true` / `false` | Send a notification when the analysis begins |
| `notify_complete` | `true` / `false` | Send a notification when the analysis finishes |
| `notify_error` | `true` / `false` | Send a notification if an error occurs |

**Examples:**
/set auto_combined false
/set intensity 0.6
/set threshold 0.7
/set format document

---

## 6. Color Customization

Use `/set_color` to change the colors of the overlay masks (Note that RGB values range from 0 to 255):
/set_color frame 255,0,0 # Red for the frame
/set_color cells 0,0,255 # Blue for built cells
/set_color honey 0,255,0 # Green for honey

---

## 7. Results

After sending an image, the bot responds with:

### 7.1. Text Summary (Example)
✅ Processing complete
• Time: 3.2s
📏 Frame: 900 cm²
🔨 Cells: 720 cm² (80.0% of the frame)
🍯 Honey: 450 cm² (50.0% of the cells)


### 7.2. Images with Masks (Default Colors)

- **Red**: Frame (FrameModel)
- **Blue**: Built cells (BuiltModel)
- **Green**: Caped honey (HoneyModel)

### 7.3. Combined image (if `auto_combined` is enabled)

A single image showing all detections overlaid.

---

## 8. Frequently Asked Questions (FAQ)

**8.1. Does the Telegram bot store my images?**

If you agree to use this bot, images may be stored anonymously. These images will be used solely and exclusively for research purposes to improve the quality of the results. Users may request the deletion of their data by contacting the administrator.

**8.2. What should I do if the Telegram bot isn't responding?**

1. Check your Internet connection.
2. If it takes more than a minute, resend the image.
3. If the problem persists, contact the administrator.

**8.3. Can I send multiple images at once?**

Yes. The bot processes the images sequentially and returns the results for each one.

**8.4. Why does the message “You are not registered” appear?**

Registration is not yet complete. Submit `/login` and wait for the administrator's approval.

**8.5. What does the message “Frame not valid” mean?**

The frame detection model identified more than one region as the frame boundary. Make sure the image includes the entire frame, without any shadows or occlusions that might split it.

**8.6. Can I use the bot without an internet connection?**

Currently, an internet connection is required to transmit the images to the processing server.

**8.7. How accurate are the results?**

Accuracy depends on image quality. Under optimal conditions (good lighting, sharp focus, full frame), segmentation accuracy exceeds 90%.

**8.8. Can I change the AI model?**

Yes. Use `/set_model <category> <variant>` to choose from the available architectures (e.g., `unet`, `fpn`, `linknet`). The default value is `unet`. Please note that different models may result in a longer response time for the results.

---

## 9. Technical Support

For issues or suggestions:

- **e-mail:** `foco@fceia.unr.edu.ar`
- **Issue Tracker on GitHub:** `https://github.com/sergiogeninatti/SegB/issues`

---

## 10. Release History

| Version | Date | Summary of Changes |
|---------|-------|---------------------|
| v1.0.0 | May 2026 | Stable Release. FrameModel, BuiltModel, and ConMod models with configurable commands. |

---

**© 2026 Proyecto SegB**

