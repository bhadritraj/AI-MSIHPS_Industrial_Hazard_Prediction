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

# 🏗 System Architecture

The system consists of three major layers:

---

## 🔵 1. Sensor Node (ESP32 DevKit V1 – 38 Pin)

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

## 🧠 2. AI Engine (Flask Backend)

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

## 🔴 3. Alert Node (ESP32 – 30 Pin)

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

# 🔁 Data Flow
