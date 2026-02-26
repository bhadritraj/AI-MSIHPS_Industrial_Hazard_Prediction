# AI-Powered Multi-Sensor Industrial Hazard Prediction System (AI-MSIHPS)

Predicting industrial hazards before they become fatal.

---

## Overview

AI-MSIHPS is a distributed IoT + AI-based industrial safety system designed to **predict hazardous conditions before they become critical**.

This system is built for:

- Chemical factories  
- Sewage treatment plants  
- Confined spaces  
- Underground chambers  
- Boiler rooms  

Unlike traditional systems that trigger alarms only after thresholds are crossed, our system uses **Machine Learning + Sensor Fusion** to forecast unsafe conditions 30–60 minutes in advance.

---

## Problem Statement

Current industrial safety systems:

- Detect danger only after gas thresholds are crossed  
- Rely on manual inspection before entry  
- Lack continuous predictive monitoring  
- Provide no intelligent risk forecasting  

This leads to delayed evacuation and worker fatalities.
  
Predictive AI-powered safety system  

---

##  Proposed Solution

A distributed AI-powered multi-sensor architecture that:

- Continuously monitors environmental and structural parameters  
- Sends sensor data via MQTT in JSON format  
- Uses AI models for forecasting and anomaly detection  
- Generates a real-time Risk Score (0–100)  
- Activates automated evacuation alerts  
- Prevents unsafe worker entry via RFID-based control  

---

# System Architecture

The system consists of three major layers:

---

## 1. Sensor Node (ESP32 DevKit V1 – 38 Pin)

### Connected Sensors

- MQ-2 (Methane, LPG, Smoke)
- MQ-135 (Air Quality)
- MQ-7 (Carbon Monoxide)
- Vibration Sensor
- 4-Pin Sound Sensor
- Ultrasonic Sensor (Liquid Level)
- Flame Sensor
- MPU6050 (Tilt / Structural Monitoring)
- RFID Scanner
- 16x2 LCD Display

### Responsibilities

- Collect sensor data  
- Convert data into JSON format  
- Publish data to MQTT broker  
- Display live readings on LCD  

---

## 2. AI Engine (Flask Backend)

Receives sensor data via MQTT and applies:

- Random Forest (Risk Classification)
- LSTM (Time-Series Forecasting)
- Weighted Sensor Fusion (Risk Score Calculation)
- Z-Score Anomaly Detection

### Outputs

- Risk Score (0–100)
- Status: Safe / Warning / Critical
- Predicted Time-to-Danger
- Alert signals

All processed data is stored in a database for:

- Historical analysis  
- Compliance tracking  
- Model retraining  

---

## 3. Alert Node (ESP32 – 30 Pin)

### Connected Devices

- 0.96" OLED Display
- 5 Color LEDs
- Passive Buzzer

### Responsibilities

- Fetch risk score from backend API  
- Trigger visual and sound alerts  
- Display evacuation messages  
- Indicate safety levels using LED color coding  

---

# Data Flow

Sensors
↓
ESP32 (38 Pin)
↓
MQTT (JSON Data)
↓
Flask Backend AI Engine
↓
Database + Dashboard
↓
ESP32 Alert Node (30 Pin)
↓
LED + Buzzer + OLED


---

# AI Risk Score Model

Risk Score is calculated using weighted sensor fusion:

Risk Score =
(w1 × Gas Index) +
(w2 × CO Level) +
(w3 × Temperature/Humidity Factor) +
(w4 × Vibration Risk) +
(w5 × Structural Tilt) +
(w6 × Sound Anomaly)


Additional AI capabilities:

- Gas accumulation trend prediction  
- Time-series forecasting  
- Structural anomaly detection  
- Entry denial logic based on risk threshold  

---

# Communication Stack

- Protocol: MQTT  
- Data Format: JSON  
- Backend: Flask (Python)  
- Database: MySQL / PostgreSQL  
- Dashboard: Web-hosted interface  
- Hardware: Dual ESP32 architecture  

---

# Key Features

- Predictive hazard detection  
- AI-based risk scoring  
- Multi-sensor fusion system  
- Distributed IoT architecture  
- Automated evacuation alerts  
- Worker entry control using RFID  
- Industrial scalability  

---

# Sustainable Development Goals (SDG Alignment)

- SDG 3 – Good Health & Well-Being  
- SDG 8 – Decent Work & Economic Growth  
- SDG 9 – Industry, Innovation & Infrastructure  
- SDG 11 – Sustainable Cities & Communities  

---

# Hardware Requirements

- 2x ESP32 Boards  
- MQ-2, MQ-7, MQ-135 Sensors  
- MPU6050  
- Ultrasonic Sensor  
- Flame Sensor  
- RFID Module  
- 16x2 LCD  
- 0.96" OLED  
- LEDs (5 Colors)  
- Passive Buzzer  

---

# Software Requirements

- Python 3.x  
- Flask  
- MQTT Broker (Mosquitto)  
- Scikit-learn  
- TensorFlow / Keras  
- MySQL / PostgreSQL  

---

# Repository Structure


---

# Future Enhancements

- Edge AI deployment on ESP32  
- LoRa-based industrial mesh network  
- Mobile application integration  
- PLC integration  
- Patent filing  
- Industrial safety certification  

---

# Team

Team Name: [Your Team Name]  
Institution: [Your Institution]  
Year: 2026  

---

# License

This project is developed for research and industrial innovation purposes.


