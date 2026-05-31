# SegB - Telegram Bot for Honeycomb Image Analysis

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
[![TensorFlow 2.10](https://img.shields.io/badge/TensorFlow-2.10-orange.svg)](https://tensorflow.org/)
[![Docker](https://img.shields.io/badge/Docker-20.10+-blue.svg)](https://docker.com/)

## 📌 Description

**SegB** (Segmentation Bot) is a Telegram bot that provides access to deep learning models for automatic analysis of honeycomb images. It integrates three segmentation models:

- **FrameModel**: Detects the wooden frame boundaries and computes pixel-to-centimeter scale.
- **BuiltModel**: Segments the total area of built cells within the frame.
- **ConMod/HoneyModel**: Segments capped honey areas, which is particularly challenging due to the continuous wax layer that hides cell boundaries.

The bot offloads all computational requirements to a central server using Docker, freeing end users (beekeepers and agronomists) from needing powerful hardware or managing software updates.

## 🎯 Scientific Contribution

This work is described in the paper:

> **SegB: Plataforma de servicio a apicultores y banco de pruebas para investigación del contenido de colmenas**  
> *SoftwareX (2026)*

SegB constitutes the first testbed in apiculture that combines productive extension with continuous data collection for research under real field conditions.

## 🤖 Access the Bot

The bot is publicly available on Telegram: [**@abejagraficabot**](https://t.me/abejagraficabot)

## 📋 Requirements

- Docker 20.10+ with NVIDIA Container Toolkit (for GPU acceleration)
- NVIDIA GPU with CUDA 11.8+ (recommended)
- Poetry 1.8.5+ (if running without Docker)
- Python 3.10.12 (if running without Docker)
- Telegram account

## 🚀 Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/sergiogeninatti/SegB.git
cd SegB

# Create .env file with your bot token
echo "TELEGRAM_BOTTOKEN=your_bot_token_here" > .env

# Build and run
docker-compose up -d bot
