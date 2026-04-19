# Real-Time Scalable Event Processing System with Auto-Scaling Simulation

## 👤 Author
Piyush Kumar  
M.Tech (Data Engineering)  
IIT Jodhpur  

---

## 📌 Project Overview

This project aims to design and implement a **real-time scalable event processing system** inspired by platforms like BookMyShow, where massive traffic spikes occur during ticket launches.

During such events:
- Thousands of users perform actions simultaneously
- Systems receive continuous streams of events
- Sudden load spikes (10x–100x) can crash traditional systems

This project simulates such scenarios and builds a system capable of:
- Processing events in real time
- Handling high data velocity
- Scaling dynamically based on load (in progress)

---

## 🚀 Current Progress (~40%)

### ✅ Completed
- Use case finalized (ticket booking system)
- System architecture designed
- Kafka and Zookeeper setup using Docker
- Producer implemented (event generator)
- Consumer implemented (event processing pipeline)

### ⏳ In Progress
- Auto-scaling module (dynamic worker management)
- Load-based performance evaluation

---

## 🧠 System Architecture (Current)

Producer → Kafka → Consumer → (Auto-Scaling Module - Upcoming)

---

## 🛠️ Tech Stack

- **Python**
- **Apache Kafka**
- **Zookeeper**
- **Docker**
- **VS Code**

---

## ⚙️ Why These Technologies?

### 🔹 Apache Kafka
Kafka is used as the core streaming platform because:
- It can handle **high-throughput real-time data**
- It acts as a **buffer between producers and consumers**
- It ensures **fault-tolerant and scalable event streaming**
- Widely used in industry (finance, booking systems, etc.)

---

### 🔹 Zookeeper
Zookeeper is required for Kafka because:
- It manages **Kafka cluster coordination**
- Keeps track of brokers and topics
- Ensures **system consistency and reliability**

---

### 🔹 Python
Python is used for:
- Rapid development
- Easy simulation of real-time events
- Strong ecosystem for data engineering tasks

---

### 🔹 Docker
Docker is used to:
- Run Kafka and Zookeeper easily
- Ensure **consistent environment setup**
- Avoid manual installation issues

---

## 📂 Project Structure
